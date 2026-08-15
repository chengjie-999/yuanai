"""本地 Agent 命令行入口

用法:
    python agent/main.py --server-url wss://cjyuanai.cn --agent-id 1

开发期以命令行脚本方式运行，前台输出日志，Ctrl+C 退出。
"""

import argparse
import asyncio
import logging
import signal
import socket
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.ws_client import AgentWSClient
from agent.orchestrator import Orchestrator

logger = logging.getLogger("agent")


def parse_args():
    p = argparse.ArgumentParser(description="小元AI 本地 Agent")
    p.add_argument("--server-url", default="wss://cjyuanai.cn", help="云端 WebSocket 地址")
    p.add_argument("--agent-id", default=socket.gethostname(), help="Agent 唯一标识")
    p.add_argument("--agent-name", default="小元AI Agent", help="Agent 显示名称")
    p.add_argument("--agent-token", default=os.getenv("AGENT_TOKEN", ""), help="Agent 认证 JWT token（也可通过 AGENT_TOKEN 环境变量设置）")
    p.add_argument("--tray", action="store_true", help="以托盘模式运行（默认命令行模式）")
    return p.parse_args()


async def main():
    args = parse_args()
    if args.tray:
        from agent.tray import main as tray_main
        tray_main()
        return

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
        server_url=args.server_url,
        agent_id=args.agent_id,
        agent_name=args.agent_name,
        capabilities=capabilities,
        agent_token=args.agent_token,
    )
    client.on_chat_request(orchestrator.stream)

    # 把 orchestrator 的活动事件通过 WebSocket 实时上报
    orchestrator._on_activity = lambda ev: client.send_activity(ev)
    # 工具内的 progress 心跳等任意事件上报（如 Claude Code 长任务保活）
    orchestrator._on_event = lambda ev: client.send_event(ev)

    logger.info("=" * 50)
    logger.info("小元AI 本地 Agent 启动")
    logger.info("云端地址: %s", args.server_url)
    logger.info("Agent ID: %s", args.agent_id)
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

    try:
        await stop
    except asyncio.CancelledError:
        pass
    finally:
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    logger.info("Agent 已退出")


if __name__ == "__main__":
    asyncio.run(main())
