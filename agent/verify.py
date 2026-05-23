"""多智能体链路验证脚本 — 本地测试，无需 MySQL/Redis/前端"""

import asyncio
import io
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows GBK → UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from agent.orchestrator import Orchestrator
from yuanai_core.core.schemas import ChatRequest


TEST_CASES = [
    {
        "name": "数据分析 — 列出数据集",
        "messages": [
            {"role": "system", "content": "你是小元AI统筹助手。调用子Agent帮用户完成任务。"},
            {"role": "user", "content": "帮我列出现有的所有数据集"},
        ],
    },
    {
        "name": "数据采集 — 爬取网页",
        "messages": [
            {"role": "system", "content": "你是小元AI统筹助手。调用子Agent帮用户完成任务。"},
            {"role": "user", "content": "帮我抓取 https://httpbin.org/headers 的内容"},
        ],
    },
    {
        "name": "跨领域 — 先采集再分析",
        "messages": [
            {"role": "system", "content": "你是小元AI统筹助手。调用子Agent帮用户完成任务。"},
            {"role": "user", "content": "先看看有哪些数据集，然后帮我分析第一个数据集"},
        ],
    },
]


async def run_test(case: dict, orch: Orchestrator):
    print(f"\n{'='*60}")
    print(f"测试: {case['name']}")
    print(f"用户: {case['messages'][-1]['content']}")
    print(f"{'='*60}")
    print()

    req = ChatRequest(
        request_id=f"verify-{hash(case['name'])}",
        session_id="verify",
        messages=case["messages"],
    )

    full_text = ""
    async for event in orch.stream(req):
        if event.type == "token":
            print(event.data, end="", flush=True)
            full_text += event.data
        elif event.type == "tool_start":
            name = event.data.get("name", "")
            print(f"\n  🔧 调用子Agent: {name}")
        elif event.type == "tool_end":
            name = event.data.get("name", "")
            output = str(event.data.get("output", ""))
            if len(output) > 120:
                output = output[:120] + "..."
            print(f"  ✅ {name} 完成")
            if output:
                print(f"     → {output}")
        elif event.type == "done":
            print(f"\n\n✅ 测试完成")
        elif event.type == "error":
            print(f"\n❌ 错误: {event.data}")

    print()


async def main():
    orch = Orchestrator()

    # 默认跑所有测试
    import argparse
    p = argparse.ArgumentParser(description="多智能体验证")
    p.add_argument("--case", type=int, default=0,
                   help="测试用例编号 (0=全部, 1=数据分析, 2=数据采集, 3=跨领域)")
    args = p.parse_args()

    if args.case == 0:
        cases = TEST_CASES
    else:
        cases = [TEST_CASES[min(args.case - 1, len(TEST_CASES) - 1)]]

    for case in cases:
        await run_test(case, orch)

    print(f"\n全部 {len(cases)} 个测试完成")


if __name__ == "__main__":
    asyncio.run(main())
