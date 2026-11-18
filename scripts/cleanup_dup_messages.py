# -*- coding: utf-8 -*-
"""清理会话重复消息副本（2026-11-18 生产事故：整段对话重复 12 遍）。

根因已修（前端创建即赋 msg_id + (session_id,msg_id) 唯一索引 + 轮询合并按 id
去重），本脚本清理存量数据：检测「整段重复块」（同一会话里前 N 条消息内容
与后续 N 条完全一致、且重复 ≥2 次），保留最后一个完整副本及其后的新消息，
删除更早的旧副本。

用法（在服务器上执行，dry-run 默认只报告）：
    python scripts/cleanup_dup_messages.py                 # 全库 dry-run
    python scripts/cleanup_dup_messages.py --session-id xxx  # 单会话
    python scripts/cleanup_dup_messages.py --apply          # 确认后执行删除
"""

import argparse
import hashlib
import sys

sys.path.insert(0, ".")


def _sig(role: str, content: str, images: str) -> str:
    # 只比「正文」不比 META 信封——12 份副本是不同轮次保存的，META 里
    # turn/工具结果等字段不同（正文完全一致）；按完整 content 哈希会全部落空
    from yuanai_core.core.message import split_meta
    _, body = split_meta(content or "")
    return hashlib.md5(f"{role}|{body}|{images or ''}".encode("utf-8")).hexdigest()


def find_dup_blocks(sigs):
    """返回 (block_len, last_block_start, dup_starts)：前 block_len 条在后续完整
    重复 ≥2 次（各副本长度可不一致——真实事故数据每份副本 39~48 条不等，
    步进式比对会提前断走）。last_block_start = 最后一个完整重复块的起始下标。
    无重复返回 None"""
    n = len(sigs)
    if n < 16:
        return None
    # 第一个与首条内容相同的下标 = 候选块长 L
    L = None
    for i in range(1, n):
        if sigs[i] == sigs[0]:
            L = i
            break
    if L is None or L < 8:
        return None
    # 验证首块自洽（抽验首 8 条与尾 3 条）
    for j in list(range(0, min(8, L))) + [L - 3, L - 2, L - 1]:
        if j < 0 or j >= L:
            continue
        if sigs[j] != sigs[L + j]:
            return None
    # 收集所有「完整重复块起点」（与首块逐一比对，容忍各副本长短不一）
    starts = [0]
    for p in range(L, n - L + 1):
        if sigs[p:p + L] == sigs[0:L]:
            starts.append(p)
    if len(starts) < 3:  # 含原始块至少 3 份才认定整段重复病
        return None
    return L, starts[-1], starts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", default="", help="只处理指定会话")
    ap.add_argument("--apply", action="store_true", help="实际删除（默认 dry-run）")
    args = ap.parse_args()

    from sqlalchemy import text
    from db.session import AgentDatabase
    db = AgentDatabase()

    if args.session_id:
        sessions = [(args.session_id,)]
    else:
        with db.session() as s:
            sessions = [(r[0],) for r in s.execute(
                text("SELECT session_id FROM chat_session"))]

    total_del = 0
    scanned = 0
    found_sessions = 0
    for (sid,) in sessions:
        scanned += 1
        with db.session() as s:
            rows = s.execute(text(
                "SELECT id, role, content, images FROM ai_chat "
                "WHERE session_id=:sid ORDER BY id"), {"sid": sid}).fetchall()
        if len(rows) < 16:
            continue
        sigs = [_sig(r[1], r[2], r[3] or "") for r in rows]
        found = find_dup_blocks(sigs)
        if not found:
            continue
        found_sessions += 1
        L, last_start, starts = found
        # 只删「内容在保留块中已存在」的行——副本间隙里的唯一消息（如藏文轮次）
        # 内容不在保留块中 → 救援保留（宁可多留不可误删）
        kept_sigs = set(sigs[last_start:])
        del_ids = [r[0] for r, sg in zip(rows[:last_start], sigs[:last_start])
                   if sg in kept_sigs]
        rescued = last_start - len(del_ids)
        print(f"[会话 {sid[:12]}…] 共 {len(rows)} 条，块长 {L}，重复块 {len(starts)} 份"
              f" → 保留 {len(rows) - len(del_ids)} 条（含救援唯一消息 {rescued} 条），"
              f"删除 {len(del_ids)} 条")
        if args.apply and del_ids:
            with db.session() as s:
                # 删除前备份到 ai_chat_dup_backup（可回滚——加固：宁可多留不可误删）
                s.execute(text(
                    "CREATE TABLE IF NOT EXISTS ai_chat_dup_backup "
                    "(id INT, session_id VARCHAR(64), role VARCHAR(16), content MEDIUMTEXT, "
                    "images TEXT, msg_id VARCHAR(36), create_time TIMESTAMP NULL, "
                    "deleted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
                for i in range(0, len(del_ids), 200):
                    chunk = del_ids[i:i + 200]
                    s.execute(text(
                        "INSERT INTO ai_chat_dup_backup "
                        "(id, session_id, role, content, images, msg_id, create_time) "
                        "SELECT id, session_id, role, content, images, msg_id, create_time "
                        "FROM ai_chat WHERE session_id=:sid AND id IN :ids"),
                        {"sid": sid, "ids": tuple(chunk)})
                # 分批删（单条 IN 太长）
                for i in range(0, len(del_ids), 200):
                    chunk = del_ids[i:i + 200]
                    s.execute(text(
                        "DELETE FROM ai_chat WHERE session_id=:sid AND id IN :ids"),
                        {"sid": sid, "ids": tuple(chunk)})
                s.commit()
            total_del += len(del_ids)
    print(f"扫描 {scanned} 个会话，发现整段重复 {found_sessions} 个")
    if args.apply:
        print(f"完成：共删除 {total_del} 条重复消息（已备份到 ai_chat_dup_backup 表，"
              f"确认无异常后可自行 DROP）")
    else:
        print("dry-run（未删除任何数据）——确认无误后加 --apply 执行")


if __name__ == "__main__":
    main()
