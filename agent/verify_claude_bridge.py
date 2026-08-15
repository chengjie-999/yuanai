"""Claude Code 桥接离线验证（不连云端，直接驱动 handler 断言事件流）

用法:
    python -m agent.verify_claude_bridge

断言序列: agent → token* → done（简单问答）
并验证会话持久化: 第二次请求同 cloud session_id 时复用 claude session
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yuanai_core.core.schemas import ChatRequest
from agent.claude_bridge import ClaudeBridgeHandler


async def run_case(handler: ClaudeBridgeHandler, name: str, session_id: str, prompt: str) -> bool:
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"输入: {prompt}")
    print(f"{'='*60}")

    req = ChatRequest(
        request_id=f"bridge-verify-{abs(hash((name, prompt))) % 100000}",
        session_id=session_id,
        user_id=0,
        messages=[{"role": "user", "content": prompt}],
    )

    seq = []
    full_text = ""
    async for event in handler.stream(req):
        seq.append(event.type)
        if event.type == "token":
            print(event.data, end="", flush=True)
            full_text += event.data
        elif event.type == "agent":
            print(f"\n  [身份] sender={event.data.get('sender')}")
        elif event.type == "tool_start":
            print(f"\n   工具开始: {event.data.get('name')}")
        elif event.type == "tool_end":
            out = str(event.data.get("output", ""))
            print(f"  OK 工具完成: {event.data.get('name')} → {out[:80]}")
        elif event.type == "done":
            print("\nOK 完成")
        elif event.type == "error":
            print(f"\nERR 错误: {event.data}")

    ok = "agent" in seq and "done" in seq and "token" in seq
    print(f"\n断言: 序列={seq}")
    print(f"结果: {'通过 OK' if ok else '失败 ERR'}")
    return ok


async def main():
    handler = ClaudeBridgeHandler()

    # 用例 1: 简单问答
    ok1 = await run_case(handler, "简单问答", "bridge-verify-session", "用一句话自我介绍，说明你是 Claude Code")

    # 用例 2: 工具调用（列目录，应有 tool_start/tool_end）
    print(f"\n{'='*60}")
    print("测试: 工具调用（列目录）")
    print(f"{'='*60}")
    req2 = ChatRequest(
        request_id="bridge-verify-tool",
        session_id="bridge-verify-session-2",
        user_id=0,
        messages=[{"role": "user", "content": "运行 ls 列出项目根目录，一句话报告"}],
    )
    seq2 = []
    async for event in handler.stream(req2):
        seq2.append(event.type)
        if event.type == "tool_start":
            print(f"   工具开始: {event.data.get('name')}")
        elif event.type == "tool_end":
            print(f"  OK 工具完成: {event.data.get('name')}")
        elif event.type == "token":
            print(event.data, end="", flush=True)
        elif event.type == "error":
            print(f"\nERR 错误: {event.data}")
    ok2 = "agent" in seq2 and "tool_start" in seq2 and "tool_end" in seq2 and "done" in seq2
    print(f"\n断言: 序列={seq2}")
    print(f"结果: {'通过 OK' if ok2 else '失败 ERR'}")

    # 用例 3: 会话续接（同 session_id 第二次提问，应能引用上文）
    print(f"\n{'='*60}")
    print("测试: 会话续接（同 session_id 追问）")
    print(f"{'='*60}")
    req3 = ChatRequest(
        request_id="bridge-verify-resume",
        session_id="bridge-verify-session",
        user_id=0,
        messages=[{"role": "user", "content": "刚才的自我介绍里，你说你是什么？一句话回答"}],
    )
    seq3 = []
    full3 = ""
    async for event in handler.stream(req3):
        seq3.append(event.type)
        if event.type == "token":
            print(event.data, end="", flush=True)
            full3 += event.data
        elif event.type == "error":
            print(f"\nERR 错误: {event.data}")
    ok3 = "agent" in seq3 and "done" in seq3 and "token" in seq3
    print(f"\n断言: 序列={seq3}")
    print(f"结果: {'通过 OK' if ok3 else '失败 ERR'}")
    print(f"\n（续接是否真正引用上文需人工确认，自动断言只查事件流）")

    print(f"\n{'='*60}")
    print(f"总结果: {'全部通过 OK' if ok1 and ok2 and ok3 else '存在失败 ERR'}")
    sys.exit(0 if ok1 and ok2 and ok3 else 1)


if __name__ == "__main__":
    asyncio.run(main())
