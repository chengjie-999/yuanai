"""Token 估算（零依赖纯函数）——上下文用量指示器 / 用量展示用。

不引 tiktoken（依赖重、本地 Agent 打包体积敏感）：CJK 字符 ≈1 token
（DeepSeek/豆包 tokenizer 对中文常 0.6~1.5 token/字，取 1 保守偏满），
其余按 4 字符 ≈1 token。估算本用于展示百分比，误差可接受；
需要精确计数时再按模型接官方 tokenizer。
"""

import re

# 中日韩表意文字 + CJK 标点 + 全角字符（均按 1 token 计）
_CJK_RE = re.compile(r'[一-鿿　-〿＀-￯]')


def estimate_tokens(text: str) -> int:
    """文本 → 估算 token 数（2026-11-06）"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = max(0, len(text) - cjk)
    return cjk + other // 4 + (1 if other % 4 else 0)


def model_context_window(model: str = "") -> int:
    """模型上下文窗口上限（2026-11-06）：deepseek 系 128K、doubao 系 256K，
    未识别兜底 128K——指示器展示用，新模型接入时在此登记。"""
    m = (model or "").lower()
    if m.startswith("doubao") or "seed" in m:
        return 256_000
    return 128_000
