"""本地 Agent 命令行入口

用法:
    python agent/main.py --server-url ws://localhost:8000 --agent-id 1

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
    p.add_argument("--server-url", default="ws://localhost:8000", help="云端 WebSocket 地址")
    p.add_argument("--agent-id", default=socket.gethostname(), help="Agent 唯一标识")
    p.add_argument("--agent-name", default="小元AI Agent", help="Agent 显示名称")
    p.add_argument("--tray", action="store_true", help="以托盘模式运行（默认命令行模式）")
    return p.parse_args()


async def main():
    args = parse_args()
    if args.tray:
        from agent.tray import main as tray_main
        tray_main()
        return

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # 抑制 websockets 协议日志
    logging.getLogger("websockets").setLevel(logging.WARNING)

    capabilities = ["analysis", "collection", "automation"]

    orchestrator = Orchestrator()
    client = AgentWSClient(
        server_url=args.server_url,
        agent_id=args.agent_id,
        agent_name=args.agent_name,
        capabilities=capabilities,
    )
    client.on_chat_request(orchestrator.stream)

    # 把 orchestrator 的活动事件通过 WebSocket 实时上报
    orchestrator._on_activity = lambda ev: client.send_activity(ev)

    logger.info("=" * 50)
    logger.info("小元AI 本地 Agent 启动")
    logger.info("云端地址: %s", args.server_url)
    logger.info("Agent ID: %s", args.agent_id)
    logger.info("可用能力: %s", capabilities)
    logger.info("=" * 50)

    # 优雅退出
    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _shutdown():
        logger.info("收到退出信号，正在关闭...")
        stop.set_result(True)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Windows 不支持 add_signal_handler
            pass

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
