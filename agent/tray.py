"""系统托盘程序：Windows 任务栏右下角图标，管理 Agent 生命周期"""

import asyncio
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger("agent.tray")

# 状态颜色
GREEN = (76, 175, 80)
YELLOW = (255, 152, 0)
RED = (244, 67, 54)
GRAY = (158, 158, 158)

ROOT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT_DIR / "data" / "agent_icon.png"


def _make_icon(color: tuple) -> Image.Image:
    """生成 32x32 纯色圆形图标"""
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((3, 3, 29, 29), fill=color, outline=(255, 255, 255, 200), width=2)
    return img


class AgentTray:
    """系统托盘：管理 Agent 连接状态和用户交互"""

    def __init__(self, server_url: str, agent_id: str, agent_name: str, agent_token: str = ""):
        self.server_url = server_url
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_token = agent_token
        self._icon = None
        self._running = False
        self._status = "offline"  # offline | online | working
        self._loop = None
        self._client = None

    def run(self):
        """主入口：启动托盘（阻塞主线程）"""
        icon = _make_icon(GRAY)
        self._icon = pystray.Icon(
            "yuanai_agent",
            icon,
            f"小元AI Agent - {self.agent_name}",
            menu=self._build_menu(),
        )
        self._icon.title = f"小元AI Agent - 离线"

        # 异步线程启动 Agent 连接
        self._running = True
        asyncio_thread = threading.Thread(target=self._start_agent_loop, daemon=True)
        asyncio_thread.start()

        # 托盘在主线程运行（阻塞）
        self._icon.run()

    def _build_menu(self):
        def open_web():
            url = self.server_url.replace("ws://", "http://").replace("wss://", "https://").rstrip("/")
            webbrowser.open(url)

        def on_open_web(icon, item):
            open_web()

        def on_exit(icon, item):
            self._running = False
            icon.stop()

        return pystray.Menu(
            pystray.MenuItem("打开 Web 对话", on_open_web, default=True),
            pystray.MenuItem("退出 Agent", on_exit),
        )

    def _start_agent_loop(self):
        """在独立线程中运行 asyncio 事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._agent_main())
        except Exception as e:
            logger.error("Agent 主循环异常: %s", e)
        finally:
            self._loop.close()

    async def _agent_main(self):
        """Agent 主逻辑：连接、重连、状态更新"""
        from agent.ws_client import AgentWSClient
        from agent.orchestrator import Orchestrator

        capabilities = ["analysis", "collection", "automation"]

        while self._running:
            try:
                orchestrator = Orchestrator()
                self._client = AgentWSClient(
                    server_url=self.server_url,
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    capabilities=capabilities,
                    agent_token=self.agent_token,
                )
                self._client.on_chat_request(orchestrator.stream)
                orchestrator._on_activity = lambda ev: self._set_status("working") or (
                    self._client and self._client.send_activity(ev)
                )

                self._set_status("online")
                await self._client.connect()
            except Exception as e:
                logger.error("Agent 连接异常: %s", e)

            if self._running:
                self._set_status("offline")
                await asyncio.sleep(5)

    def _set_status(self, status: str):
        self._status = status
        colors = {"online": GREEN, "working": YELLOW, "offline": RED}
        labels = {"online": "在线", "working": "执行中", "offline": "离线"}
        if self._icon:
            try:
                self._icon.icon = _make_icon(colors.get(status, GRAY))
                self._icon.title = f"小元AI Agent - {labels.get(status, status)}"
            except Exception:
                pass


def main():
    import argparse

    p = argparse.ArgumentParser(description="小元AI 本地 Agent（托盘模式）")
    p.add_argument("--server-url", default="ws://localhost:8000", help="云端 WebSocket 地址")
    p.add_argument("--agent-id", default=None, help="Agent 唯一标识")
    p.add_argument("--agent-name", default="小元AI Agent", help="Agent 显示名称")
    p.add_argument("--agent-token", default=os.environ.get("AGENT_TOKEN", ""), help="Agent 认证 JWT token")
    args = p.parse_args()

    agent_id = args.agent_id or os.environ.get("AGENT_ID", "") or "1"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("websockets").setLevel(logging.WARNING)

    logger.info("启动托盘模式: server=%s agent=%s", args.server_url, agent_id)

    tray = AgentTray(args.server_url, agent_id, args.agent_name, args.agent_token)
    tray.run()


if __name__ == "__main__":
    main()
