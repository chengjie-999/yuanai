"""系统托盘程序：Windows 任务栏右下角图标，管理 Agent 生命周期（傻瓜化发布版）

- 首次启动无身份 → 弹窗输入安装码自动注册（后台「Agent 管理」页签发）
- 托盘菜单勾选各 Agent 开关（数据分析/采集脚本工具 + 自动化 + Claude Code），持久化 data/agent_config.json
- 二合一进程：mode=claude 请求走本机 Claude Code 桥接分支，其余走统筹 Agent
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import pystray
from pystray import Menu as TrayMenu
from pystray import MenuItem
from PIL import Image, ImageDraw

logger = logging.getLogger("agent.tray")

# 当前版本（打包发布时更新；云端 downloads/version.json 由网页上传时写入）
AGENT_VERSION = "1.0.0"


def _ver_lt(a: str, b: str) -> bool:
    """简单版本比较（1.2.3 三段数字，缺段补 0）"""
    try:
        pa = [int(x) for x in str(a).split(".")]
        pb = [int(x) for x in str(b).split(".")]
    except ValueError:
        return str(a) != str(b)  # 非数字版本号：不同即视为需要更新
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    return pa < pb


def _run_script_allowed(script_path: str, root: str) -> bool:
    """冻结模式 --run-script 白名单校验（S5.1 L1）：
    realpath 必须落在内置脚本目录（agent/datanalysis/scripts|crawl、skills）内"""
    allowed = [os.path.realpath(os.path.join(root, r)) for r in
               ("agent/datanalysis/scripts", "agent/datanalysis/crawl", "skills")]
    p = os.path.realpath(script_path)
    return any(p == a or p.startswith(a + os.sep) for a in allowed)

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
    """保存 Agent 开关配置（读-改-写合并——文件里还有 vault 等其它节，不能整覆盖）"""
    try:
        _config_file().parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if _config_file().is_file():
            try:
                data = json.loads(_config_file().read_text(encoding="utf-8"))
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        data["enabled"] = toggles
        _config_file().write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("保存 Agent 配置失败: %s", e)


# ---- 开机自启（注册表 HKCU Run，仅冻结模式 exe 有效） ----
_AUTOSTART_NAME = "小元AI Agent"


def autostart_enabled() -> bool:
    """查询开机自启是否开启"""
    if not getattr(sys, "frozen", False):
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            winreg.QueryValueEx(key, _AUTOSTART_NAME)
        return True
    except Exception:
        return False


def set_autostart(enable: bool):
    """开启/关闭开机自启（写入/删除注册表 Run 键）"""
    if not getattr(sys, "frozen", False):
        logger.info("开发模式不支持开机自启（仅 exe 发布版可用）")
        return
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
    if enable:
        winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, sys.executable)
        logger.info("已开启开机自启: %s", sys.executable)
    else:
        try:
            winreg.DeleteValue(key, _AUTOSTART_NAME)
            logger.info("已关闭开机自启")
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)


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
        # 2026-10-19 修复：root 已销毁仍作 parent 弹窗 → TclError 被吞，
        # 安装成功反而报「失败」；不传 parent 用独立弹窗
        try:
            messagebox.showinfo("安装成功", "本机 Agent 已注册，开始运行！\n\n图标会常驻任务栏右下角。")
        except Exception:
            pass
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
        self._update_available = None  # 云端最新版本号（发现新版后设置）
        self._update_forced = False  # min_version 安全下限触发（必须更新）
        self._update_sha256 = ""  # S1.7：云端清单 sha256（下载校验用）

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

        # 后台线程检查更新（启动 5 秒后，此后每 6 小时一次）
        update_thread = threading.Thread(target=self._update_check_loop, daemon=True)
        update_thread.start()

        # vault 双向同步线程（Obsidian ↔ 知识星球；agent_config.json 的 vault 节未配置则跳过）
        self._vault_loop = None
        try:
            from agent.vault_sync import build_loop_from_config
            self._vault_loop = build_loop_from_config(
                str(_config_file()), str(self.agent_id), self.agent_token, self.server_url,
                status_cb=self._emit_vault_status)
            if self._vault_loop:
                threading.Thread(target=self._vault_loop.run_loop, daemon=True).start()
                logger.info("vault 同步已启动: %s", self._vault_loop.vault_dir)
        except Exception as e:
            logger.warning("vault 同步启动失败: %s", e)

        # 计划执行器线程（手机定计划、电脑执行）：轮询云端队列认领执行；
        # 技能开关用 callable 实时读托盘 toggles，切换即生效
        self._plan_loop = None
        try:
            from agent.plan_executor import PlanExecutor
            http_base = self.server_url.replace("wss://", "https://").replace("ws://", "http://")
            self._plan_loop = PlanExecutor(
                str(self.agent_id), self.agent_token or "", http_base,
                enabled_skills=lambda: [o["cap"] for o in AGENT_OPTIONS
                                        if o["cap"] and self.toggles.get(o["key"], True)])
            threading.Thread(target=self._plan_loop.run_loop, name="plan-executor",
                             daemon=True).start()
            logger.info("计划执行器已启动")
        except Exception as e:
            logger.warning("计划执行器启动失败: %s", e)

        # 托盘在主线程运行（阻塞）
        self._icon.run()

    # ==================== 自动更新 ====================

    def _update_check_loop(self):
        """周期性检查云端 version.json，发现新版时更新托盘菜单提示"""
        time.sleep(5)
        while self._running:
            try:
                self._check_update_once()
            except Exception as e:
                logger.warning("检查更新失败: %s", e)
            time.sleep(6 * 3600)  # 每 6 小时查一次

    def _version_base_url(self) -> str:
        base = self.server_url.replace("ws://", "http://").replace("wss://", "https://").rstrip("/")
        return base

    @staticmethod
    def _insecure_update_allowed(base: str) -> bool:
        """http 仅允许 localhost/127.0.0.1 的开发场景，且需 AGENT_ALLOW_INSECURE_UPDATE=1 显式开启"""
        if base.startswith("https://"):
            return True
        from urllib.parse import urlparse
        if urlparse(base).hostname not in ("localhost", "127.0.0.1"):
            return False
        return os.getenv("AGENT_ALLOW_INSECURE_UPDATE", "0") == "1"

    def _check_update_once(self, manual: bool = False):
        """请求云端 version.json 比对（优先比文件大小，其次比版本号）；manual=True 为用户手动触发

        S1.7：清单缺 sha256 → fail-closed 不提供更新（防旧清单绕过校验）。
        """
        import urllib.request
        url = f"{self._version_base_url()}/downloads/version.json"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest = str(data.get("version", ""))
        remote_sha = str(data.get("sha256", ""))

        # 文件大小优先：更新后 exe 被替换成云端同一文件，大小一致即判定为最新
        # 2026-10-19 修复：开发态（非 frozen）sys.executable 是 python.exe——
        # 比大小必误判新版本、点「立即更新」会把 python.exe 替换成 agent exe。
        # 开发态直接跳过更新检查。
        if not getattr(sys, "frozen", False):
            return
        remote_size = data.get("size")
        has_new = False
        if remote_size:
            try:
                local_size = os.path.getsize(sys.executable)
                has_new = int(remote_size) != local_size
            except OSError:
                has_new = False
        elif latest:
            has_new = latest != AGENT_VERSION

        # fail-closed：无 sha256 的清单不提供更新（旧后端清单无法校验完整性）
        if has_new and not remote_sha:
            logger.warning("version.json 缺少 sha256，拒绝提供更新（fail-closed）")
            has_new = False
        # min_version 安全下限：当前版本低于下限时强制提示
        min_ver = str(data.get("min_version", ""))
        self._update_forced = bool(min_ver and latest and _ver_lt(AGENT_VERSION, min_ver))

        if has_new:
            self._update_available = latest or f"({remote_size})"
            self._update_sha256 = remote_sha
            try:
                self._icon.update_menu()
            except Exception:
                pass
            force_tip = "（安全要求，必须更新）" if self._update_forced else ""
            self._icon.notify(f"发现新版本 v{latest}{force_tip}，托盘菜单点击「立即更新」即可自动升级", "小元AI Agent")
        elif manual:
            self._icon.notify(f"已是最新版本 v{AGENT_VERSION}", "小元AI Agent")

    def _do_update(self):
        """一键更新：校验清单 sha256 → 下载并同步算哈希 → 一致才写自替换脚本"""
        import hashlib
        import urllib.request
        new_exe = os.path.join(_config_file().parent, "yuanai-agent.new")
        bat = os.path.join(_config_file().parent, "update.bat")
        exe_path = sys.executable
        base = self._version_base_url()
        self._icon.title = "小元AI Agent - 下载更新中..."

        try:
            # S1.7-1：强制 https（http 仅 localhost 开发 + env 显式豁免）
            if not self._insecure_update_allowed(base):
                raise RuntimeError("自动更新必须走 https（本地开发可设 AGENT_ALLOW_INSECURE_UPDATE=1）")

            # S1.7-2：先取清单，sha256 缺失即中止（fail-closed）
            with urllib.request.urlopen(f"{base}/downloads/version.json", timeout=8) as resp:
                manifest = json.loads(resp.read().decode("utf-8"))
            remote_sha = str(manifest.get("sha256", "")).lower()
            if not remote_sha:
                raise RuntimeError("云端清单缺少 sha256，已拒绝更新（安全）")
            exe_url = f"{base}{manifest.get('exe', '/downloads/yuanai-agent.exe')}"

            # S1.7-3：分块下载（约 200MB）+ 同步计算 sha256
            hasher = hashlib.sha256()
            with urllib.request.urlopen(exe_url, timeout=120) as resp, open(new_exe, "wb") as out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    out.write(chunk)
            if hasher.hexdigest() != remote_sha:
                # 校验失败：删除临时文件，绝不写 update.bat
                os.remove(new_exe)
                raise RuntimeError("更新包校验失败（sha256 不一致），已中止")

            # 自替换脚本：等待本进程退出 → 覆盖 → 重启 → 自删
            with open(bat, "w", encoding="gbk") as f:
                f.write(
                    "@echo off\n"
                    ":retry\n"
                    "timeout /t 2 /nobreak >nul\n"
                    f'copy /y "{new_exe}" "{exe_path}" >nul 2>&1\n'
                    "if errorlevel 1 goto retry\n"
                    f'if exist "{new_exe}" del "{new_exe}"\n'
                    f'start "" "{exe_path}"\n'
                    'del "%~f0"\n'
                )
            subprocess.Popen([bat], creationflags=0x08000000, close_fds=True)
            self._running = False
            self._icon.stop()
        except Exception as e:
            logger.error("自动更新失败: %s", e)
            self._icon.title = f"小元AI Agent - 更新失败"
            try:
                self._icon.notify(f"更新失败：{e}\n请稍后重试或手动下载新版", "小元AI Agent")
            except Exception:
                pass

    # ==================== vault 同步（Obsidian ↔ 知识星球） ====================

    def _emit_vault_status(self, s: dict) -> None:
        """vault 同步状态 → 日志 + WS 上报（云端存 _agent_info 供前端徽标）"""
        logger.info("vault 同步: %s", s)
        client = getattr(self, "_client", None)
        if client:
            try:
                from yuanai_core.core.schemas import vault_sync_event
                client.send_event(vault_sync_event(s))
            except Exception:
                pass

    def _vault_enabled(self) -> bool:
        from agent.vault_sync import load_vault_config
        cfg = load_vault_config(str(_config_file()))
        return bool(cfg.get("enabled")) and bool((cfg.get("path") or "").strip())

    def _on_vault_toggle(self, icon, item):
        """菜单勾选开关：切换 vault 同步并持久化（下次启动生效）"""
        from agent.vault_sync import load_vault_config, save_vault_config
        cfg = load_vault_config(str(_config_file()))
        path = (cfg.get("path") or "").strip()
        if not cfg.get("enabled"):
            if not path:
                self._icon.notify("请先「设置 vault 路径」再开启同步", "vault 同步")
                return
            cfg["enabled"] = True
            self._icon.notify("vault 同步已开启（重启 Agent 生效）", "vault 同步")
        else:
            cfg["enabled"] = False
            self._icon.notify("vault 同步已关闭", "vault 同步")
        save_vault_config(str(_config_file()), cfg)

    def _on_set_vault_path(self, icon, item):
        """弹文件夹选择框设置 Obsidian vault 同步目录"""
        import tkinter as tk
        from tkinter import filedialog, messagebox
        from agent.vault_sync import load_vault_config, save_vault_config

        root = tk.Tk()
        root.withdraw()
        try:
            chosen = filedialog.askdirectory(
                title="选择 Obsidian vault 中的「知识星球」同步目录",
                parent=root)
            if not chosen:
                return
            cfg = load_vault_config(str(_config_file()))
            cfg["path"] = chosen
            save_vault_config(str(_config_file()), cfg)
            root.destroy()
            # 2026-10-19 修复：同安装弹窗——root 已销毁勿作 parent
            try:
                messagebox.showinfo("vault 同步",
                                    f"同步目录已设置：\n{chosen}\n\n重启 Agent 后生效。")
            except Exception:
                pass
        except Exception as e:
            root.destroy()
            try:
                messagebox.showerror("vault 同步", f"设置失败：{e}")
            except Exception:
                pass

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
                # 2026-10-19 修复：plan/vault 循环线程持旧 secret，软重连只换
                # WS——循环持续 401 直到重启进程。身份变更走整循环重建
                logger.info("身份已更新，重启全部 Agent 循环")
                self._restart_loops()

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
            MenuItem("开机自启", self._on_autostart_toggle, checked=lambda item: autostart_enabled()),
            MenuItem("vault 同步", self._on_vault_toggle, checked=lambda item: self._vault_enabled()),
            MenuItem("设置 vault 路径...", self._on_set_vault_path),
            MenuItem("检查更新", lambda icon, item: threading.Thread(target=self._check_update_once, args=(True,), daemon=True).start()),
        ]
        # 发现新版时追加「立即更新」入口
        if self._update_available:
            items.append(MenuItem(f"立即更新 v{self._update_available}", self._on_update_click))
        items += [
            MenuItem("打开 Web 对话", on_open_web, default=True),
            MenuItem("重新注册（换安装码）", on_reinstall),
            MenuItem("退出 Agent", on_exit),
        ]
        return TrayMenu(*items)

    def _on_update_click(self, icon, item):
        """点击立即更新：后台线程执行下载+自替换"""
        threading.Thread(target=self._do_update, daemon=True).start()

    def _on_autostart_toggle(self, icon, item):
        """切换开机自启（exe 发布版有效）"""
        enabled = autostart_enabled()
        set_autostart(not enabled)

    def _make_toggle_action(self, key: str):
        """生成开关切换回调：翻转 → 持久化 → 重连生效"""
        def on_toggle(icon, item):
            self.toggles[key] = not self.toggles.get(key, True)
            save_toggles(self.toggles)
            logger.info("Agent 开关变化: %s = %s", key, self.toggles[key])
            self._trigger_restart()
        return on_toggle

    def _restart_loops(self):
        """身份变更后重建全部循环：停 plan/vault 线程 + 触发 WS 主循环重建"""
        self._trigger_restart()
        for attr in ("_plan_loop", "_vault_loop"):
            loop_obj = getattr(self, attr, None)
            if loop_obj and hasattr(loop_obj, "stop"):
                try:
                    loop_obj.stop()
                except Exception:
                    pass
            setattr(self, attr, None)

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
                # 2026-10-19 修复：补传 server_url/agent_id/token——
                # 此前【记住】记忆写入因 _server_url 为空永远 no-op
                claude_handler = ClaudeBridgeHandler(server_url=self.server_url,
                                                     agent_id=str(self.agent_id),
                                                     agent_token=self.agent_token)

                # 三路分派：mode=claude → Claude 桥接；@指定子智能体 → 直接调
                # 对应 skill Agent（确定性路由，跳过统筹 LLM）；其余 → 统筹
                async def route(req):
                    target = getattr(req, "target_agent", "") or ""
                    if getattr(req, "mode", "") == "claude" or target == "claude":
                        # 2026-10-19 修复：托盘开关关闭 Claude Code 时桥接分支
                        # 仍无条件生效——开关失效；关闭时回统筹并如实说明
                        if not self.toggles.get("claude", True):
                            from yuanai_core.core.schemas import done as _ev_done
                            yield _ev_done("Claude Code 已在托盘菜单中停用。如需使用，请在托盘「Agent 开关」里启用后重试。", "", req.request_id)
                            return
                        async for ev in claude_handler.stream(req):
                            yield ev
                    elif target == "automation":  # 融合后仅 automation 保留 @定向
                        async for ev in orchestrator.stream_target(req, target):
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
                # B1-12 停止联动：云端 stop 事件 → 终止该请求的脚本子进程
                self._client.on_stop_request(lambda rid: orchestrator.cancel_request(rid))
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
    # 冻结+窗口模式：无控制台，sys.stdout/stderr 为 None → 日志写入崩溃。
    # 启动最早阶段先把它们指向空设备（log 文件仍正常写入）
    if getattr(sys, "frozen", False):
        for _name in ("stdout", "stderr"):
            if getattr(sys, _name) is None:
                setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))

    # 冻结模式脚本执行入口：分析/采集脚本子进程复用本 exe（自包含，无需系统 Python）
    # S5.1（L1）：白名单校验（_MEIPASS 解包目录里的内置脚本目录）——
    # 防 exe 被拿来执行任意本地 Python 文件
    if getattr(sys, "frozen", False) and len(sys.argv) >= 3 and sys.argv[1] == "--run-script":
        _script_path = sys.argv[2]
        _root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        if not _run_script_allowed(_script_path, _root):
            print(f"拒绝执行越界脚本: {_script_path}", file=sys.stderr)
            sys.exit(2)
        sys.argv = [sys.argv[0]] + sys.argv[3:]
        with open(_script_path, encoding="utf-8") as _f:
            exec(compile(_f.read(), _script_path, "exec"), {"__name__": "__main__", "__file__": _script_path})
        sys.exit(0)

    # 首启安装引导（安装包化 2026-10-16）：exe 非安装位置双击 → 引导安装
    # （选目录 + 桌面快捷方式 + 旧数据迁移），装完启动新副本；已安装则跳过
    if getattr(sys, "frozen", False) and len(sys.argv) < 2:
        from utils.data_path import is_frozen_in_install_dir
        if not is_frozen_in_install_dir():
            from agent.bootstrap import run_install_bootstrap
            run_install_bootstrap()  # 内部处理完会启动新副本并 sys.exit(0)
            sys.exit(0)

    import argparse

    p = argparse.ArgumentParser(description="小元AI 本地 Agent（托盘模式）")
    p.add_argument("--server-url", default="wss://cjyuanai.cn", help="云端 WebSocket 地址")
    p.add_argument("--agent-id", default=None, help="Agent 唯一标识")
    p.add_argument("--agent-name", default="小元AI Agent", help="Agent 显示名称")
    p.add_argument("--agent-token", default=os.environ.get("AGENT_TOKEN", ""), help="Agent 认证 JWT token")
    args = p.parse_args()

    # 文件日志（窗口模式下控制台不可见，靠 data/logs/agent_tray.log 排障）
    _handlers = [logging.StreamHandler()]
    if getattr(sys, "frozen", False):
        _log_dir = os.path.join(os.path.dirname(_config_file()), "logs")
        os.makedirs(_log_dir, exist_ok=True)
        _handlers.append(logging.FileHandler(os.path.join(_log_dir, "agent_tray.log"), encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=_handlers,
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
