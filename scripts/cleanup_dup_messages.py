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
    return hashlib.md5(f"{role}|{content or ''}|{images or ''}".encode("utf-8")).hexdigest()


def find_dup_blocks(sigs):
    """返回 (block_len, last_block_start)：sigs 前 block_len 条在后续完整重复
    至少 2 次；last_block_start = 最后一个完整重复块的起始下标。无重复返回 None"""
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
    # 验证块内容完整一致（抽验首 8 条与尾 3 条）
    for j in list(range(0, min(8, L))) + [L - 3, L - 2, L - 1]:
        if j < 0 or j >= L:
            continue
        if sigs[j] != sigs[L + j]:
            return None
    # 找最后一个完整重复块的起点
    last_start = 0
    s = 0
    while s + 2 * L <= n:
        ok = True
        for j in range(L):
            if sigs[s + j] != sigs[s + L + j]:
                ok = False
                break
        if ok:
            last_start = s + L
            s += L
        else:
            break
    repeats = (last_start // L) if L else 0
    if repeats < 2:
        return None
    return L, last_start


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
    for (sid,) in sessions:
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
        L, last_start = found
        del_ids = [r[0] for r in rows[:last_start]]
        print(f"[会话 {sid[:12]}…] 共 {len(rows)} 条，块长 {L}，重复块 {last_start // L} 份"
              f" → 保留 {len(rows) - last_start} 条，删除 {len(del_ids)} 条")
        if args.apply and del_ids:
            with db.session() as s:
                # 分批删（单条 IN 太长）
                for i in range(0, len(del_ids), 200):
                    chunk = del_ids[i:i + 200]
                    s.execute(text(
                        "DELETE FROM ai_chat WHERE session_id=:sid AND id IN :ids"),
                        {"sid": sid, "ids": tuple(chunk)})
                s.commit()
            total_del += len(del_ids)
    if args.apply:
        print(f"完成：共删除 {total_del} 条重复消息")
    else:
        print("dry-run（未删除任何数据）——确认无误后加 --apply 执行")


if __name__ == "__main__":
    main()
