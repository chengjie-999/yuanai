"""北京时间（UTC+8 固定偏移）——LLM 可见时间的唯一权威来源（2026-10-23）

为什么需要：云服务器系统时区多为 UTC，`datetime.now()` 在云端进程里返回
UTC——对话中「获取时间」工具与 /stream 的日期注入曾差 8 小时。
中国无夏令时，固定 +8 偏移即可，不依赖 zoneinfo/tzdata（Windows 无系统时区库）。

用法：直接替换 `datetime.now()` 使用点——返回 naive 墙钟（datetime 对象），
与既有 strftime/日期运算完全兼容。
"""
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def beijing_now() -> datetime:
    """北京时间墙钟（naive datetime，UTC+8）"""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)
