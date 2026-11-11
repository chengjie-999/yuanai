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
AGENT_VERSION = "--help"


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


def _cleanup_mei_residue():
    """更新器自愈（P0）：清理 %TEMP%\\_MEI* 残留——PyInstaller 单文件模式崩溃/
    更新被中断会遗留解包目录，残留冲突可致新包启动即崩（DLL 加载失败）。
    启动与更新前调用；当前进程自己的解包目录跳过；任何异常静默不影响主流程。"""
    try:
        import glob
        import shutil
        import tempfile
        meipass = getattr(sys, "_MEIPASS", "") or ""
        keep = os.path.normcase(os.path.abspath(meipass)) if meipass else ""
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
        removed = 0
        for d in glob.glob(os.path.join(temp_dir, "_MEI*")):
            try:
                if keep and os.path.normcase(os.path.abspath(d)) == keep:
                    continue  # 当前进程自己的解包目录不能删
                if os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
                    logger.info("已清理残留临时目录: %s", d)
            except Exception:
                pass
        if removed:
            logger.info("更新器自愈：清理了 %d 个 _MEI 残留目录", removed)
    except Exception:
        pass


# ==================== 单实例保护（2026-11-09 多开根治） ====================
_SINGLE_MUTEX_NAME = "XiaoYuanAI-Agent-SingleInstance"
_SINGLE_INSTANCE_HANDLE = None  # 持住句柄防 GC 提前释放互斥体


def _acquire_single_instance(wait_s: float = 0.5):
    """Windows 命名互斥体单实例保护：返回 (句柄|None, 是否第二实例)。
    已存在时等 wait_s 秒再判一次（覆盖极端交接窗口；互斥体是内核对象，
    进程退出自动释放，无残留死锁）。非 Windows 恒放行。"""
    if os.name != "nt":
        return None, False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        handle = kernel32.CreateMutexW(None, False, _SINGLE_MUTEX_NAME)
        if kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
            return handle, False
        deadline = time.time() + wait_s
        while time.time() < deadline:
            time.sleep(0.1)
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
            handle = kernel32.CreateMutexW(None, False, _SINGLE_MUTEX_NAME)
            if kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
                return handle, False
        return None, True
    except Exception:
        return None, False


def _notify_already_running() -> None:
    """第二实例提示（MessageBox 前台可见——此时托盘气泡尚不可靠）"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            "小元AI Agent 已经在运行了：\n\n请查看任务栏右下角的托盘图标。\n"
            "刚启动时解压加载需要几秒，图标出现前请勿重复双击。",
            "小元AI Agent", 0x40,  # MB_ICONINFORMATION
        )
    except Exception:
        pass


def _inputbox_ps(title: str, prompt: str) -> str:
    """独立进程文本输入框（Microsoft.VisualBasic InputBox 经 PowerShell 弹出，
    结果 UTF-8 临时文件传回）——绕开 pystray 回调线程弹 tkinter 无焦点不可用
    （2026-11-09 vault 教训）与控制台 GBK 编码坑。用户取消/失败返回空串。"""
    if os.name != "nt":
        return ""
    import tempfile
    prompt = str(prompt).replace("'", "''").replace("\n", " ")
    title = str(title).replace("'", "''")
    out_file = os.path.join(tempfile.gettempdir(), f"yuanai_input_{os.getpid()}.txt")
    try:
        os.remove(out_file)
    except OSError:
        pass
    ps = (
        "Add-Type -AssemblyName Microsoft.VisualBasic | Out-Null;"
        f"$r = [Microsoft.VisualBasic.Interaction]::InputBox('{prompt}', '{title}');"
        "if ($r -ne '') {"
        # UTF8Encoding($false) = 无 BOM（Encoding.UTF8 自带 BOM 会污染首字符，
        # 与 pick_directory 同款坑 2026-11-11）
        f"[System.IO.File]::WriteAllText('{out_file}', $r, "
        "([System.Text.UTF8Encoding]::new($false)))"
        "}"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                       capture_output=True, timeout=300,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return ""
    try:
        with open(out_file, "r", encoding="utf-8") as f:
            value = f.read().strip().lstrip("﻿")  # 双保险：残留 BOM 也剥
        os.remove(out_file)
        return value
    except OSError:
        return ""


def _run_script_allowed(script_path: str, root: str) -> bool:
    """冻结模式 --run-script 白名单校验（S5.1 L1）：
    realpath 必须落在内置脚本目录（agent/datanalysis/scripts|crawl、skills）内"""
    allowed = [os.path.realpath(os.path.join(root, r)) for r in
               ("agent/datanalysis/scripts", "agent/datanalysis/crawl", "skills")]
    p = os.path.realpath(script_path)
    return any(p == a or p.startswith(a + os.sep) for a in allowed)

# 状态颜色（离线=灰环灰球；在线=绿环；执行=黄环——2026-11-08 图标定版）
GREEN = (76, 175, 80)
YELLOW = (255, 152, 0)
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


def _make_icon(status: str = "offline") -> Image.Image:
    """32x32 托盘图标（2026-11-08 定版）：小元AI 吉祥物渐变核心球
    （亮 #60a5fa → 深 #1d4ed8，同 Mascot 形象）+ 状态色外环
    （在线绿/执行黄/离线灰）——不再是纯色圆点；离线=灰球"""
    S = 32
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ring = {"online": GREEN, "working": YELLOW, "offline": GRAY}.get(status, GRAY)
    draw.ellipse((2, 2, S - 2, S - 2), outline=ring + (255,), width=2)
    # 球体：自上而下线性渐变（离线灰）
    if status == "offline":
        top, bottom = (0x9e, 0x9e, 0x9e), (0x75, 0x75, 0x75)
    else:
        top, bottom = (0x60, 0xa5, 0xfa), (0x1d, 0x4e, 0xd8)
    cx, cy, R = S / 2, S / 2 + 1, 10
    for i in range(2 * R):
        t = i / (2 * R - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        y = int(cy - R + i)
        half = int((R * R - (i - R) ** 2) ** 0.5)
        draw.line([(cx - half, y), (cx + half, y)], fill=(r, g, b, 255))
    # 左上高光
    draw.ellipse((cx - R + 3, cy - R + 2, cx - R + 8, cy - R + 7),
                 fill=(255, 255, 255, 90))
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
        self._profile_label = None  # 本机账号归属（2026-11-08，查询成功后显示）
        self._reinstall_prompted = False  # T3 注销兜底：每次进程只弹一次重新注册

    def run(self):
        """主入口：启动托盘（阻塞主线程）"""
        _cleanup_mei_residue()  # P0 更新器自愈：启动先清上次崩溃/更新遗留
        icon = _make_icon("offline")
        self._icon = pystray.Icon(
            "yuanai_agent",
            icon,
            f"小元AI Agent - {self.agent_name}",
            menu=self._build_menu(),
        )
        self._icon.title = f"小元AI Agent - 离线"

        # 启动反馈（2026-11-09）：无窗口应用双击后解压加载需几秒，此前毫无
        # 动静，用户误判「没启动」而连点致多开——托盘就绪后弹一次气泡确认
        def _notify_started():
            time.sleep(1.5)
            try:
                self._icon.notify("小元AI Agent 已启动，图标常驻任务栏右下角\n"
                                  "右键图标可开关能力、查看账号", "小元AI Agent")
            except Exception:
                pass

        threading.Thread(target=_notify_started, daemon=True).start()

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
        _fail_notified = False
        while self._running:
            try:
                self._check_update_once()
            except Exception as e:
                logger.warning("检查更新失败: %s", e)
                # P0 更新器自愈：检查失败不再静默（每次进程运行只提示一次，防刷屏）
                if not _fail_notified:
                    _fail_notified = True
                    try:
                        self._icon.notify(f"检查更新失败：{e}\n网络不通或服务端异常，不影响使用；"
                                          "可稍后重试或去小元AI网站重新下载", "小元AI Agent")
                    except Exception:
                        pass
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
                # 2026-11-08 修复：update_menu() 只重估动态属性（勾选态），
                # 不增删菜单项——发现新版后「立即更新」项从未出现过。
                # menu setter 整体重建并刷新（内部调 update_menu）
                self._icon.menu = self._build_menu()
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
        _cleanup_mei_residue()  # P0 更新器自愈：更新前清残留，防新包解压冲突
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
                # P0 更新器自愈：人话报错 = 保留原失败原因（自身已人话）+
                # 可行动指引（清理临时目录/重试/重新下载）；按原因分类前缀
                reason = str(e)
                if any(k in reason for k in ("https", "sha256", "校验")):
                    tip = f"更新中止（安全）：{reason}"
                elif any(k in reason.lower() for k in ("timeout", "timed out", "urlopen", "getaddrinfo", "refused")):
                    tip = f"网络连接失败：{reason}"
                else:
                    tip = f"更新失败：{reason}（可能被杀软拦截或临时目录残留冲突）"
                self._icon.notify(
                    f"{tip}\n已自动清理临时目录残留——点「立即更新」重试；"
                    "仍失败可去小元AI网站「设置 → 本地 Agent」重新下载安装", "小元AI Agent")
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

    # ==================== 桌宠（dsh-pet-indesktop 联动，2026-10-22） ====================

    def _on_pet_launch(self, icon, item):
        threading.Thread(target=self._pet_action, args=("launch",), daemon=True).start()

    def _on_pet_stop(self, icon, item):
        threading.Thread(target=self._pet_action, args=("stop",), daemon=True).start()

    def _on_pet_setup(self, icon, item):
        threading.Thread(target=self._pet_action, args=("setup",), daemon=True).start()

    def _on_terminal_open(self, icon, item):
        threading.Thread(target=self._terminal_action, daemon=True).start()

    def _terminal_action(self) -> None:
        """终端对话入口（三本地合一 2026-10-23）：新控制台窗口跑 python -m agent.terminal。
        源码树运行直接复用当前解释器；冻结 exe 向上探测仓库 venv；失败只通知。"""
        try:
            from agent.terminal import find_terminal_launcher
            launcher = find_terminal_launcher()
            if not launcher:
                self._icon.notify("终端对话需源码环境（本机仓库 + venv）——"
                                  "发布版 exe 不含控制台终端", "终端对话")
                return
            python_exe, root = launcher
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen([python_exe, "-m", "agent.terminal"], cwd=root,
                             stdin=subprocess.DEVNULL, **kwargs)
        except Exception as e:
            logger.warning("打开终端对话失败: %s", e)
            self._icon.notify(f"终端对话启动失败：{e}", "终端对话")

    def _pet_action(self, action: str) -> None:
        """桌宠菜单动作：启动/关闭/联动设置（独立线程；失败只通知不崩托盘）"""
        try:
            from agent.pet_events import launch_pet, stop_pet, setup, find_pet_exe
            if action == "launch":
                ok, msg = launch_pet()
            elif action == "stop":
                ok, msg = stop_pet()
            else:
                if not find_pet_exe():
                    self._icon.notify("未找到桌宠程序——请先安装 dsh-pet-indesktop"
                                      "（官网下载页有便携包，装到 %LOCALAPPDATA%/dsh-pet）",
                                      "桌宠联动")
                    return
                setup()
                self._icon.notify("桌宠联动已配置：重启桌宠后右键菜单「Agent 联动」勾选「小元AI」",
                                  "桌宠联动")
                return
            self._icon.notify(msg, "桌宠")
        except Exception as e:
            logger.warning("桌宠菜单动作 %s 失败: %s", action, e)
            self._icon.notify(f"桌宠操作失败：{e}", "桌宠")

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
            # P0 退出清子进程：tree-kill 自己 spawn 的 claude（根治「只有重启才释放锁」）
            try:
                from agent.bridge_policy import kill_spawned_tree
                n = kill_spawned_tree()
                if n:
                    logger.info("退出时已终止 %d 个残留 Claude 子进程", n)
            except Exception:
                pass
            icon.stop()

        def on_reinstall(icon, item):
            # 换安装码：独立进程输入框重新注册（不退出进程）——2026-11-09 修复
            # pystray 回调线程弹 tkinter 无焦点不可用（vault 教训同款 bug）
            threading.Thread(target=self._reinstall_flow, args=("手动",), daemon=True).start()

        # 菜单分组（2026-11-08 优化）：标题/账号 → 能力开关 → 常用入口 →
        # 工具 → 发现新版时的更新项 → 维护项。状态走图标颜色+悬停标题，
        # 不在菜单里刷（工具调用时 working/online 高频切换，菜单会闪）
        items = [
            MenuItem("小元AI Agent", None, enabled=False),
        ]
        if self._profile_label:
            items.append(MenuItem(self._profile_label, None, enabled=False))
        items.append(TrayMenu.SEPARATOR)
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
            MenuItem("终端对话", self._on_terminal_open),
            TrayMenu.SEPARATOR,
            MenuItem("桌宠", TrayMenu(
                MenuItem("启动桌宠", self._on_pet_launch),
                MenuItem("关闭桌宠", self._on_pet_stop),
                MenuItem("桌宠联动设置", self._on_pet_setup),
            )),
            MenuItem("设置 Claude 工作目录…", self._on_cc_workspace),
            # vault 同步菜单下架（2026-11-09 用户拍板：知识星球非主力）——
            # 托盘菜单回调线程弹 tkinter 目录选择框无焦点不可用（选不了/
            # ✕取消不响应/切窗口消失），先隐藏入口；已配置用户的同步循环不受影响。
            # 去留待办：修复对话框（原生 Windows 目录选择器）或彻底移除，见待办清单。
            MenuItem("开机自启", self._on_autostart_toggle, checked=lambda item: autostart_enabled()),
        ]
        # 仅发现新版时出现（2026-11-08：后台 6h 自动检查，「检查更新」常显项
        # 已移除——用户拍板「有新版本了再出现」）
        if self._update_available:
            items.append(TrayMenu.SEPARATOR)
            items.append(MenuItem(f"立即更新 v{self._update_available}", self._on_update_click))
        items += [
            TrayMenu.SEPARATOR,
            MenuItem("重新注册（换安装码）", on_reinstall),
            MenuItem("退出 Agent", on_exit),
        ]
        return TrayMenu(*items)

    def _on_update_click(self, icon, item):
        """点击立即更新：后台线程执行下载+自替换"""
        threading.Thread(target=self._do_update, daemon=True).start()

    def _on_cc_workspace(self, icon, item):
        """设置 Claude Code 工作目录：原生目录选择器（独立进程，无 pystray
        回调线程焦点问题）→ 校验落盘 → 下一轮委派生效（运行期切换无需重启）"""
        threading.Thread(target=self._set_cc_workspace, daemon=True).start()

    def _set_cc_workspace(self):
        from agent import cc_workspace
        picked = cc_workspace.pick_directory("选择 Claude Code 的工作目录（代码仓库）")
        if not picked:
            return  # 用户取消
        try:
            cc_workspace.set_project_dir(picked)
            info = cc_workspace.describe()
            guard_tip = "" if info["guard_ready"] else \
                "（注意：该目录缺少安全钩子，Claude 委派将被拒绝）"
            self._icon.notify(f"Claude Code 工作目录已设为：{picked}\n"
                              f"下一轮对话生效{guard_tip}", "小元AI Agent")
            logger.info("CC 工作目录已切换: %s", picked)
        except ValueError as e:
            logger.warning("CC 工作目录设置被拒: %s", e)
            try:
                self._icon.notify(f"设置失败：{e}", "小元AI Agent")
            except Exception:
                pass

    # ==================== T3 注销/停用兜底引导（2026-11-09） ====================

    def _on_auth_rejected(self, code: str):
        """云端拒绝设备凭据（账号注销/设备解绑/冻结）→ 通知 + 自动弹重新注册。
        每次进程只提示一次（否则每次重连循环都弹）；注册成功后复位。"""
        if self._reinstall_prompted:
            return
        self._reinstall_prompted = True
        logger.warning("云端拒绝设备凭据（HTTP %s），引导重新注册", code)
        try:
            self._icon.notify("本机 Agent 已与账号解除关联（账号注销或设备解绑），"
                              "云端功能已停止——正在弹出重新注册窗口", "小元AI Agent")
        except Exception:
            pass
        threading.Thread(target=self._reinstall_flow, args=("注销兜底",), daemon=True).start()

    def _reinstall_flow(self, why: str):
        """重新注册流程（菜单「重新注册」与注销兜底共用）：独立进程输入框
        （绕开 pystray 回调线程 tkinter 无焦点问题）→ do_install → 换身份重启循环"""
        code = _inputbox_ps(
            "小元AI Agent 重新注册",
            "请输入新的安装码（小元AI网站「设置 → 本地 Agent」自取，形如 YUAN-XXXX-XXXX-XXXX）：",
        )
        if not code:
            return  # 用户取消（兜底提示已给，等用户主动操作）
        from agent.main import do_install, load_identity
        try:
            do_install(self.server_url, code.strip())
        except Exception as e:
            logger.warning("重新注册失败（%s）: %s", why, e)
            try:
                self._icon.notify(f"注册失败：{e}\n请检查安装码与网络后重试", "小元AI Agent")
            except Exception:
                pass
            return
        identity = load_identity()
        self.agent_id = str(identity.get("agent_id") or self.agent_id)
        self.agent_token = identity.get("agent_secret", "") or self.agent_token
        self._reinstall_prompted = False  # 注册成功：允许未来再次提示
        logger.info("身份已更新（%s），重启全部 Agent 循环", why)
        try:
            self._icon.notify("注册成功，正在重新连接云端…", "小元AI Agent")
        except Exception:
            pass
        # 2026-10-19 修复：plan/vault 循环线程持旧 secret，软重连只换 WS——
        # 循环持续 401 直到重启进程。身份变更走整循环重建
        self._restart_loops()

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
                # 对应 skill Agent（确定性路由，跳过统筹 LLM）；其余 → 统筹。
                # 与命令行模式共用 agent/route.py（2026-10-21 清洁8）；
                # claude 开关实时读托盘 toggles，关闭时回统筹并如实说明
                from agent.route import make_route
                route = make_route(orchestrator, claude_handler,
                                   claude_enabled=lambda: self.toggles.get("claude", True))

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
                # T3 注销兜底：凭据被拒（注销/解绑/冻结）→ 通知 + 引导重新注册
                self._client.on_auth_rejected(self._on_auth_rejected)
                orchestrator._on_activity = lambda ev: self._set_status("working") or (
                    self._client and self._client.send_activity(ev)
                )
                orchestrator._on_event = lambda ev: self._client.send_event(ev) if self._client else None
                claude_handler._ws_send = self._client.send_event

                self._set_status("online")
                self._fetch_profile()  # 本机账号归属（2026-11-08，后台线程查询）
                await self._client.connect()
            except Exception as e:
                logger.error("Agent 连接异常: %s", e)

            if self._running and not self._restart:
                self._set_status("offline")
                await asyncio.sleep(5)

    def _set_status(self, status: str):
        self._status = status
        labels = {"online": "在线", "working": "执行中", "offline": "离线"}
        if self._icon:
            try:
                # 2026-11-08：图标=吉祥物渐变球+状态色外环（离线灰/在线绿/执行黄）
                self._icon.icon = _make_icon(status)
                self._icon.title = f"小元AI Agent - {labels.get(status, status)}"
            except Exception:
                pass

    def _fetch_profile(self):
        """本机账号归属（2026-11-08）：设备凭据查云端绑定用户，托盘菜单显示。
        失败静默（菜单不显示账号行，不影响主链路）"""
        def _do():
            try:
                import urllib.request
                http_base = self._version_base_url()
                req = urllib.request.Request(
                    f"{http_base}/api/v1/agent/my-profile",
                    headers={"X-Agent-Id": str(self.agent_id),
                             "X-Agent-Secret": str(self.agent_token)})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if data.get("bound"):
                    u = data.get("user") or {}
                    self._profile_label = f"账号：{u.get('display_name') or u.get('username')}"
                else:
                    self._profile_label = "账号：未绑定（后台「Agent 管理」可绑定）"
                # menu setter 整体重建（update_menu 不增删菜单项，2026-11-08）
                self._icon.menu = self._build_menu()
            except Exception:
                logger.warning("获取账号信息失败（菜单不显示账号行）")
        threading.Thread(target=_do, daemon=True).start()


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

    # 单实例保护（2026-11-09 多开根治）：第二实例弹提示即退。位置必须在
    # --run-script 分支（脚本子进程复用本 exe，不得被拦）与安装引导之后
    # （引导进程不持锁，安装副本首启零竞争）
    global _SINGLE_INSTANCE_HANDLE
    _mutex_handle, _is_dup = _acquire_single_instance()
    if _is_dup:
        _notify_already_running()
        sys.exit(0)
    _SINGLE_INSTANCE_HANDLE = _mutex_handle

    import argparse

    p = argparse.ArgumentParser(description="小元AI 本地 Agent（托盘模式）")
    # 2026-11-08 修复：默认值写死 wss://cjyuanai.cn 会顶掉身份文件里的
    # server_url（本地联调 ws://localhost:8000 被覆盖 → 拿本地设备号去连
    # 生产 403）——default=None 走身份文件，仅显式传参时覆盖
    p.add_argument("--server-url", default=None, help="云端 WebSocket 地址（默认读身份文件）")
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

    # 傻瓜引导（T2 2026-11-06 + 安装器 2026-11-07）：无身份时按优先级静默注册
    # ① install_code.txt（安装器/引导程序写入）② exe 文件名内嵌码
    # ③ 输码弹窗兜底——零输码零弹窗；注册失败/取消则退出
    from agent.main import (load_identity, install_code_from_exe_name,
                            install_code_from_file, clear_install_code_file,
                            register_device)
    identity = load_identity()
    # 2026-11-08 修复：身份文件优先（与 CLI 口径一致），显式传参才覆盖——
    # 注册与连接共用该值（此前 argparse 默认值写死生产地址，本地联调身份被顶掉）
    server_url = args.server_url or identity.get("server_url") or "wss://cjyuanai.cn"
    if not identity.get("agent_id") or not identity.get("agent_secret"):
        code = install_code_from_file() or install_code_from_exe_name()
        if code:
            try:
                register_device(server_url, code)
                clear_install_code_file()  # 码一次消费，注册成功即清
                identity = load_identity()
                logger.info("已自动注册（安装码 %s）", code[:8] + "***")
                try:
                    import tkinter.messagebox as _mb
                    _mb.showinfo("注册成功", "本机 Agent 已自动注册并开始运行！\n\n图标会常驻任务栏右下角。")
                except Exception:
                    pass
            except Exception as e:
                logger.warning("静默注册失败（转弹窗兜底）: %s", str(e)[:120])
        if not identity.get("agent_id") or not identity.get("agent_secret"):
            if not _install_dialog(server_url):
                logger.info("用户取消安装，进程退出")
                sys.exit(0)
            identity = load_identity()

    agent_id = args.agent_id or str(identity.get("agent_id") or "1")
    agent_token = args.agent_token or identity.get("agent_secret", "") or ""

    logger.info("启动托盘模式: server=%s agent=%s", server_url, agent_id)

    tray = AgentTray(server_url, agent_id, args.agent_name, agent_token)
    tray.run()


if __name__ == "__main__":
    main()
