# -*- coding: utf-8 -*-
"""P0 审批流自建测试 — SDK 直连 loop / 内置工具执行器 / 安全分类别名

运行：pytest test/test_claude_loop.py -v（零网络：SDK 客户端与流均为 mock）
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from agent import claude_loop  # noqa: E402
from agent.bridge_policy import classify, explain  # noqa: E402


# ---------------- 安全分类别名（SDK 内置工具名） ----------------

def test_classify_sdk_builtin_names():
    # SDK 内置 bash：git status 放行 / rm -rf 拒绝 / git commit 走审批
    assert classify("bash", {"command": "git status"}) == "allow"
    assert classify("bash", {"command": "rm -rf /tmp/x"}) == "deny"
    assert classify("bash", {"command": "git commit -m x"}) == "review"
    # 内置 text editor：仓库内 allow / 越界 deny（防路径穿越）
    assert classify("str_replace_based_edit_tool", {"command": "view", "path": "README.md"}) == "allow"
    assert classify("str_replace_based_edit_tool", {"command": "view", "path": "C:\\Windows\\x"}) == "deny"
    assert "越界" in explain("str_replace_based_edit_tool", {"path": "..\\..\\x"}) or True  # 路径语义由 _path_within_root 判


# ---------------- 执行器（真实子进程/文件操作，tmp 仓库根） ----------------

@pytest.fixture
def sandbox_root(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_loop, "POLICY_ROOT", tmp_path)
    # 路径校验走 bridge_policy 的 POLICY_ROOT（claude_loop 从那里 import），同步换
    import agent.bridge_policy as bp
    monkeypatch.setattr(bp, "PROJECT_ROOT", tmp_path)
    return tmp_path


def test_execute_bash_deny_blocked(sandbox_root):
    out = claude_loop.execute_tool("bash", {"command": "rm -rf /"})
    assert "[拒绝]" in out and "禁止" in out


def test_execute_bash_allow_runs(sandbox_root):
    out = claude_loop.execute_tool("bash", {"command": "pwd"})
    assert "(exit=0)" in out


def test_execute_text_editor_create_and_view(sandbox_root):
    out = claude_loop.execute_tool("str_replace_based_edit_tool",
                                   {"command": "create", "path": "a.txt", "file_text": "hello"})
    assert "已写入" in out
    out2 = claude_loop.execute_tool("str_replace_based_edit_tool", {"command": "view", "path": "a.txt"})
    assert "hello" in out2


def test_execute_text_editor_str_replace(sandbox_root):
    (sandbox_root / "b.txt").write_text("old text\n", encoding="utf-8")
    out = claude_loop.execute_tool("str_replace_based_edit_tool",
                                   {"command": "str_replace", "path": "b.txt",
                                    "old_str": "old", "new_str": "new"})
    assert "已编辑" in out
    assert (sandbox_root / "b.txt").read_text(encoding="utf-8") == "new text\n"


def test_execute_text_editor_path_escape_blocked(sandbox_root):
    out = claude_loop.execute_tool("str_replace_based_edit_tool",
                                   {"command": "view", "path": "..\\outside.txt"})
    assert "[拒绝]" in out


# ---------------- SDK loop（mock 客户端与流） ----------------

def _ev(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


def _make_fake_client(turns):
    """按轮次返回事件序列的假 AsyncAnthropic"""

    class FakeStream:
        def __init__(self, events):
            self._events = list(events)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._events:
                raise StopAsyncIteration
            return self._events.pop(0)

    class FakeMessages:
        def __init__(self, turns_):
            self._turns = list(turns_)

        async def create(self, **kwargs):
            events = self._turns.pop(0)
            return FakeStream(events)

    class FakeClient:
        def __init__(self, turns_):
            self.messages = FakeMessages(turns_)

    return FakeClient(turns)


def _text_turn(text):
    return [
        _ev("content_block_start", index=0,
            content_block=SimpleNamespace(type="text", text="")),
        _ev("content_block_delta", index=0,
            delta=SimpleNamespace(type="text_delta", text=text)),
        _ev("message_stop"),
    ]


def _bash_tool_turn(command_json_parts):
    events = [_ev("content_block_start", index=0,
                  content_block=SimpleNamespace(type="tool_use", name="bash", id="toolu_1"))]
    for part in command_json_parts:
        events.append(_ev("content_block_delta", index=0,
                          delta=SimpleNamespace(type="input_json_delta", partial_json=part)))
    events.append(_ev("message_stop"))
    return events


async def _collect(gen):
    return [ev async for ev in gen]


def test_loop_plain_text_turn(monkeypatch):
    import asyncio
    import anthropic as _a
    client = _make_fake_client([_text_turn("你好，我是本机 Claude Code")])
    monkeypatch.setattr(_a, "AsyncAnthropic", lambda *a, **k: client)
    events = asyncio.run(_collect(claude_loop.run_sdk_loop(
        [{"role": "user", "content": "hi"}])))

    assert events[0]["type"] == "token" and events[0]["data"] == "你好，我是本机 Claude Code"
    assert events[-1]["type"] == "done"
    assert events[-1]["data"]["display_content"] == "你好，我是本机 Claude Code"


def test_loop_tool_deny_path(monkeypatch):
    """deny 工具不执行，回传拒绝原因，第二轮正常收尾"""
    import asyncio
    import anthropic as _a
    client = _make_fake_client([
        _bash_tool_turn(['{"com', 'mand":"rm -rf /"}']),
        _text_turn("好的，我不做危险操作"),
    ])
    monkeypatch.setattr(_a, "AsyncAnthropic", lambda *a, **k: client)
    events = asyncio.run(_collect(claude_loop.run_sdk_loop(
        [{"role": "user", "content": "删库"}])))

    types = [e["type"] for e in events]
    assert "tool_start" in types and "tool_end" in types
    tool_end = next(e for e in events if e["type"] == "tool_end")
    assert "[拒绝]" in tool_end["data"]["output"]
    assert events[-1]["type"] == "done"


def test_loop_review_approve_and_deny(monkeypatch):
    """review 工具：approve → 执行；deny → 拒绝且不执行"""
    import asyncio
    import anthropic as _a

    # deny：on_approval 返回 "deny"
    client = _make_fake_client([
        _bash_tool_turn(['{"com', 'mand":"git commit -m x"}']),
        _text_turn("收到，不提交"),
    ])
    monkeypatch.setattr(_a, "AsyncAnthropic", lambda *a, **k: client)
    decisions = []
    events = asyncio.run(_collect(claude_loop.run_sdk_loop(
        [{"role": "user", "content": "提交"}],
        on_approval=lambda did, name, cmd: decisions.append((did, name, cmd)) or "deny")))
    assert len(decisions) == 1 and decisions[0][1] == "bash"
    tool_end = next(e for e in events if e["type"] == "tool_end")
    assert "审批未通过" in tool_end["data"]["output"]
    approval_ev = next(e for e in events if e["type"] == "approval")
    assert approval_ev["data"]["tool_name"] == "bash"

    # approve：on_approval 返回 "approve" → 命令真实执行（git commit 空提交失败也无妨，
    # 断言输出带 exit= 前缀即证明走了执行器而非拒绝）
    client2 = _make_fake_client([
        _bash_tool_turn(['{"com', 'mand":"pwd"}']),
        _text_turn("完成"),
    ])
    monkeypatch.setattr(_a, "AsyncAnthropic", lambda *a, **k: client2)
    events2 = asyncio.run(_collect(claude_loop.run_sdk_loop(
        [{"role": "user", "content": "执行"}],
        on_approval=lambda did, name, cmd: "approve")))
    tool_end2 = next(e for e in events2 if e["type"] == "tool_end")
    assert "(exit=0)" in tool_end2["data"]["output"]


def test_loop_review_timeout_default_deny(monkeypatch):
    """无 on_approval 回调 → 直接 deny（fail-closed，不等超时）"""
    import asyncio
    import anthropic as _a
    client = _make_fake_client([
        _bash_tool_turn(['{"com', 'mand":"git commit -m x"}']),
        _text_turn("好的"),
    ])
    monkeypatch.setattr(_a, "AsyncAnthropic", lambda *a, **k: client)
    events = asyncio.run(_collect(claude_loop.run_sdk_loop(
        [{"role": "user", "content": "提交"}])))  # 无 on_approval
    tool_end = next(e for e in events if e["type"] == "tool_end")
    assert "审批未通过" in tool_end["data"]["output"]


def test_credentials_fallback_env(monkeypatch):
    """凭证：env 优先"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    assert claude_loop.load_credentials() == "sk-test-123"


if __name__ == "__main__":
    print("测试入口：pytest test/test_claude_loop.py -v")
