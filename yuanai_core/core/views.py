"""视图滤波 — 每个 Agent 只看到自己该看的那部分消息（纯函数，云边共用）

群聊消息流按信封（sender/recipient/turn/type）裁剪/重渲染：
- 自己的发言原样
- 别人对我说（recipient == 我）→ 完整 + 【sender】前缀
- 别人之间的对话 → 摘要（首 N 字）
- tool_result → 截断 + 标注
- 用户定向别人的消息 → 摘要（与我无关）

信封取值优先级：envelopes[i] > dict 内字段 > content META > 空。
全空信封（旧数据/旧前端）→ 退化为「仅剥 META 的原文」（= 历史行为直通）。
"""
from typing import Dict, List, Optional

from yuanai_core.core.message import Envelope, split_meta, _S_KEY

# 与 frontend/src/config/agents.ts AGENT_CONFIG 对偶
AGENT_LABELS = {
    "orchestrator": "小元AI",
    "local": "小元AI · 本机",
    "analysis": "数据分析 Agent",
    "collection": "数据采集 Agent",
    "automation": "自动化 Agent",
    "claude": "Claude Code",
    "planet": "知识星球",
    "user": "用户",
}

SUMMARY_CHARS = 120
TOOL_RESULT_CHARS = 400


def render_label(sender: str) -> str:
    """【xx Agent】展示前缀；未知 sender → ''"""
    if not sender:
        return ""
    label = AGENT_LABELS.get(sender)
    return f"【{label}】" if label else ""


def _resolve_env(item: Dict, envelopes: Optional[List[dict]], i: int) -> Envelope:
    """信封取值优先级：envelopes[i] > dict 内字段 > content META > 空（逐字段补缺）

    注意按「等于默认值」补缺而非 falsy 判断——type 默认 "chat"、turn 默认 0
    都是合法默认，但 "chat" 是 truthy，用 or 会把 dict 里的真实 type 吞掉。
    """
    from yuanai_core.core.message import ENVELOPE_FIELDS
    DEFAULTS = {"sender": "", "recipient": "", "turn": 0, "type": "chat"}
    env = Envelope()
    if isinstance(envelopes, list) and i < len(envelopes) and isinstance(envelopes[i], dict):
        env = Envelope.from_any(envelopes[i])
    env2 = Envelope.from_any(item)
    kwargs = {}
    for k in ENVELOPE_FIELDS:
        v1, v2 = getattr(env, k), getattr(env2, k)
        kwargs[k] = v2 if v1 == DEFAULTS[k] else v1
    meta, _ = split_meta(item.get("content") or "")
    if meta.get(_S_KEY):
        env3 = Envelope.from_meta(meta)
        for k in ENVELOPE_FIELDS:
            if kwargs[k] == DEFAULTS[k] and getattr(env3, k) != DEFAULTS[k]:
                kwargs[k] = getattr(env3, k)
    return Envelope(**kwargs)


def _clip(text: str, limit: int) -> str:
    t = str(text or "")
    return t if len(t) <= limit else t[:limit]


def view_for(agent: str, messages: List[dict], *,
             self_senders: Optional[set] = None,
             envelopes: Optional[List[dict]] = None,
             summary_chars: int = SUMMARY_CHARS) -> List[dict]:
    """agent 视角的消息列表（已解码信封、已裁剪/标注）。

    输出项 = {"role","content","tool_calls"?,"tool_call_id"?}，可直接喂 LangChain /
    react-agent。全空信封（旧数据）→ 退化为仅剥 META 的原文。
    """
    self_senders = self_senders or set()
    self_set = {agent} | self_senders
    # 信封证据 = envelopes 参数 或 dict 内字段（recipient/turn/type 是新协议标记）。
    # 旧数据的 META-s 不算证据：P3 后端先行期旧前端仍发旧格式，若把 s 当信封
    # 就会双前缀（旧前端已在 content 里写过【xx】）。旧数据走退化直通。
    any_env = bool(envelopes) or any(
        isinstance(m, dict) and (m.get("sender") or m.get("recipient")
                                 or m.get("type") or m.get("turn"))
        for m in messages)
    if not any_env:
        # 全空信封：退化直通（仅剥 META），与历史行为一致
        out = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "")
            content = split_meta(m.get("content") or "")[1]
            item = {"role": role, "content": content}
            if m.get("tool_calls"):
                item["tool_calls"] = m["tool_calls"]
            if m.get("tool_call_id"):
                item["tool_call_id"] = m["tool_call_id"]
            out.append(item)
        return out

    out = []
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            continue
        role = m.get("role", "")
        content = split_meta(m.get("content") or "")[1]
        env = _resolve_env(m, envelopes, i)
        item: Dict = {"role": role, "content": content}
        if m.get("tool_calls"):
            item["tool_calls"] = m["tool_calls"]
        if m.get("tool_call_id"):
            item["tool_call_id"] = m["tool_call_id"]

        if role == "system":
            out.append(item)  # 系统提示词原样透传（不能进摘要/前缀规则）
            continue

        if role == "user":
            if not env.recipient or env.recipient == agent:
                pass  # 用户广播或对我说 → 原样
            else:
                # 用户定向别人 → 摘要（与我无关）
                label = AGENT_LABELS.get(env.recipient, env.recipient)
                item["content"] = (f"【用户@{label}】" + _clip(content, summary_chars))
            out.append(item)
            continue

        # assistant 侧
        if env.type == "tool_result":
            label = render_label(env.sender) or "【工具】"
            item["content"] = f"{label}工具结果：" + _clip(content, TOOL_RESULT_CHARS)
        elif env.sender in self_set:
            pass  # 自己的发言 → 原样
        elif env.recipient == agent:
            item["content"] = render_label(env.sender) + content
        elif env.type == "summary":
            pass  # 显式 summary 类型 → 原样
        else:
            # 别人之间的对话 → 摘要
            clipped = _clip(content, summary_chars)
            tail = "……" if len(content) > summary_chars else ""
            item["content"] = render_label(env.sender) + clipped + tail
        out.append(item)
    return out


def compose_target_prompt(view: List[dict], max_context: int = 6) -> str:
    """@定向/子 Agent 专用：最新 user 正文 + 定向上下文块（工具结构行不进 prompt）。

    view 为 view_for(target, ...) 的输出；取最后一条 user 消息为任务正文，
    其前最多 max_context 条作为上下文（跳过 tool/tool_call_id 结构行）。
    """
    text = ""
    context: List[str] = []
    for item in reversed(view):
        if not isinstance(item, dict):
            continue
        role = item.get("role", "")
        content = str(item.get("content") or "").strip()
        if role == "user" and not text and content:
            text = content
            continue
        if role in ("assistant", "user") and content and not item.get("tool_calls"):
            context.append(content)
            if len(context) >= max_context:
                break
    context.reverse()
    if not context:
        return text
    return "最近的对话上下文：\n" + "\n".join(context) + "\n\n用户需求：" + text
