#!/usr/bin/env python
"""Claude Code PreToolUse/PostToolUse 钩子：拦截危险操作 + 审计日志

仅在桥接调用（环境变量 CLAUDE_CODE_BRIDGE=1）时启用拦截，
不影响用户本人在本仓库的日常交互会话。

PreToolUse：classify 结果 deny/review → exit 2（拒绝并给出原因）
PostToolUse：写审计日志，恒放行（exit 0）
"""

import json
import os
import sys
import time

# 钩子以仓库根为 cwd 运行，但也兼容任意 cwd：按自身位置推导项目根
HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HOOK_DIR))
sys.path.insert(0, PROJECT_ROOT)

AUDIT_LOG = os.path.join(PROJECT_ROOT, "data", "logs", "claude_audit.log")


def _audit(record: str):
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {record}\n")
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 无法解析则放行（钩子不应成为故障点）

    # 仅桥接调用启用拦截（CLI/SDK 调用方注入 CLAUDE_CODE_BRIDGE=1）
    if os.getenv("CLAUDE_CODE_BRIDGE", "0") != "1":
        sys.exit(0)

    hook_event = payload.get("hook_event_name", "")
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    from agent.bridge_policy import classify, explain

    if hook_event == "PreToolUse":
        verdict = classify(tool_name, tool_input)
        summary = json.dumps(tool_input, ensure_ascii=False)[:200]
        _audit(f"PreToolUse | {tool_name} | {verdict} | {summary}")
        if verdict in ("deny", "review"):
            reason = explain(tool_name, tool_input)
            if verdict == "review":
                reason = f"{reason}（审批通道未启用，已拒绝）"
            print(reason, file=sys.stderr)
            sys.exit(2)  # 拒绝并给出原因
        sys.exit(0)

    if hook_event == "PostToolUse":
        response = payload.get("tool_response", {})
        output = response.get("output") if isinstance(response, dict) else response
        output_len = len(str(output)) if output is not None else 0
        summary = json.dumps(tool_input, ensure_ascii=False)[:200]
        _audit(f"PostToolUse | {tool_name} | output_len={output_len} | {summary}")
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
