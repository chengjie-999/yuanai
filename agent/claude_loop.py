"""P0 审批流自建：anthropic SDK 直连 agent loop（claude -p 子进程的替代实现）

定位（B 路线约束）：**只补 can_use_tool 缺口，不复刻全功能**——
工具面 = bridge_policy 白名单（Read/Write/Edit/Glob/Grep + Bash 经 classify
allow/deny/review），审批流走 approval 事件 + decision 队列（超时默认 deny
fail-closed）。联网被禁维持现状（SDK 不注册 WebFetch/WebSearch）。

与 claude_bridge 的关系：本模块是独立候选实现（P0a）；接入主流程
（--sdk 开关切换 + 审批 decision 云端回传）在 P0b 完成。

凭证优先级：ANTHROPIC_API_KEY > ANTHROPIC_AUTH_TOKEN（OAuth Bearer）>
~/.claude/.credentials.json 的 apiKey。
"""

import asyncio
import glob as _glob
import json
import logging
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

from utils.data_path import root_path
from agent.bridge_policy import classify, explain, PROJECT_ROOT as POLICY_ROOT

logger = logging.getLogger("claude_loop")

MAX_TOOL_OUTPUT = 2000      # 工具结果回传模型的最大字符数（对齐 claude_bridge）
MAX_READ_LINES = 2000       # Read 截断行数
APPROVAL_TIMEOUT = 120      # 审批等待秒数；超时默认 deny（fail-closed）
MAX_TOKENS_DEFAULT = 64000  # 流式请求给足输出空间（含 thinking）
MAX_ITERATIONS = 60         # 单次会话工具轮数上限（防死循环）
# 模型可配（env CLAUDE_BRIDGE_MODEL）；默认 Opus 4.8（最新 Opus 档）
SDK_MODEL = os.getenv("CLAUDE_BRIDGE_MODEL", "claude-opus-4-8")
# thinking 参数可关（env CLAUDE_BRIDGE_THINKING=0）：第三方网关（deepseek 系等）
# 多不识别 Anthropic 的 thinking 字段，硬发会 400 → 关闭后网关侧自带的思维链
# 仍会以 reasoning 流回传
SDK_THINKING = os.getenv("CLAUDE_BRIDGE_THINKING", "1") == "1"

# ——— SDK tool 定义 ———
# bash 与 text editor 是 Anthropic 内置工具（schema-less，type+name 声明即可，
# 不能自定义同名带 schema 工具）；Read/Glob/Grep 为自定义（bridge_policy 白名单照搬）
_SDK_TOOLS = [
    {"type": "bash_20250124", "name": "bash"},
    {"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"},
    {"name": "Read", "description": "读取仓库内文本文件（行数截断 2000）",
     "input_schema": {"type": "object", "properties": {
         "file_path": {"type": "string", "description": "文件路径（仓库内）"},
         "offset": {"type": "integer"}, "limit": {"type": "integer"}},
         "required": ["file_path"]}},
    {"name": "Write", "description": "写入/覆盖仓库内文件（文本编辑器工具的子集，两者选一即可）",
     "input_schema": {"type": "object", "properties": {
         "file_path": {"type": "string"}, "content": {"type": "string"}},
         "required": ["file_path", "content"]}},
    {"name": "Glob", "description": "按模式查找仓库内文件（如 **/*.py）",
     "input_schema": {"type": "object", "properties": {
         "pattern": {"type": "string"}}, "required": ["pattern"]}},
    {"name": "Grep", "description": "在仓库内按正则搜索文件内容（逐文件扫描，限前 50 个命中）",
     "input_schema": {"type": "object", "properties": {
         "pattern": {"type": "string"}, "glob": {"type": "string"}},
         "required": ["pattern"]}},
]

_IGNORE_DIRS = {".git", "node_modules", "venv", "dist", "build", "__pycache__",
                ".claude", "data", ".idea", ".vscode"}


# ==================== 凭证 ====================

def load_credentials() -> Optional[str]:
    """anthropic 凭证：env > ~/.claude/.credentials.json；失败返回 None"""
    env = (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or "").strip()
    if env:
        return env
    try:
        cred_path = Path.home() / ".claude" / ".credentials.json"
        if cred_path.is_file():
            data = json.loads(cred_path.read_text("utf-8"))
            if isinstance(data, dict):
                api_key = data.get("apiKey") or ""
                if api_key:
                    return api_key
                # OAuth 模式：anthropic SDK 需 bearer token 换取，暂不支持（提示走 env）
                logger.warning(".credentials.json 为 OAuth 凭证，SDK loop 暂不支持；"
                               "请设置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN")
    except Exception as e:
        logger.warning("读取 ~/.claude/.credentials.json 失败: %s", e)
    return None


# ==================== 工具执行器 ====================

def _within_root(path: Path) -> bool:
    """仓库内校验（与 bridge_policy 同口径）"""
    p = str(path.resolve()).replace("\\", "/").rstrip("/")
    r = str(POLICY_ROOT).replace("\\", "/").rstrip("/")
    return p.casefold() == r.casefold() or p.casefold().startswith(r.casefold() + "/")


def _resolve_path(tool_input: dict) -> Optional[Path]:
    raw = tool_input.get("file_path") or tool_input.get("path") or ""
    if not raw:
        return None
    p = Path(str(raw))
    if not p.is_absolute():
        p = POLICY_ROOT / p
    return p


def _exec_read(tool_input: dict) -> str:
    p = _resolve_path(tool_input)
    if p is None or not _within_root(p):
        return "[拒绝] 读取路径超出项目仓库"
    if not p.is_file():
        return f"[错误] 文件不存在: {p}"
    try:
        text = p.read_text("utf-8", errors="replace")
    except OSError as e:
        return f"[错误] 读取失败: {e}"
    lines = text.splitlines()
    offset = max(int(tool_input.get("offset") or 0), 0)
    limit = int(tool_input.get("limit") or MAX_READ_LINES)
    sliced = lines[offset:offset + limit]
    out = "\n".join(sliced)
    if offset + limit < len(lines):
        out += f"\n...（共 {len(lines)} 行，已截断）"
    return out or "(空文件)"


def _exec_write(tool_input: dict) -> str:
    p = _resolve_path(tool_input)
    if p is None or not _within_root(p):
        return "[拒绝] 写入路径超出项目仓库"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(tool_input.get("content", "")), encoding="utf-8")
        return f"已写入 {p}（{len(str(tool_input.get('content', '')))} 字符）"
    except OSError as e:
        return f"[错误] 写入失败: {e}"


def _exec_edit(tool_input: dict) -> str:
    p = _resolve_path(tool_input)
    if p is None or not _within_root(p):
        return "[拒绝] 写入路径超出项目仓库"
    if not p.is_file():
        return f"[错误] 文件不存在: {p}"
    old = str(tool_input.get("old_string", ""))
    new = str(tool_input.get("new_string", ""))
    replace_all = bool(tool_input.get("replace_all"))
    try:
        text = p.read_text("utf-8")
    except OSError as e:
        return f"[错误] 读取失败: {e}"
    if replace_all:
        if old not in text:
            return "[错误] old_string 未在文件中出现"
        text = text.replace(old, new)
    else:
        if text.count(old) != 1:
            return f"[错误] old_string 出现 {text.count(old)} 次（必须恰好 1 次，或设 replace_all）"
        text = text.replace(old, new, 1)
    try:
        p.write_text(text, encoding="utf-8")
        return f"已编辑 {p}"
    except OSError as e:
        return f"[错误] 写入失败: {e}"


def _exec_glob(tool_input: dict) -> str:
    pattern = str(tool_input.get("pattern", ""))
    if not pattern or ".." in pattern:
        return "[拒绝] 非法 glob 模式"
    hits = []
    for p in _glob.glob(str(POLICY_ROOT / pattern), recursive=True):
        rel = Path(p).relative_to(POLICY_ROOT)
        if any(part in _IGNORE_DIRS for part in rel.parts):
            continue
        hits.append(str(rel))
    if not hits:
        return "(无匹配文件)"
    shown = hits[:100]
    out = "\n".join(shown)
    if len(hits) > 100:
        out += f"\n...（共 {len(hits)} 个，已截断）"
    return out


def _exec_grep(tool_input: dict) -> str:
    pattern = str(tool_input.get("pattern", ""))
    if not pattern:
        return "[拒绝] 空搜索模式"
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"[错误] 正则无效: {e}"
    gpat = str(tool_input.get("glob") or "**/*")
    results: List[str] = []
    scanned = 0
    for p in _glob.glob(str(POLICY_ROOT / gpat), recursive=True):
        path = Path(p)
        if not path.is_file() or any(part in _IGNORE_DIRS for part in path.relative_to(POLICY_ROOT).parts):
            continue
        if path.stat().st_size > 512 * 1024:
            continue  # 跳过超大文件
        scanned += 1
        if scanned > 500:
            break
        try:
            text = path.read_text("utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                rel = path.relative_to(POLICY_ROOT)
                results.append(f"{rel}:{i}: {line.strip()[:200]}")
                if len(results) >= 50:
                    return "\n".join(results) + "\n...（已截断）"
    return "\n".join(results) if results else "(无匹配)"


def _exec_bash(tool_input: dict) -> str:
    """SDK 内置 bash：input 为 {"command": str} 或 {"restart": true}；
    执行前必须经 classify==allow（调用方保证）；120s 超时；输出截断"""
    if str(tool_input.get("restart")) in ("true", "True", "1"):
        return "[错误] 会话重启请求不支持（无状态执行器）"
    command = str(tool_input.get("command", ""))
    if not command:
        return "[错误] 空命令"
    try:
        proc = subprocess.run(
            command, shell=True, cwd=str(POLICY_ROOT), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "[错误] 命令执行超时（120s），已终止"
    except OSError as e:
        return f"[错误] 命令执行失败: {e}"
    out = (proc.stdout or "") + (f"\n[stderr]\n{proc.stderr}" if proc.stderr else "")
    out = out.strip() or "(无输出)"
    if len(out) > MAX_TOOL_OUTPUT * 10:
        out = out[:MAX_TOOL_OUTPUT * 10] + "\n...(输出过长已截断)"
    return f"(exit={proc.returncode})\n{out}"


def _exec_text_editor(tool_input: dict) -> str:
    """SDK 内置 text editor：command ∈ view/create/str_replace/insert"""
    cmd = str(tool_input.get("command", ""))
    path_raw = str(tool_input.get("path", ""))
    if cmd == "view":
        return _exec_read({"file_path": path_raw,
                           "offset": tool_input.get("view_range", [None, None])[0]
                           if isinstance(tool_input.get("view_range"), list) else None})
    if cmd == "create":
        return _exec_write({"file_path": path_raw, "content": tool_input.get("file_text", "")})
    if cmd == "str_replace":
        return _exec_edit({"file_path": path_raw,
                           "old_string": tool_input.get("old_str", ""),
                           "new_string": tool_input.get("new_str", ""),
                           "replace_all": False})
    if cmd == "insert":
        p = _resolve_path({"file_path": path_raw})
        if p is None or not _within_root(p):
            return "[拒绝] 写入路径超出项目仓库"
        if not p.is_file():
            return f"[错误] 文件不存在: {p}"
        try:
            lines = p.read_text("utf-8").splitlines()
            at = int(tool_input.get("insert_line", 0))
            at = max(0, min(at, len(lines)))
            lines.insert(at, str(tool_input.get("insert_text", "")))
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return f"已插入到 {p} 第 {at} 行后"
        except (OSError, ValueError) as e:
            return f"[错误] 插入失败: {e}"
    return f"[错误] 未知文本编辑器命令: {cmd}"


_EXECUTORS = {
    "Read": _exec_read, "Write": _exec_write,
    "Glob": _exec_glob, "Grep": _exec_grep,
    "bash": _exec_bash,
    "str_replace_based_edit_tool": _exec_text_editor,
}


def _audit_tool(name: str, verdict: str, tool_input: dict):
    """SDK 模式工具调用审计（与 CLI 钩子 claude_guard 同文件同格式——
    CLI 走 hooks 审计，SDK 执行器此前无审计落盘，2026-10-19 补齐）"""
    try:
        import time as _time
        from utils.data_path import root_path
        log = os.path.join(root_path(), "data", "logs", "claude_audit.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        summary = json.dumps(tool_input, ensure_ascii=False)[:200]
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{_time.strftime('%Y-%m-%d %H:%M:%S')} | SDK | {name} | {verdict} | {summary}\n")
    except Exception:
        pass


def execute_tool(name: str, tool_input: dict) -> str:
    """工具执行入口（含安全分类；deny 直接拒绝不执行）"""
    verdict = classify(name, tool_input)
    _audit_tool(name, verdict, tool_input)
    if verdict == "deny":
        return f"[拒绝] {explain(name, tool_input) or '被安全策略拒绝'}"
    fn = _EXECUTORS.get(name)
    return fn(tool_input) if fn else "[错误] 未注册的工具"


# ==================== SDK 流式 loop ====================



async def run_sdk_loop(
        messages: List[Dict],
        *,
        api_key: Optional[str] = None,
        system: str = "",
        model: str = SDK_MODEL,
        max_tokens: int = MAX_TOKENS_DEFAULT,
        on_approval=None,
) -> AsyncGenerator[Dict, None]:
    """anthropic SDK 直连流式循环。产出事件 dict：
    {type: token|reasoning|tool_start|tool_end|approval|done|error, data: ...}

    on_approval(decision_id, tool_name, command) → 可等待的裁决（同步函数内用
    _run_async 包装，返回 "approve"|"deny"）；返回 None/超时 → deny（fail-closed）。
    与 claude_bridge 的事件映射对齐：token/reasoning/tool_start/tool_end 数据形状一致。
    api_key=None 时 SDK 自动解析凭证（ANTHROPIC_API_KEY/AUTH_TOKEN/ant 配置）。
    """
    try:
        import anthropic
    except ImportError:
        # 2026-10-19 修复：import 在 try 外——SDK 依赖缺失时 ImportError 直接冒到
        # WS 层不降级；改为产出 error 事件（桥接层见 error 且无产出 → 自动降级 CLI）
        logger.warning("anthropic SDK 未安装（pip install anthropic），SDK 模式不可用")
        yield {"type": "error", "data": "anthropic SDK 未安装，已降级 CLI 模式"}
        return

    client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()
    pending_messages = [m for m in messages]
    iteration = 0
    final_text = ""

    try:
        while iteration < MAX_ITERATIONS:
            iteration += 1
            stream = await client.messages.create(
                model=model, max_tokens=max_tokens,
                # 自适应思考（Opus 4.8 系唯一开启方式）+ 摘要可见（reasoning 流给用户）；
                # 第三方网关不识别时用 CLAUDE_BRIDGE_THINKING=0 关闭
                **({"thinking": {"type": "adaptive", "display": "summarized"}} if SDK_THINKING else {}),
                system=system or None,
                messages=pending_messages,
                tools=_SDK_TOOLS,
                stream=True,
            )

            content_blocks: Dict[str, Dict] = {}   # idx → {name, input, id}
            text_parts: List[str] = []
            current_block_idx = -1

            async for event in stream:
                kind = getattr(event, "type", "")
                if kind == "content_block_start":
                    blk = event.content_block
                    current_block_idx = getattr(event, "index", -1)
                    if getattr(blk, "type", "") == "tool_use":
                        content_blocks[str(current_block_idx)] = {
                            "name": blk.name, "input": "", "id": blk.id}
                        yield {"type": "tool_start",
                               "data": {"name": blk.name, "sender": "claude"}}
                elif kind == "content_block_delta":
                    delta = event.delta
                    d_type = getattr(delta, "type", "")
                    if d_type == "text_delta" and getattr(delta, "text", ""):
                        text_parts.append(delta.text)
                        yield {"type": "token", "data": delta.text}
                    elif d_type == "thinking_delta" and getattr(delta, "thinking", ""):
                        yield {"type": "reasoning", "data": delta.thinking}
                    elif d_type == "input_json_delta" and getattr(delta, "partial_json", ""):
                        blk = content_blocks.get(str(current_block_idx))
                        if blk:
                            blk["input"] += delta.partial_json
                elif kind == "message_stop":
                    break

            # 组装 assistant 消息（回复模型）
            assistant_content = []
            block_index = 0
            for blk in content_blocks.values():
                assistant_content.append({"type": "text", "text": ""})
                assistant_content.append({
                    "type": "tool_use", "id": blk["id"], "name": blk["name"],
                    "input": _safe_json(blk["input"]),
                })
                block_index += 1
            if text_parts:
                assistant_content.insert(0, {"type": "text", "text": "".join(text_parts)})

            if not content_blocks:
                final_text = "".join(text_parts)
                yield {"type": "done", "data": {"display_content": final_text, "reasoning_content": ""}}
                return

            # 执行工具（审批/拒绝）
            tool_results = []
            for blk in content_blocks.values():
                name = blk["name"]
                tool_input = _safe_json(blk["input"])
                verdict = classify(name, tool_input)
                output = ""
                if verdict == "review":
                    decision_id = uuid.uuid4().hex[:12]
                    yield {"type": "approval", "data": {
                        "decision_id": decision_id, "tool_name": name,
                        "command": str(tool_input.get("command", "")),
                        "reason": explain(name, tool_input)}}
                    decision = await _wait_decision(on_approval, decision_id, name,
                                                    str(tool_input.get("command", "")))
                    _audit_tool(name, "review→approve" if decision == "approve" else
                                f"review→denied({'超时' if decision is None else '用户拒绝'})", tool_input)
                    if decision == "approve":
                        output = execute_tool(name, tool_input)
                    else:
                        output = f"[拒绝] 审批未通过（{'超时' if decision is None else '用户拒绝'}），命令未执行"
                elif verdict == "deny":
                    output = f"[拒绝] {explain(name, tool_input) or '被安全策略拒绝'}"
                else:
                    output = execute_tool(name, tool_input)
                if len(output) > MAX_TOOL_OUTPUT:
                    output = output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)"
                tool_results.append((name, output))
                # 参数：SDK 流式累积的是 JSON 字符串 → 解析成 dict（schemas 再统一序列化）
                _args_raw = blk.get("input", "")
                if isinstance(_args_raw, str) and _args_raw.strip().startswith(("{", "[")):
                    try:
                        _args_raw = json.loads(_args_raw)
                    except Exception:
                        pass
                yield {"type": "tool_end", "data": {"name": name, "output": output,
                                                    "sender": "claude",
                                                    "args": _args_raw or None}}

            # 追加 assistant(tool_use) + user(tool_result) 继续下一轮
            assistant_content = [c for c in assistant_content if c.get("type") == "tool_use"]
            if text_parts:
                assistant_content.insert(0, {"type": "text", "text": "".join(text_parts)})
            pending_messages.append({"role": "assistant", "content": assistant_content})
            pending_messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": blk["id"], "content": out}
                for (name, out), blk in zip(tool_results, content_blocks.values())
            ]})

        yield {"type": "error", "data": f"达到最大迭代轮数（{MAX_ITERATIONS}），已终止"}
    except Exception as e:
        logger.warning("SDK loop 异常: %s", e)
        yield {"type": "error", "data": f"Claude Code 执行失败: {str(e)[:500]}"}


def _safe_json(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


async def _wait_decision(on_approval, decision_id: str, tool_name: str, command: str):
    """等待 on_approval 裁决；None 回调 / 异常 / 超时 → None（调用方转 deny）"""
    if not on_approval:
        return None
    try:
        decision = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                None, lambda: on_approval(decision_id, tool_name, command)),
            timeout=APPROVAL_TIMEOUT)
        return decision if decision in ("approve", "deny") else None
    except asyncio.TimeoutError:
        logger.warning("审批超时（%ss），默认 deny: %s %s", APPROVAL_TIMEOUT, tool_name, command[:80])
        return None
    except Exception:
        return None
