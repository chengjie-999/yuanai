"""DSML 工具调用标记抑制（DeepSeek 流式怪癖，云边共用纯函数）

DeepSeek 模型在流式响应中发起工具调用时，会把调用以 DSML 标记文本写进
content 流（形如 `<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="search_web">…`，
全角竖线 U+FF5C，部分网关转 ASCII |）。消费层若原样透传 token，用户会在
聊天正文看到这段 XML。本模块在流式消费层统一剥除——真正的工具调用走
tool_calls 结构化字段，这里的文本只是重复品/噪音。

注意：langchain/LangGraph 解析层无法覆盖（DeepSeek 专用路径绕过 langchain、
create_react_agent 是黑盒），因此方案是「一个纯函数过滤器 + 各消费路径接线」。
"""

import re
from typing import Optional

# 标记正则：兼容全角 ｜ 与 ASCII |、可选空白、开闭标签、任意属性
# 实测形态：<｜｜DSML｜｜tool_calls> / <｜｜DSML｜｜invoke name="x"> / </｜｜DSML｜｜invoke>
_TAG_RE = re.compile(r"</?\s*[｜|]{2}\s*DSML\s*[｜|]{2}[^>]*>", re.IGNORECASE)

# 流式 chunk 边界保护：疑似标记前缀的最长长度（`<｜｜DSML｜｜tool_calls>` 前缀部分）
_TAIL_HOLD = 24

# 可能被劈开的标记开头（用于判断尾部是否要暂扣）
_PREFIXES = ("<", "<｜", "<｜｜", "<|", "<||", "<｜｜D", "<｜｜DS",
             "<｜｜DSM", "<｜｜DSML", "<｜｜DSML｜", "<｜｜DSML｜｜")


def has_dsml(text: str) -> bool:
    """是否包含 DSML 标记（快速判定用）"""
    return bool(_TAG_RE.search(text or ""))


def strip_dsml(text: str) -> str:
    """非流式整段剥离：去掉所有 DSML 块（标签及其间参数文本）。
    与 DsmlStreamFilter 同一语义（整段作为单个 chunk 喂入；函数体内引用，
    DsmlStreamFilter 定义于本文件后方，运行时已存在）。"""
    f = DsmlStreamFilter()
    return f.feed(text) + f.flush()


class DsmlStreamFilter:
    """跨 chunk 状态机：喂入流式增量，吐出清洗后的文本。

    状态：
    - NORMAL：正常透传；尾部疑似标记前缀暂扣（防 chunk 边界劈开标记）
    - BLOCK：处于 <tool_calls> 块内，整块丢弃直到 </tool_calls>（或流末全弃）

    用法：f = DsmlStreamFilter(); for chunk: clean = f.feed(chunk); tail = f.flush()
    """

    def __init__(self):
        self._buf = ""
        self._in_block = False
        self.saw_block = False  # 本轮是否丢弃过完整 tool_calls 块

    def feed(self, text: str) -> str:
        self._buf += text or ""
        return self._drain(partial=True)

    def flush(self) -> str:
        """流结束：仍在 BLOCK 态则全部丢弃（宁缺勿漏），否则吐出剩余缓冲"""
        out = self._drain(partial=False)
        if self._in_block:
            self._buf = ""
            self._in_block = False
        return out

    def _drain(self, partial: bool) -> str:
        out = []
        while True:
            if self._in_block:
                # 找 </…tool_calls> 闭标签
                m = _TAG_RE.search(self._buf)
                if not m:
                    if not partial:
                        self._buf = ""
                    return "".join(out)
                tag = m.group(0)
                self._buf = self._buf[m.end():]
                if tag.lstrip().startswith("</") and "tool_calls" in tag.lower():
                    self._in_block = False
                    self.saw_block = True
                continue

            m = _TAG_RE.search(self._buf)
            if m:
                before = self._buf[:m.start()]
                tag = m.group(0)
                self._buf = self._buf[m.end():]
                if tag.lstrip().startswith("</"):
                    out.append(before)  # 孤立闭标签：文本保留（无对应开标签的噪音也一并剥）
                    continue
                out.append(before)
                if "tool_calls" in tag.lower():
                    self._in_block = True
                continue

            # 无标记：从最后一个 < 起若疑似标记前缀则暂扣（防 chunk 边界劈开标记），
            # 其余吐出；尾部超长且无竖线特征则判定非标记，直接全吐
            if partial:
                idx = self._buf.rfind("<")
                if idx >= 0:
                    tail = self._buf[idx:]
                    if len(tail) >= _TAIL_HOLD and "｜" not in tail and "|" not in tail:
                        pass  # 尾部已超标记长度且无竖线 → 不是 DSML，全吐
                    else:
                        out.append(self._buf[:idx])
                        self._buf = tail
                        return "".join(out)
            out.append(self._buf)
            self._buf = ""
            return "".join(out)
