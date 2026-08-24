"""系统托盘程序：Windows 任务栏右下角图标，管理 Agent 生命周期（傻瓜化发布版）

- 首次启动无身份 → 弹窗输入安装码自动注册（后台「Agent 管理」页签发）
- 托盘菜单勾选各 Agent 开关（数据分析/采集/自动化/生命科学/Claude Code），持久化 data/agent_config.json
- 二合一进程：mode=claude 请求走本机 Claude Code 桥接分支，其余走统筹 Agent
"""

import asyncio
import json
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

import pystray
from pystray import Menu as TrayMenu
from pystray import MenuItem
from PIL import Image, ImageDraw

logger = logging.getLogger("agent.tray")

# 状态颜色
GREEN = (76, 175, 80)
YELLOW = (255, 152, 0)
RED = (244, 67, 54)
GRAY = (158, 158, 158)

ROOT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT_DIR / "data" / "agent_icon.png"

# Agent 开关选项（claude 是二合一分支，不进 capabilities）
AGENT_OPTIONS = [
    {"key": "analysis", "label": "数据分析", "cap": "analysis"},
    {"key": "collection", "label": "数据采集", "cap": "collection"},
    {"key": "automation", "label": "自动化", "cap": "automation"},
    {"key": "medical", "label": "生命科学", "cap": "medical"},
    {"key": "claude", "label": "Claude Code", "cap": None},
]

# 配置持久化：data/agent_config.json（与身份文件同目录）
def _config_file() -> Path:
    from utils.data_path import root_path
    return Path(root_path()) / "data" / "agent_config.json"


def load_toggles() -> dict:
    """读取 Agent 开关配置，缺省全部开启"""
    defaults = {o["key"]: True for o in AGENT_OPTIONS}
    try:
        if _config_file().is_file():
            saved = json.loads(_config_file().read_text(encoding="utf-8"))
            if isinstance(saved.get("enabled"), dict):
                for k in defaults:
                    if k in saved["enabled"]:
                        defaults[k] = bool(saved["enabled"][k])
    except Exception as e:
        logger.warning("读取 Agent 配置失败，使用默认值: %s", e)
    return defaults


def save_toggles(toggles: dict):
    """保存 Agent 开关配置"""
    try:
        _config_file().parent.mkdir(parents=True, exist_ok=True)
        _config_file().write_text(
            json.dumps({"enabled": toggles}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("保存 Agent 配置失败: %s", e)


def _make_icon(color: tuple) -> Image.Image:
    """生成 32x32 纯色圆形图标"""
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((3, 3, 29, 29), fill=color, outline=(255, 255, 255, 200), width=2)
    return img


def _install_dialog(server_url: str, title: str = "小元AI Agent 安装") -> bool:
    """傻瓜引导：弹窗输入安装码 → 自动注册 → 返回是否成功"""
    import tkinter as tk
    from tkinter import simpledialog, messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        code = simpledialog.askstring(
            title,
            "首次使用需要安装码：\n\n请到网站后台「Agent 管理」页复制安装码\n（形如 YUAN-XXXX-XXXX-XXXX）",
            parent=root,
        )
        if not code:
            root.destroy()
            return False
        from agent.main import do_install
        do_install(server_url, code.strip())
        root.destroy()
        messagebox.showinfo("安装成功", "本机 Agent 已注册，开始运行！\n\n图标会常驻任务栏右下角。", parent=root)
        return True
    except Exception as e:
        root.destroy()
        try:
            messagebox.showerror("安装失败", f"注册失败：{e}\n\n请检查网络后重试。")
        except Exception:
            pass
        return False


class AgentTray:
    """系统托盘：管理 Agent 连接状态和用户交互"""

    def __init__(self, server_url: str, agent_id: str, agent_name: str, agent_token: str = ""):
        self.server_url = server_url
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_token = agent_token
        self.toggles = load_toggles()
        self._icon = None
        self._running = False
        self._status = "offline"  # offline | online | working
        self._loop = None
        self._client = None
        self._restart = False  # 开关切换后触发重连

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

        def on_reinstall(icon, item):
            # 换安装码：弹窗重新注册（不退出进程）
            if _install_dialog(self.server_url, "重新注册"):
                from agent.main import load_identity
                identity = load_identity()
                self.agent_id = str(identity.get("agent_id") or self.agent_id)
                self.agent_token = identity.get("agent_secret", "") or self.agent_token
                self._trigger_restart()

        items = [
            MenuItem("小元AI Agent", None, enabled=False),
            TrayMenu.SEPARATOR,
        ]
        # Agent 开关（勾选 = 启用）
        for opt in AGENT_OPTIONS:
            items.append(MenuItem(
                f"启用 {opt['label']}",
                self._make_toggle_action(opt["key"]),
                checked=lambda item, k=opt["key"]: bool(self.toggles.get(k)),
            ))
        items += [
            TrayMenu.SEPARATOR,
            MenuItem("打开 Web 对话", on_open_web, default=True),
            MenuItem("重新注册（换安装码）", on_reinstall),
            MenuItem("退出 Agent", on_exit),
        ]
        return TrayMenu(*items)

    def _make_toggle_action(self, key: str):
        """生成开关切换回调：翻转 → 持久化 → 重连生效"""
        def on_toggle(icon, item):
            self.toggles[key] = not self.toggles.get(key, True)
            save_toggles(self.toggles)
            logger.info("Agent 开关变化: %s = %s", key, self.toggles[key])
            self._trigger_restart()
        return on_toggle

    def _trigger_restart(self):
        """触发 Agent 重连（新 capabilities/开关立即生效）"""
        self._restart = True
        if self._client:
            try:
                future = asyncio.run_coroutine_threadsafe(self._client.disconnect(), self._loop)
                future.result(timeout=5)
            except Exception:
                pass

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
        """Agent 主逻辑：连接、重连、状态更新（二合一：统筹 + Claude 分支）"""
        from agent.ws_client import AgentWSClient
        from agent.orchestrator import Orchestrator
        from agent.claude_bridge import ClaudeBridgeHandler

        while self._running:
            self._restart = False
            try:
                # 按开关过滤：enabled_skills 决定委派工具与 capabilities
                enabled_skills = [
                    o["cap"] for o in AGENT_OPTIONS
                    if o["cap"] and self.toggles.get(o["key"], True)
                ]
                orchestrator = Orchestrator(
                    enabled_skills=enabled_skills,
                    enable_claude=bool(self.toggles.get("claude", True)),
                )
                claude_handler = ClaudeBridgeHandler()

                # 二合一路由：mode=claude → Claude 桥接；否则统筹
                async def route(req):
                    if getattr(req, "mode", "") == "claude":
                        async for ev in claude_handler.stream(req):
                            yield ev
                    else:
                        async for ev in orchestrator.stream(req):
                            yield ev

                self._client = AgentWSClient(
                    server_url=self.server_url,
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    capabilities=enabled_skills,
                    agent_token=self.agent_token,
                )
                self._client.on_chat_request(route)
                orchestrator._on_activity = lambda ev: self._set_status("working") or (
                    self._client and self._client.send_activity(ev)
                )
                orchestrator._on_event = lambda ev: self._client.send_event(ev) if self._client else None
                claude_handler._ws_send = self._client.send_event

                self._set_status("online")
                await self._client.connect()
            except Exception as e:
                logger.error("Agent 连接异常: %s", e)

            if self._running and not self._restart:
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
    # 冻结模式脚本执行入口：分析/采集脚本子进程复用本 exe（自包含，无需系统 Python）
    if getattr(sys, "frozen", False) and len(sys.argv) >= 3 and sys.argv[1] == "--run-script":
        _script_path = sys.argv[2]
        sys.argv = [sys.argv[0]] + sys.argv[3:]
        with open(_script_path, encoding="utf-8") as _f:
            exec(compile(_f.read(), _script_path, "exec"), {"__name__": "__main__", "__file__": _script_path})
        sys.exit(0)

    import argparse

    p = argparse.ArgumentParser(description="小元AI 本地 Agent（托盘模式）")
    p.add_argument("--server-url", default="wss://cjyuanai.cn", help="云端 WebSocket 地址")
    p.add_argument("--agent-id", default=None, help="Agent 唯一标识")
    p.add_argument("--agent-name", default="小元AI Agent", help="Agent 显示名称")
    p.add_argument("--agent-token", default=os.environ.get("AGENT_TOKEN", ""), help="Agent 认证 JWT token")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("websockets").setLevel(logging.WARNING)

    # 傻瓜引导：无身份时弹窗输入安装码自动注册（注册失败/取消则退出）
    from agent.main import load_identity
    identity = load_identity()
    if not identity.get("agent_id") or not identity.get("agent_secret"):
        if not _install_dialog(args.server_url):
            logger.info("用户取消安装，进程退出")
            sys.exit(0)
        identity = load_identity()

    agent_id = args.agent_id or str(identity.get("agent_id") or "1")
    agent_token = args.agent_token or identity.get("agent_secret", "") or ""

    logger.info("启动托盘模式: server=%s agent=%s", args.server_url, agent_id)

    tray = AgentTray(args.server_url, agent_id, args.agent_name, agent_token)
    tray.run()


if __name__ == "__main__":
    main()
