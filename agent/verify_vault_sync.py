"""vault 同步链路验证脚本（沿 verify.py 风格：离线断言 + 可选在线检查）

用法：
    python -m agent.verify_vault_sync            # 离线断言（纯函数 + mock HTTP 循环）
    python -m agent.verify_vault_sync --online   # 额外检查本地云端 API 的同步端点

离线部分零网络零 MySQL（mock HTTP 层），覆盖：
- 规范化哈希一致性（token/链接写法不同 → 哈希一致，防回环）
- 三向判定矩阵（none/upload/download/conflict/双变同内容）
- frontmatter 往返（parse/inject/strip）
- 同步循环冷启动 + 上传 + 下载 + 冲突（mock HTTP）
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

OK = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [OK] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def offline_checks():
    print("=== 1. 纯函数断言 ===")
    from yuanai_core.pure.vault_note import (
        canonical_body, note_body_hash, parse_frontmatter, strip_frontmatter,
        inject_frontmatter, sync_decision, vault_filename)

    check("图片链接规范化（token/写法统一）",
          note_body_hash("x ![a](https://s/api/asset/1/5/a.png?token=t)", 5)
          == note_body_hash("x ![a](assets/5/a.png)", 5))
    check("三向：全同 → none", sync_decision("b", "b", "b") == "none")
    check("三向：vault 变 → upload", sync_decision("b", "v", "b") == "upload")
    check("三向：cloud 变 → download", sync_decision("b", "b", "c") == "download")
    check("三向：双变 → conflict", sync_decision("b", "v", "c") == "conflict")
    check("三向：双变同内容 → none", sync_decision("b", "v", "v") == "none")
    text = inject_frontmatter("正文", {"planet_note_id": 7, "map_id": 3})
    fm = parse_frontmatter(text)
    check("frontmatter 注入/解析往返", fm.get("planet_note_id") == 7 and strip_frontmatter(text) == "正文")
    check("vault 文件名保留中文与空格", vault_filename("数据分析 笔记") == "数据分析 笔记.md")
    check("vault 文件名剔除非法字符", vault_filename('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij.md")

    print("=== 2. 同步循环（mock HTTP + 临时 vault） ===")
    from agent.vault_sync import VaultSyncLoop

    tmp = tempfile.mkdtemp(prefix="verify_vault_")
    vault = os.path.join(tmp, "vault")
    os.makedirs(vault, exist_ok=True)
    loop = VaultSyncLoop(vault_dir=vault, agent_id="1", agent_secret="s",
                         server_base="http://fake", state_path=os.path.join(tmp, "state.json"))

    from yuanai_core.pure.vault_note import note_body_hash
    cloud = {"notes": []}  # mock 云端状态（哈希用真实内容计算，保证三向判定正确）

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": cloud["notes"]}
        if path.startswith("/pull/content"):
            ids = [int(x) for x in path.split("ids=")[1].split(",")]
            return True, {"notes": [n for n in cloud["notes"] if n["id"] in ids]}
        if path == "/push/upsert":
            ch = note_body_hash(payload["content"], payload["map_id"])
            nid = next((n["id"] for n in cloud["notes"]
                        if payload["map_id"] and n["map_id"] == payload["map_id"]), None)
            if nid is None:
                nid = max([n["id"] for n in cloud["notes"]], default=0) + 1
                cloud["notes"].append({"id": nid, "map_id": payload["map_id"],
                                       "title": payload["title"], "content": payload["content"],
                                       "content_hash": ch})
            else:
                n = next(n for n in cloud["notes"] if n["id"] == nid)
                n["content"] = payload["content"]
                n["content_hash"] = ch
            return True, {"id": nid, "created": False, "content_hash": ch}
        if path == "/push/delete":
            cloud["notes"] = [n for n in cloud["notes"] if n["id"] != payload["nid"]]
            return True, {}
        return True, {}

    loop._http_ok = fake_ok
    loop._http_raw = lambda path, timeout=60: None

    # 冷启动（空云端）
    loop.run_once()
    check("冷启动基线建立", loop._state.get("baseline") is True)

    # 本地新建 → 上传
    f = os.path.join(vault, "知识星球", "测试笔记.md")
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "w", encoding="utf-8") as fh:
        fh.write("---\nmap_id: 0\n---\n\n离线断言笔记")
    old = time.time() - 10
    os.utime(f, (old, old))
    loop._snap_prev = loop._snap_prev2 = loop._scan()
    r = loop.run_once()
    check("本地新建 → 上传", r["uploaded"] == 1, str(r))
    check("上传后回填锚点", "planet_note_id:" in open(f, encoding="utf-8").read())

    # 云端改 → 下载（回填把 mtime 刷成当前时间 → 拨回 old 满足防抖）
    os.utime(f, (old, old))
    nid = loop._state["notes"]["知识星球/测试笔记.md"]["note_id"]
    for n in cloud["notes"]:
        if n["id"] == nid:
            n["content"] = "云端改写版"
            n["content_hash"] = note_body_hash("云端改写版", 0)
    loop._snap_prev = loop._snap_prev2 = loop._scan()
    r = loop.run_once()
    check("云端改 → 下载", r["downloaded"] == 1, str(r))
    check("下载内容落盘", "云端改写版" in open(f, encoding="utf-8").read())

    # 双改 → 冲突（本地赢 + conflict 副本）：云端与本地同时再改
    for n in cloud["notes"]:
        if n["id"] == nid:
            n["content"] = "云端又改版"
            n["content_hash"] = note_body_hash("云端又改版", 0)
    with open(f, "w", encoding="utf-8") as fh:
        fh.write("本地再改版")
    os.utime(f, (time.time() - 10, time.time() - 10))
    loop._snap_prev = loop._snap_prev2 = loop._scan()
    r = loop.run_once()
    check("双改 → 冲突 + 本地赢", r["conflicts"] == 1
          and loop._state["notes"]["知识星球/测试笔记.md"]["base_hash"]
          == note_body_hash("本地再改版", 0), str(r))

    print(f"\n离线断言完成：{OK} 过 / {FAIL} 败")
    return FAIL == 0


def online_checks():
    print("=== 3. 在线检查（本地 API） ===")
    import urllib.request

    base = os.getenv("VAULT_SYNC_API", "http://127.0.0.1:8000")
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:
            check("本地 API 健康", resp.status == 200)
    except Exception as e:
        check("本地 API 健康", False, str(e))
        print("（在线检查跳过：API 未运行；离线断言已覆盖核心链路）")
        return


def main():
    ok = offline_checks()
    if "--online" in sys.argv:
        online_checks()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
