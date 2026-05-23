"""
CDP 事件驱动模块 — 替换轮询，监听浏览器原生事件。

事件类型：
- screencast_frame: 浏览器渲染新帧时推送 (Page.startScreencast)
- url_changed: URL 变化时推送 (Page.frameNavigated)
- console_message: 控制台输出 (Runtime.consoleAPICalled, 可选)
"""
import asyncio
import base64
import logging
import threading
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class CDPEventBus:
    """CDP 事件总线，跨线程安全（Selenium 回调线程 → asyncio 协程）"""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._listeners: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        self._running = False

    def push(self, event_type: str, data: dict):
        """Selenium CDP 回调线程调用，推事件到 asyncio 队列"""
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, {"type": event_type, "data": data})
        except RuntimeError:
            logger.warning("asyncio 事件循环未运行，丢弃 CDP 事件: %s", event_type)

    async def get(self, timeout: float = 0.5) -> dict | None:
        """异步消费者：从队列取出事件（非阻塞）"""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def on(self, event_type: str, callback: Callable):
        """注册同步回调"""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)

    def emit(self, event_type: str, data: dict):
        """触发同步回调"""
        with self._lock:
            for cb in self._listeners.get(event_type, []):
                try:
                    cb(data)
                except Exception:
                    pass


# 全局单例
cdp_bus = CDPEventBus()


class CDPScreencast:
    """管理 Page.startScreencast 生命周期"""

    def __init__(self, driver):
        self._driver = driver
        self._active = False

    def start(self, quality: int = 70, max_width: int = 1280, max_height: int = 720,
              every_nth_frame: int = 1):
        """开启 screencast：浏览器每渲染一帧推一张 JPEG"""
        if self._active:
            return
        try:
            self._driver.execute_cdp_cmd("Page.enable", {})
            self._driver.execute_cdp_cmd("Page.startScreencast", {
                "format": "jpeg",
                "quality": quality,
                "maxWidth": max_width,
                "maxHeight": max_height,
                "everyNthFrame": every_nth_frame,
            })
            self._active = True
            logger.info("CDP screencast 已开启 (quality=%d, max=%dx%d, everyNth=%d)",
                        quality, max_width, max_height, every_nth_frame)
        except Exception as e:
            logger.warning("CDP screencast 启动失败: %s，降级到传统截图", e)

    def stop(self):
        """停止 screencast"""
        if not self._active:
            return
        try:
            self._driver.execute_cdp_cmd("Page.stopScreencast", {})
            self._active = False
            logger.info("CDP screencast 已停止")
        except Exception:
            pass

    @property
    def active(self) -> bool:
        return self._active


def register_cdp_listeners(driver, event_bus: CDPEventBus | None = None):
    """
    在 Selenium 驱动上注册 CDP 事件监听。
    在驱动创建后、任何导航前调用。

    监听事件:
    - Page.screencastFrame → 推 base64 JPEG 帧
    - Page.frameNavigated → 推 URL 变化
    """
    if event_bus is None:
        event_bus = cdp_bus

    def on_screencast_frame(data: dict):
        """CDP 回调：收到 screencast 帧"""
        try:
            b64 = data.get("data", "")
            # 确认收到帧
            driver.execute_cdp_cmd("Page.screencastFrameAck", {
                "sessionId": data.get("sessionId", 0)
            })
            if b64:
                event_bus.push("screencast_frame", {"data": b64})
        except Exception:
            pass

    def on_frame_navigated(data: dict):
        """CDP 回调：页面 URL 变化"""
        frame = data.get("frame", {})
        url = frame.get("url", "")
        if url and not url.startswith("about:") and not url.startswith("data:"):
            event_bus.push("url_changed", {"url": url})
            event_bus.emit("url_changed", {"url": url})

    # 注册 screencast 帧回调
    driver.execute_cdp_cmd("Page.enable", {})
    try:
        # Selenium 4.x CDP listener API
        driver.add_cdp_listener("Page.screencastFrame", on_screencast_frame)
        driver.add_cdp_listener("Page.frameNavigated", on_frame_navigated)
        logger.info("CDP 事件监听已注册: screencastFrame, frameNavigated")
    except AttributeError:
        logger.warning("Selenium 版本不支持 add_cdp_listener，CDP 事件不可用")

    return event_bus
