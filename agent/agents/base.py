"""Agent 基类（融合后仅 automation 的 react 模式保留子 Agent）"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AgentBase(ABC):
    """所有 Agent 的统一抽象基类"""

    name: str = "base"
    model_name: str = ""

    @abstractmethod
    def run(self, prompt: str, progress_cb=None) -> str:
        """同步执行。progress_cb(current, total, message) 可选进度回调
        （delegate/stream_target 统一透传；不接受 progress_cb 的实现会必炸）。"""
        ...
