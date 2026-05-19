"""本地 MySQL ↔ 云 MySQL 双向数据库合并工具

基于业务唯一键（非 auto-increment ID）比对差异，交互式确认后双向同步。

用法:
    python -m db.merge          # 交互式合并
    python -m db.merge --dry-run   # 仅预览不写入
"""
import sys
import argparse
import logging

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# 表合并元信息
# ============================================================================

TABLES_META = [
    {
        "table": "users",
        "merge_keys": ["username"],
        "conflict_mode": "interactive",   # password_hash 冲突需要人工裁决
        "interactive_fields": ["password_hash"],
        "parent": None,
    },
    {
        "table": "websites",
        "merge_keys": ["name"],
        "conflict_mode": "newer_wins",
        "parent": None,
    },
    {
        "table": "chat_session",
        "merge_keys": ["session_id"],
        "conflict_mode": "newer_wins",    # 按 update_time 比较
        "time_field": "update_time",
        "parent": "users",                # user_id 需要 remap
    },
    {
        "table": "ai_chat",
        "merge_keys": ["session_id", "create_time", "role"],
        "conflict_mode": "keep_both",     # 内容不同则两边都保留
        "parent": "chat_session",
    },
    {
        "table": "task_image",
        "merge_keys": ["session_id", "task_url"],
        "conflict_mode": "newer_wins",
        "parent": "chat_session",
    },
    {
        "table": "crawl_records",
        "merge_keys": ["url", "user_id"],
        "conflict_mode": "newer_wins",
        "parent": "users",
    },
    {
        "table": "datasets",
        "merge_keys": ["name", "user_id", "file_path"],
        "conflict_mode": "newer_wins",
        "parent": "users",
    },
]


def _connect(mysql_config: dict):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.engine import URL
    conn_url = URL.create(
        "mysql+pymysql",
        username=mysql_config["user"],
        password=mysql_config["password"],
        host=mysql_config["host"],
        port=mysql_config.get("port", 3306),
        database=mysql_config["database"],
    )
    engine = create_engine(conn_url)
    Session = sessionmaker(bind=engine)
    return Session()


def _get_all(session, table: str):
    from sqlalchemy import text
    rows = session.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
    return [dict(r) for r in rows]


def _build_key(row: dict, keys: list) -> tuple:
    return tuple(str(row.get(k, "")) for k in keys)


def _is_different(row_a: dict, row_b: dict, meta: dict) -> bool:
    skip = {"id"}
    for k, v in row_a.items():
        if k in skip:
            continue
        if str(v) != str(row_b.get(k, "")):
            return True
    return False


def _compare_time(row_a: dict, row_b: dict, meta: dict) -> dict:
    """返回时间较新的一方：'local' 或 'cloud'"""
    tf = meta.get("time_field", "create_time")
    ta = row_a.get(tf)
    tb = row_b.get(tf)
    if ta is None:
        return "cloud"
    if tb is None:
        return "local"
    return "local" if ta >= tb else "cloud"


def _dedup_ai_chat(local_rows: list, cloud_rows: list) -> tuple:
    """ai_chat 特殊处理：用 (session_id, create_time, role) 作为近似唯一键，去重后返回各自独有"""
    local_set = set()
    cloud_set = set()
    for r in local_rows:
        local_set.add((str(r["session_id"]), str(r["create_time"]), r["role"]))
    for r in cloud_rows:
        cloud_set.add((str(r["session_id"]), str(r["create_time"]), r["role"]))
    return local_set - cloud_set, cloud_set - local_set


def _insert_row(session, table: str, row: dict):
    """插入一行记录"""
    from sqlalchemy import text
    cols = [k for k in row if k != "id"]
    placeholders = ", ".join([f":{c}" for c in cols])
    col_names = ", ".join([f"`{c}`" for c in cols])
    sql = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders})"
    session.execute(text(sql), {c: row[c] for c in cols})


def _remap_user_id(row: dict, mapping: dict):
    """将 row 中的 user_id 从源库 ID 映射为目标库 ID"""
    if "user_id" in row and row["user_id"] is not None:
        old_id = row["user_id"]
        row["user_id"] = mapping.get(old_id, old_id)


def merge_all(local_config: dict, cloud_config: dict, dry_run: bool = False):
    """执行双向合并"""
    local_sess = _connect(local_config)
    cloud_sess = _connect(cloud_config)

    user_id_to_local = {}   # cloud user_id → local user_id (按 username)
    user_id_to_cloud = {}   # local user_id → cloud user_id (按 username)

    stats = {"pushed": 0, "pulled": 0, "conflicts": 0, "skipped": 0}

    try:
        for meta in TABLES_META:
            table = meta["table"]
            print(f"\n--- [{table}] ---")

            local_rows = _get_all(local_sess, table)
            cloud_rows = _get_all(cloud_sess, table)
            print(f"  本地: {len(local_rows)} 条, 云端: {len(cloud_rows)} 条")

            # 特殊处理：users 表先建立映射
            if table == "users":
                _merge_users(local_sess, cloud_sess, local_rows, cloud_rows, meta, dry_run, stats)
                # 重建映射
                local_users = _get_all(local_sess, "users")
                cloud_users = _get_all(cloud_sess, "users")
                user_id_to_local = {}
                user_id_to_cloud = {}
                for u in cloud_users:
                    match = next((lu for lu in local_users if lu["username"] == u["username"]), None)
                    if match:
                        user_id_to_local[u["id"]] = match["id"]
                        user_id_to_cloud[match["id"]] = u["id"]
                continue

            if table == "websites":
                _merge_simple_bidirectional(
                    local_sess, cloud_sess, local_rows, cloud_rows, meta, dry_run, stats
                )
                continue

            if table == "ai_chat":
                _merge_ai_chat(local_sess, cloud_sess, local_rows, cloud_rows, dry_run, stats)
                continue

            # 有 parent 的表需要 remap user_id
            if meta.get("parent") == "users":
                for r in local_rows:
                    r["_orig_user_id"] = r.get("user_id")
                for r in cloud_rows:
                    r["_orig_user_id"] = r.get("user_id")

            _merge_simple_bidirectional(
                local_sess, cloud_sess, local_rows, cloud_rows, meta, dry_run, stats,
                user_id_to_cloud=user_id_to_cloud,
                user_id_to_local=user_id_to_local,
            )

        print(f"\n=== 合并完成 ===")
        print(f"  推送 (本地→云端): {stats['pushed']} 条")
        print(f"  拉取 (云端→本地): {stats['pulled']} 条")
        print(f"  冲突已解决: {stats['conflicts']} 条")
        print(f"  跳过: {stats['skipped']} 条")

    finally:
        local_sess.close()
        cloud_sess.close()


def _merge_users(local_sess, cloud_sess, local_rows, cloud_rows, meta, dry_run, stats):
    local_by_name = {r["username"]: r for r in local_rows}
    cloud_by_name = {r["username"]: r for r in cloud_rows}

    local_only = set(local_by_name) - set(cloud_by_name)
    cloud_only = set(cloud_by_name) - set(local_by_name)
    common = set(local_by_name) & set(cloud_by_name)

    # 本地独有 → 推送到云端
    for name in local_only:
        row = local_by_name[name]
        print(f"  → 推送用户: {name}")
        if not dry_run:
            _insert_row(cloud_sess, "users", row)
            cloud_sess.commit()
        stats["pushed"] += 1

    # 云端独有 → 拉取到本地
    for name in cloud_only:
        row = cloud_by_name[name]
        print(f"  ← 拉取用户: {name}")
        if not dry_run:
            _insert_row(local_sess, "users", row)
            local_sess.commit()
        stats["pulled"] += 1

    # 冲突：两边都有的用户
    for name in common:
        lrow = local_by_name[name]
        crow = cloud_by_name[name]
        if not _is_different(lrow, crow, meta):
            stats["skipped"] += 1
            continue
        # password_hash 不同 → 交互式裁决
        if lrow.get("password_hash") != crow.get("password_hash"):
            print(f"\n  ⚠ 用户 '{name}' 两端密码不同")
            print(f"    本地创建时间: {lrow.get('create_time')}")
            print(f"    云端创建时间: {crow.get('create_time')}")
            choice = input("    保留哪一方? [local/cloud/skip] ").strip().lower()
            if choice == "local":
                if not dry_run:
                    crow["password_hash"] = lrow["password_hash"]
                    _update_row(cloud_sess, "users", crow, ["username"])
                    cloud_sess.commit()
                stats["conflicts"] += 1
            elif choice == "cloud":
                if not dry_run:
                    lrow["password_hash"] = crow["password_hash"]
                    _update_row(local_sess, "users", lrow, ["username"])
                    local_sess.commit()
                stats["conflicts"] += 1
            else:
                stats["skipped"] += 1
        # 其他字段以较新时间为准
        winner = _compare_time(lrow, crow, meta)
        if winner == "local":
            if not dry_run:
                _update_row(cloud_sess, "users", lrow, ["username"])
                cloud_sess.commit()
            stats["pushed"] += 1
        elif winner == "cloud":
            if not dry_run:
                _update_row(local_sess, "users", crow, ["username"])
                local_sess.commit()
            stats["pulled"] += 1


def _merge_simple_bidirectional(local_sess, cloud_sess, local_rows, cloud_rows, meta,
                                 dry_run, stats, user_id_to_cloud=None, user_id_to_local=None):
    merge_keys = meta["merge_keys"]

    local_keyed = {_build_key(r, merge_keys): r for r in local_rows}
    cloud_keyed = {_build_key(r, merge_keys): r for r in cloud_rows}

    local_only = set(local_keyed) - set(cloud_keyed)
    cloud_only = set(cloud_keyed) - set(local_keyed)
    common = set(local_keyed) & set(cloud_keyed)

    for key in local_only:
        row = dict(local_keyed[key])
        if user_id_to_cloud and "user_id" in row and row["user_id"] is not None:
            row["user_id"] = user_id_to_cloud.get(row["user_id"], row["user_id"])
        row.pop("_orig_user_id", None)
        if not dry_run:
            _insert_row(cloud_sess, meta["table"], row)
            cloud_sess.commit()
        stats["pushed"] += 1

    for key in cloud_only:
        row = dict(cloud_keyed[key])
        if user_id_to_local and "user_id" in row and row["user_id"] is not None:
            row["user_id"] = user_id_to_local.get(row["user_id"], row["user_id"])
        row.pop("_orig_user_id", None)
        if not dry_run:
            _insert_row(local_sess, meta["table"], row)
            local_sess.commit()
        stats["pulled"] += 1

    for key in common:
        lrow = local_keyed[key]
        crow = cloud_keyed[key]
        if not _is_different(lrow, crow, meta):
            stats["skipped"] += 1
            continue
        winner = _compare_time(lrow, crow, meta)
        if winner == "local":
            target = dict(lrow)
            target.pop("_orig_user_id", None)
            if not dry_run:
                _update_row(cloud_sess, meta["table"], target, merge_keys)
                cloud_sess.commit()
            stats["pushed"] += 1
        else:
            target = dict(crow)
            target.pop("_orig_user_id", None)
            if not dry_run:
                _update_row(local_sess, meta["table"], target, merge_keys)
                local_sess.commit()
            stats["pulled"] += 1


def _merge_ai_chat(local_sess, cloud_sess, local_rows, cloud_rows, dry_run, stats):
    local_only_keys, cloud_only_keys = _dedup_ai_chat(local_rows, cloud_rows)

    for key in local_only_keys:
        row = next((r for r in local_rows
                     if str(r["session_id"]) == key[0]
                     and str(r["create_time"]) == key[1]
                     and r["role"] == key[2]), None)
        if row is None:
            continue
        row = dict(row)
        if not dry_run:
            _insert_row(cloud_sess, "ai_chat", row)
            cloud_sess.commit()
        stats["pushed"] += 1

    for key in cloud_only_keys:
        row = next((r for r in cloud_rows
                     if str(r["session_id"]) == key[0]
                     and str(r["create_time"]) == key[1]
                     and r["role"] == key[2]), None)
        if row is None:
            continue
        row = dict(row)
        if not dry_run:
            _insert_row(local_sess, "ai_chat", row)
            local_sess.commit()
        stats["pulled"] += 1


def _update_row(session, table: str, row: dict, merge_keys: list):
    from sqlalchemy import text
    set_cols = [k for k in row if k not in merge_keys and k != "id"]
    set_clause = ", ".join([f"`{c}` = :{c}" for c in set_cols])
    where_clause = " AND ".join([f"`{c}` = :where_{c}" for c in merge_keys])
    sql = f"UPDATE `{table}` SET {set_clause} WHERE {where_clause}"
    params = {c: row[c] for c in set_cols}
    params.update({f"where_{c}": row[c] for c in merge_keys})
    session.execute(text(sql), params)


def _load_config_local():
    from utils.sensitive_data import get_mysql_config
    return get_mysql_config()


def _load_config_cloud():
    from utils.sensitive_data import get_cloud_mysql_config
    return get_cloud_mysql_config()


def main():
    parser = argparse.ArgumentParser(description="本地 ↔ 云端数据库双向合并")
    parser.add_argument("--dry-run", action="store_true", help="仅预览差异，不写入")
    args = parser.parse_args()

    print("=== 数据库双向合并工具 ===\n")

    try:
        local_cfg = _load_config_local()
        print(f"本地数据库: {local_cfg['host']}:{local_cfg['port']}/{local_cfg['database']}")
    except Exception as e:
        print(f"本地数据库连接失败: {e}")
        sys.exit(1)

    try:
        cloud_cfg = _load_config_cloud()
        if not cloud_cfg.get("host"):
            print("云数据库未配置 (CLOUD_MYSQL_HOST 为空)")
            sys.exit(1)
        print(f"云数据库: {cloud_cfg['host']}:{cloud_cfg['port']}/{cloud_cfg['database']}")
    except Exception as e:
        print(f"云数据库连接失败: {e}")
        sys.exit(1)

    if args.dry_run:
        print("\n⚠ DRY-RUN 模式，不会写入任何数据\n")

    merge_all(local_cfg, cloud_cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
