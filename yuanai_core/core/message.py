"""消息信封编解码 — 多智能体群聊身份元数据（零依赖纯函数，云边共用）

信封（Envelope）= sender / recipient / turn / type，由编排代码填写，模型碰不到；
展示层的【xx】前缀只用于渲染给人看，与模型上下文解耦（视图滤波在 views.py）。

与前端 helpers.tsx encodeMsg 对偶：
- 既有短键 s/t/r/p（sender/toolCalls/reasoning/pageLink）不得改动
- 新增短键 rp/tn/ty（recipient/turn/type），避开 t/r/p

落库格式：\x00META\x00{json}\x00正文（无信封且无附加 meta 时不加前缀）。
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

META_PREFIX = "\x00META\x00"

# 短键 ↔ 信封字段映射（s 复用前端既有键；rp/tn/ty 为新增，避开 t/r/p）
_S_KEY = "s"          # sender
_RP_KEY = "rp"        # recipient
_TN_KEY = "tn"        # turn
_TY_KEY = "ty"        # type
ENVELOPE_FIELDS = ("sender", "recipient", "turn", "type")

MESSAGE_TYPES = ("chat", "tool_call", "tool_result", "summary", "note")


@dataclass(frozen=True)
class Envelope:
    """消息信封：谁说的 / 说给谁 / 第几轮 / 什么类型"""
    sender: str = ""          # 说话人：user/orchestrator/local/analysis/collection/automation/claude/planet
    recipient: str = ""       # "" = 广播；否则定向（@agent / 对某人发言）
    turn: int = 0             # 1-based 轮次（第 n 条 user 消息）
    type: str = "chat"        # chat | tool_call | tool_result | summary | note

    @classmethod
    def from_meta(cls, meta: Dict[str, Any]) -> "Envelope":
        """短键 dict → 信封（容错：缺失/类型错取默认）"""
        def _s(v): return str(v) if v else ""
        def _i(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0
        return cls(sender=_s(meta.get(_S_KEY)),
                   recipient=_s(meta.get(_RP_KEY)),
                   turn=_i(meta.get(_TN_KEY)),
                   type=_s(meta.get(_TY_KEY)) or "chat")

    @classmethod
    def from_any(cls, item: Dict[str, Any]) -> "Envelope":
        """字段名/短键两形态通用解析（字段名优先，容错坏值）"""
        if not isinstance(item, dict):
            return cls()

        def _i(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0

        return cls(
            sender=str(item.get("sender") or item.get(_S_KEY) or ""),
            recipient=str(item.get("recipient") or item.get(_RP_KEY) or ""),
            turn=_i(item.get("turn") or item.get(_TN_KEY) or 0),
            type=str(item.get("type") or item.get(_TY_KEY) or "chat"),
        )

    def to_meta(self) -> Dict[str, Any]:
        """短键 dict，只含非默认值"""
        out: Dict[str, Any] = {}
        if self.sender:
            out[_S_KEY] = self.sender
        if self.recipient:
            out[_RP_KEY] = self.recipient
        if self.turn:
            out[_TN_KEY] = self.turn
        if self.type and self.type != "chat":
            out[_TY_KEY] = self.type
        return out

    def is_default(self) -> bool:
        return not (self.sender or self.recipient or self.turn
                    or (self.type and self.type != "chat"))


def split_meta(content: str) -> Tuple[Dict[str, Any], str]:
    """拆 META 前缀 → (meta, 正文)；无前缀或坏 JSON → ({}, 原文)"""
    if not isinstance(content, str) or not content.startswith(META_PREFIX):
        return {}, content or ""
    end = content.find("\x00", len(META_PREFIX))
    if end == -1:
        return {}, content
    try:
        meta = json.loads(content[len(META_PREFIX):end])
    except (ValueError, TypeError):
        return {}, content
    return (meta if isinstance(meta, dict) else {}), content[end + 1:]


def decode(content: str) -> Tuple[Envelope, str]:
    """content → (Envelope, 正文)"""
    meta, body = split_meta(content)
    return Envelope.from_meta(meta), body


def encode(body: str, env: Optional[Envelope] = None,
           extra_meta: Optional[Dict[str, Any]] = None) -> str:
    """正文 + 信封（+附加 meta 如 t/r/p）→ 落库 content；全默认 → 不加前缀"""
    meta: Dict[str, Any] = {}
    if extra_meta:
        meta.update({k: v for k, v in extra_meta.items() if v})
    if env is not None:
        meta.update(env.to_meta())
    if not meta:
        return body
    return META_PREFIX + json.dumps(meta, ensure_ascii=False) + "\x00" + body


def strip(content: str) -> str:
    """剥 META 前缀返回正文"""
    return split_meta(content)[1]


def text_of(content) -> str:
    """消息 content 归一化为纯文本：list（图片/多块消息）→ 拼接 text 块；
    其他类型 → str。调用方无需再判断类型，直接 .strip() 安全。"""
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and isinstance(c.get("text"), str))
    return content if isinstance(content, str) else str(content or "")


def assign_turns(messages: List[dict]) -> List[dict]:
    """落库/补齐兜底：按序给消息赋 turn（user 自增、assistant 继承），就地返回"""
    turn = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("role") == "user":
            turn += 1
        m["turn"] = turn
    return messages


def envelope_from_message(item: Dict[str, Any]) -> Envelope:
    """从消息 dict 解析信封：字段名/短键 > content META > 默认"""
    env = Envelope.from_any(item)
    meta, _ = split_meta(item.get("content") or "")
    if not env.sender and meta.get(_S_KEY):
        env = Envelope.from_meta(meta)
    return env
