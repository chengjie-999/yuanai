"""本地 Agent 命令行入口

用法:
    python agent/main.py --server-url wss://cjyuanai.cn --agent-id 1

开发期以命令行脚本方式运行，前台输出日志，Ctrl+C 退出。
"""

import argparse
import asyncio
import json
import logging
import signal
import socket
import sys
import os
import threading
import urllib.request

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.ws_client import AgentWSClient
from agent.orchestrator import Orchestrator
from utils.data_path import root_path

logger = logging.getLogger("agent")

IDENTITY_FILE = os.path.join(root_path(), "data", "agent_identity.json")


def parse_args():
    p = argparse.ArgumentParser(description="小元AI 本地 Agent")
    p.add_argument("--server-url", default=None, help="云端 WebSocket 地址（默认 wss://cjyuanai.cn）")
    p.add_argument("--agent-id", default=None, help="Agent 唯一标识（机器模式：由安装注册自动获得）")
    p.add_argument("--agent-name", default="小元AI Agent", help="Agent 显示名称")
    p.add_argument("--agent-token", default=None, help="Agent 认证凭据（JWT 或注册获得的 agent_secret；默认：身份文件 > AGENT_TOKEN 环境变量）")
    p.add_argument("--install", metavar="安装码", default=None, help="首次安装：用后台签发的安装码注册本机（如 YUAN-XXXX-XXXX-XXXX）")
    p.add_argument("--tray", action="store_true", help="以托盘模式运行（默认命令行模式）")
    p.add_argument("--vault-sync", action="store_true",
                   help="命令行模式启动 vault 同步循环（托盘模式自动随配置启用）")
    p.add_argument("--no-plan-executor", action="store_true",
                   help="关闭计划执行器（默认开启：手机定计划、本机拉取执行）")
    return p.parse_args()


def load_identity() -> dict:
    """读取本机安装注册后保存的身份文件"""
    try:
        with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def do_install(server_url: str, install_code: str):
    """安装注册：消费安装码 → 云端注册设备 → 保存身份文件"""
    # server-url 是 ws(s):// 形式（Agent 连接用），HTTP 调用需转 http(s)://
    http_base = server_url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        payload = json.dumps({"install_code": install_code, "machine_name": socket.gethostname()}).encode("utf-8")
        req = urllib.request.Request(
            f"{http_base}/api/v1/agent/register",
            data=payload, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail", str(e))
        except Exception:
            detail = str(e)
        print(f"安装失败: {detail}")
        sys.exit(1)
    except Exception as e:
        print(f"安装失败（网络或服务异常）: {e}")
        sys.exit(1)

    os.makedirs(os.path.dirname(IDENTITY_FILE), exist_ok=True)
    identity = {
        "server_url": server_url,
        "agent_id": resp["agent_id"],
        "agent_secret": resp["agent_secret"],
        "machine_name": resp.get("machine_name", socket.gethostname()),
    }
    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(identity, f, ensure_ascii=False, indent=2)
    print("=" * 50)
    print(f"安装成功！本机已注册为 Agent #{resp['agent_id']}（{identity['machine_name']}）")
    print(f"身份已保存: {IDENTITY_FILE}")
    print("下一步: 云端后台管理 → Agent 管理，把该设备绑定到用户账号")
    print("=" * 50)


async def main():
    args = parse_args()
    if args.tray:
        from agent.tray import main as tray_main
        tray_main()
        return

    # vault 同步前台循环（CLI 模式显式启用；默认关——托盘模式随配置自动启）
    if args.vault_sync:
        identity = load_identity()
        server_url = args.server_url or identity.get("server_url") or "wss://cjyuanai.cn"
        agent_id = args.agent_id or str(identity.get("agent_id") or socket.gethostname())
        agent_token = args.agent_token or identity.get("agent_secret", "") or os.getenv("AGENT_TOKEN", "")
        from agent.vault_sync import build_loop_from_config, load_vault_config
        from utils.data_path import root_path
        cfg_path = os.path.join(root_path(), "data", "agent_config.json")
        loop = build_loop_from_config(cfg_path, agent_id, agent_token, server_url,
                                      status_cb=lambda s: logger.info("vault 同步: %s", s))
        if not loop:
            cfg = load_vault_config(cfg_path)
            if not (cfg.get("path") or "").strip():
                logger.error("未配置 vault 路径：请编辑 data/agent_config.json 的 vault.path 后重试")
            elif not cfg.get("enabled"):
                logger.error("vault 同步未启用：agent_config.json 的 vault.enabled=true 后重试")
            sys.exit(1)
        logger.info("vault 同步循环启动（Ctrl+C 退出）: %s", loop.vault_dir)
        loop.run_loop()
        return

    # 安装流程（注册后退出）
    if args.install:
        do_install(args.server_url or "wss://cjyuanai.cn", args.install)
        return

    # 机器模式：优先使用安装注册保存的身份（凭据优先级：命令行 > 身份文件 > AGENT_TOKEN 环境变量）
    identity = load_identity()
    server_url = args.server_url or identity.get("server_url") or "wss://cjyuanai.cn"
    agent_id = args.agent_id or str(identity.get("agent_id") or socket.gethostname())
    agent_token = args.agent_token or identity.get("agent_secret", "") or os.getenv("AGENT_TOKEN", "")

    # S3.3：强制 wss（ws:// 仅允许 localhost/127.0.0.1 且 AGENT_ALLOW_INSECURE_WS=1 显式豁免）
    from urllib.parse import urlparse as _urlparse
    _host = _urlparse(server_url).hostname or ""
    if server_url.startswith("ws://") and not (
            _host in ("localhost", "127.0.0.1") and os.getenv("AGENT_ALLOW_INSECURE_WS") == "1"):
        logger.error("拒绝明文 ws:// 连接（%s）：Agent 凭据经明文传输会被窃取；"
                     "本地开发可设 AGENT_ALLOW_INSECURE_WS=1", server_url)
        sys.exit(1)

    # 配置日志
    from logging.handlers import RotatingFileHandler
    from utils.data_path import root_path
    log_dir = os.path.join(root_path(), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                os.path.join(log_dir, "agent.log"),
                maxBytes=5 * 1024 * 1024, backupCount=5,
                encoding="utf-8",
            ),
        ],
    )
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    from skills import skill_registry
    capabilities = skill_registry.names

    orchestrator = Orchestrator()
    client = AgentWSClient(
        server_url=server_url,
        agent_id=agent_id,
        agent_name=args.agent_name,
        capabilities=capabilities,
        agent_token=agent_token,
    )

    # 三路分派：mode=claude → 本机 Claude Code 桥接；@指定子智能体 → 直接调
    # 对应 skill Agent（确定性路由，跳过统筹 LLM）；其余 → 统筹 Agent 意图路由
    from agent.claude_bridge import ClaudeBridgeHandler
    claude_handler = ClaudeBridgeHandler()
    TARGET_SKILLS = ("analysis", "collection", "automation")

    async def route(req):
        target = getattr(req, "target_agent", "") or ""
        if req.mode == "claude" or target == "claude":
            async for ev in claude_handler.stream(req):
                yield ev
        elif target in TARGET_SKILLS:
            async for ev in orchestrator.stream_target(req, target):
                yield ev
        else:
            async for ev in orchestrator.stream(req):
                yield ev

    client.on_chat_request(route)

    # 把 orchestrator 的活动事件通过 WebSocket 实时上报
    orchestrator._on_activity = lambda ev: client.send_activity(ev)
    # 工具内的 progress 心跳等任意事件上报（如 Claude Code 长任务保活）
    orchestrator._on_event = lambda ev: client.send_event(ev)
    claude_handler._ws_send = client.send_event

    logger.info("=" * 50)
    logger.info("小元AI 本地 Agent 启动")
    logger.info("云端地址: %s", server_url)
    logger.info("Agent ID: %s", agent_id)
    logger.info("可用能力: %s", capabilities)
    logger.info("=" * 50)

    # 优雅退出（兼容 Windows：add_signal_handler 不可用时退回到 signal.signal）
    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _shutdown():
        logger.info("收到退出信号，正在关闭...")
        stop.set_result(True)

    _signal_ok = False
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
            _signal_ok = True
        except NotImplementedError:
            pass
    if not _signal_ok:
        # Windows fallback: signal.signal + call_soon_threadsafe
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda s, f: loop.call_soon_threadsafe(_shutdown))

    connect_task = asyncio.create_task(client.connect())

    # 计划执行器（手机定计划、电脑执行）：后台线程轮询云端队列，认领分步
    # 执行分析/采集任务；云端是唯一真相源，本机崩溃后看门狗自动续跑
    plan_loop = None
    if not args.no_plan_executor and agent_token and not str(agent_token).startswith("eyJ"):
        # 仅机器模式（agent_secret）可用：REST 端点校验设备凭据，JWT 旧模式会 401
        from agent.plan_executor import PlanExecutor
        http_base = server_url.replace("wss://", "https://").replace("ws://", "http://")
        plan_loop = PlanExecutor(agent_id=str(agent_id), agent_secret=agent_token,
                                 server_base=http_base)
        threading.Thread(target=plan_loop.run_loop, name="plan-executor", daemon=True).start()
        logger.info("计划执行器已启动（轮询 %s）", http_base)

    try:
        await stop
    except asyncio.CancelledError:
        pass
    finally:
        if plan_loop:
            plan_loop.stop()
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    logger.info("Agent 已退出")


if __name__ == "__main__":
    asyncio.run(main())
