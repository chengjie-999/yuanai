"""dsh-pet-indesktop 联动事件写方（2026-10-22）

协议来源：dsh-pet-indesktop `docs/AGENT_LINK_PROTOCOL.md`（MIT 项目，本地
JSONL 文件事件总线——桌宠 ByteOffsetTailer 只读监听，零改桌宠代码接入）。
写方纪律（协议 §2.5/§6）：
1. 追加写 UTF-8；连续相同状态去重（重复行会占住桌宠端换帧节流位）
2. 事件文件 ~1MB 轮转（`.jsonl` → `.jsonl.1`，只留一代）
3. 失败静默——联动是锦上添花，绝不阻塞 Agent 本体
4. 只写元数据（状态/事件名/工具名），绝不写正文/命令/截图

一键配置：`python -m agent.pet_events --setup`
（自动探测桌宠配置目录 %APPDATA%\\dsh-pet-standalone*，合并写入
config.json 的 agent_link.custom_agents「小元AI」条目，改前备份 .bak）。
事件路径可用环境变量 PET_EVENTS_PATH 覆盖（不用 --setup 时，桌宠
custom_agents 指向同一路径即可）。演示：`--test` 发 thinking→working→idle。
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time

AGENT_KEY = "xiaoyuan"
AGENT_NAME = "小元AI"
ROTATE_BYTES = 1_000_000  # ~1MB 轮转（协议：只留一代）

_lock = threading.Lock()
_last: tuple | None = None  # (state/event, tool) 连续去重


def _config_dir() -> str:
    """桌宠配置目录（按协议 §2.1；Windows 下扫描 %APPDATA% 的 dsh-pet-standalone* 变体）。

    优先含 config.json 的目录（桌宠首启生成的真实配置目录）——防止早于安装
    运行 --setup 时创建的裸目录抢先被选中（webm-chat 等变体后缀目录才是真的）；
    多个命中时取最长名（最具体变体）。"""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/dsh-pet-standalone")
    if sys.platform.startswith("linux"):
        return os.path.expanduser("~/.config/dsh-pet-standalone")
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    hits = []
    if os.path.isdir(base):
        for name in os.listdir(base):
            p = os.path.join(base, name)
            if name.startswith("dsh-pet-standalone") and os.path.isdir(p):
                hits.append(p)
    if hits:
        with_cfg = [p for p in hits if os.path.exists(os.path.join(p, "config.json"))]
        return sorted(with_cfg or hits, key=len, reverse=True)[0]
    return os.path.join(base, "dsh-pet-standalone")


def events_path() -> str:
    """事件文件路径（PET_EVENTS_PATH 优先——不 --setup 时桌宠 custom_agents 指向同一路径即可）"""
    env = os.environ.get("PET_EVENTS_PATH")
    if env:
        return env
    return os.path.join(_config_dir(), "agent-events", f"{AGENT_KEY}.jsonl")


def _rotate_if_needed(path: str) -> None:
    try:
        if os.path.exists(path) and os.path.getsize(path) > ROTATE_BYTES:
            bak = path + ".1"
            if os.path.exists(bak):
                os.remove(bak)
            os.replace(path, bak)
    except OSError:
        pass


def emit(state: str = None, event: str = None, tool: str = None) -> None:
    """追加一行事件。state=六态词汇（thinking/working/attention/error/idle/sleeping，
    优先于 event）；event=Claude hooks 兼容事件名（PreToolUse→working 等）。失败静默。"""
    if not state and not event:
        return
    global _last
    tool = (str(tool)[:64] or "") if tool else ""
    key = (state or event or "", tool)
    with _lock:
        if _last == key:
            return  # 连续同状态去重
        _last = key
        try:
            path = events_path()
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            _rotate_if_needed(path)
            line = {"ts": time.time(), "agent": AGENT_KEY}
            if state:
                line["state"] = state
            else:
                line["event"] = event
            if tool:
                line["tool"] = tool
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            _last = None  # 写失败允许下轮重试


def setup() -> None:
    """一键配置：桌宠 config.json 合并写入 custom_agents「小元AI」条目（改前备份 .bak）"""
    d = _config_dir()
    cfg_path = os.path.join(d, "config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            cfg = {}
    link = cfg.setdefault("agent_link", {})
    agents = [a for a in (link.get("custom_agents") or []) if isinstance(a, dict)]
    agents = [a for a in agents if a.get("key") != AGENT_KEY]
    agents.append({"key": AGENT_KEY, "name": AGENT_NAME, "path": events_path()})
    link["custom_agents"] = agents
    if os.path.exists(cfg_path):
        try:
            shutil.copy2(cfg_path, cfg_path + ".bak")
        except OSError:
            pass
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("✅ 小元AI 桌宠联动已配置")
    print(f"   配置目录: {d}")
    print(f"   事件文件: {events_path()}")
    print("   下一步：重启 dsh-pet 桌宠 → 右键菜单「Agent 联动」勾选「小元AI」→ 小元干活时桌宠自动换动作")


# ====================== 桌宠进程管理（托盘托管，2026-10-22） ======================

def find_pet_exe() -> str | None:
    """探测桌宠主程序：PET_EXE_PATH 环境变量 > %LOCALAPPDATA%\dsh-pet\* >
    与 Agent exe 同目录的 dsh-pet\*（同包分发形态）。"""
    env = os.environ.get("PET_EXE_PATH")
    if env and os.path.exists(env):
        return env
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        hits = sorted(glob.glob(os.path.join(local, "dsh-pet", "dsh-pet-standalone*.exe")))
        if hits:
            return hits[0]
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir:
        hits = sorted(glob.glob(os.path.join(exe_dir, "dsh-pet", "dsh-pet-standalone*.exe")))
        if hits:
            return hits[0]
    return None


def launch_pet() -> tuple:
    """启动桌宠（独立进程，不随 Agent 退出）。返回 (ok: bool, 信息: str)"""
    exe = find_pet_exe()
    if not exe:
        return False, "未找到桌宠程序（请安装到 %LOCALAPPDATA%\dsh-pet，或与小元 Agent 同目录的 dsh-pet\）"
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([exe], cwd=os.path.dirname(exe),
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **kwargs)
        return True, f"桌宠已启动：{exe}"
    except Exception as e:
        return False, f"启动失败：{e}"


def stop_pet() -> tuple:
    """关闭桌宠（按主程序进程名；找不到进程视为已关闭）。返回 (ok, 信息)"""
    exe = find_pet_exe()
    name = os.path.basename(exe) if exe else "dsh-pet-standalone-webm-chat.exe"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, timeout=15)
        else:
            subprocess.run(["pkill", "-f", name], capture_output=True, timeout=15)
        return True, "桌宠已关闭"
    except Exception as e:
        return False, f"关闭失败：{e}"


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="小元AI 桌宠联动（dsh-pet-indesktop）")
    ap.add_argument("--setup", action="store_true", help="一键配置桌宠 custom_agents（合并写入 config.json）")
    ap.add_argument("--test", action="store_true", help="发一组演示事件（thinking→working→idle）")
    args = ap.parse_args()
    if args.setup:
        setup()
    elif args.test:
        emit(state="thinking")
        time.sleep(1)
        emit(state="working", tool="bash")
        time.sleep(1)
        emit(state="idle")
        print(f"演示事件已写入 → {events_path()}")
    else:
        ap.print_help()
