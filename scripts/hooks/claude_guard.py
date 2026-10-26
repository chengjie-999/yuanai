#!/usr/bin/env python
"""Claude Code PreToolUse/PostToolUse 钩子：拦截危险操作 + 审计日志 + 桌宠联动

仅在桥接调用（环境变量 CLAUDE_CODE_BRIDGE=1）时启用拦截，
不影响用户本人在本仓库的日常交互会话。

PreToolUse：classify 结果 deny/review → exit 2（拒绝并给出原因）
PostToolUse：写审计日志，恒放行（exit 0）
桌宠联动（2026-10-25，yuan 薄封装后用户直接跑 claude 也不丢陪伴）：
PreToolUse→working+工具名 / PostToolUse→thinking / UserPromptSubmit→thinking /
Stop|SessionEnd→idle——交互会话与桥接路径都发，失败静默。
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


def _emit_pet(hook_event: str, tool_name: str):
    """桌宠六态联动（失败静默，不阻塞钩子）"""
    try:
        from agent.pet_events import emit
        if hook_event == "PreToolUse":
            emit(state="working", tool=str(tool_name)[:64])
        elif hook_event in ("PostToolUse", "UserPromptSubmit"):
            emit(state="thinking")
        elif hook_event in ("Stop", "SessionEnd"):
            emit(state="idle")
    except Exception:
        pass


_HOOK_TO_STATE = {
    "PreToolUse": ("working", True),        # (state, 是否带工具名)
    "PostToolUse": ("thinking", False),
    "UserPromptSubmit": ("thinking", False),
    "Stop": ("idle", False),
    "SessionEnd": ("idle", False),
}


def _report_activity(hook_event: str, tool_name: str):
    """云端活动上报（O2 观测 2026-10-26）：yuancc 无 WS 连接也能让云端看到
    「这台电脑在干活」。独立线程 + 短超时 + 失败静默，绝不阻塞 CC。
    桥接调用（CLAUDE_CODE_BRIDGE=1）跳过——其活动已由 Agent 经 WS 上报，防重复。
    只传元数据（状态/工具名），绝不传命令内容。"""
    if os.getenv("CLAUDE_CODE_BRIDGE", "0") == "1":
        return
    mapping = _HOOK_TO_STATE.get(hook_event)
    if not mapping:
        return
    state, with_tool = mapping
    try:
        from utils.data_path import root_path
        import threading
        import urllib.request

        ident_path = os.path.join(root_path(), "data", "agent_identity.json")
        if not os.path.isfile(ident_path):
            return
        with open(ident_path, "r", encoding="utf-8") as f:
            identity = json.load(f)
        server_url = (identity.get("server_url") or "").replace("wss://", "https://") \
            .replace("ws://", "http://").rstrip("/")
        agent_id = str(identity.get("agent_id") or "")
        secret = str(identity.get("agent_secret") or "")
        if not server_url or not agent_id or not secret:
            return
        body = json.dumps({
            "state": state,
            "tool": str(tool_name)[:64] if with_tool else "",
        }, ensure_ascii=False).encode("utf-8")

        def _post():
            try:
                req = urllib.request.Request(f"{server_url}/api/v1/agent/activity",
                                             data=body, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("X-Agent-Id", agent_id)
                req.add_header("X-Agent-Secret", secret)
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass  # 上报失败静默（观测是锦上添花）

        threading.Thread(target=_post, daemon=True).start()
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 无法解析则放行（钩子不应成为故障点）

    hook_event = payload.get("hook_event_name", "")
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    # 非桥接（用户交互会话）：不拦截，但桌宠联动 + 云端活动上报照常
    if os.getenv("CLAUDE_CODE_BRIDGE", "0") != "1":
        _emit_pet(hook_event, tool_name)
        _report_activity(hook_event, tool_name)
        sys.exit(0)

    _emit_pet(hook_event, tool_name)

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
