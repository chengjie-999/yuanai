"""小元AI 本地 MCP 服务器（T13 A1，2026-11-15 大方向定版核心）。

项目大方向（用户拍板）：网站/移动端=主对话入口；本地以终端形式运行——
**直接用 Claude Code 终端**，经本服务器具备本地其他智能体的**发现与调用**
能力与跨系统运行能力。

本模块 = stdio MCP 服务器（Python 官方 mcp SDK 2.x）：
- 发现：`list_local_agents`——统筹/自动化/分析脚本/采集脚本/计划队列/桌宠状态
- 调用：`script_*`（9 个分析脚本 + 通用网页采集，签名与校验规则从
  ScriptRegistry 动态生成——与统筹 function calling 同一咽喉，参数校验/
  看板缓存/停止联动全复用）
- 跨系统：脚本子进程/看板产物/桌宠联动在 CC 终端一个入口调度

用法（CC 注册，一次性）：
    claude mcp add xiaoyuan -- venv\\Scripts\\python.exe -m agent.mcp_server
冻结 exe 形态（打包批次后）：
    claude mcp add xiaoyuan -- <安装目录>\\小元AI Agent.exe --run-mcp
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from agent.scripts.registry import ScriptRegistry  # noqa: E402
from agent.pet_events import emit as _emit_pet  # noqa: E402

MAX_OUTPUT = 20000  # 工具输出截断（教训 #4：最坏输出多大——脚本 stdout 含大 HTML）

_ANALYSIS = ScriptRegistry("agent/datanalysis/scripts", skill="analysis")
_CRAWL = ScriptRegistry("agent/datanalysis/crawl", skill="collection")

_PY_TYPE = {"int": "int", "float": "float"}


def _handle_of(name: str):
    for reg in (_ANALYSIS, _CRAWL):
        h = reg.resolve(name)
        if h:
            for handle in reg.iter_handles():
                if handle.name == h:
                    return handle
    return None


async def _invoke_script(name: str, **params) -> str:
    """脚本执行（与统筹 function calling 同一咽喉）：registry.run 校验 + 子
    进程 + 看板缓存 + 停止联动全复用；桌宠六态联动（终端干活→宠物陪伴）"""
    handle = _handle_of(name)
    if handle is None:
        return f"未知脚本：{name}（用 list_local_agents 查看可用脚本）"
    params = {k: v for k, v in params.items() if v is not None}
    _emit_pet("working", tool=f"script_{handle.key}")
    try:
        out = await asyncio.to_thread(handle.run, **params)
    except Exception as e:
        _emit_pet("error")
        return f"执行失败：{type(e).__name__}: {str(e)[:200]}"
    _emit_pet("idle")
    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT] + "\n...(输出过长已截断)"
    return out


def _make_script_tool(handle):
    """脚本 handle → 动态签名 async 函数（mcp 2.x 从签名生成 inputSchema——
    参数名/类型来自脚本 __script_params__ 声明，与 registry 校验同源）"""
    sig_parts = []
    for pname in handle._param_order:
        pspec = handle._param_schemas.get(pname, {})
        ptype = _PY_TYPE.get(pspec.get("type"), "str")
        sig_parts.append(f"{pname}: {ptype} = None")
    sig = ", ".join(sig_parts)
    args = ", ".join(handle._param_order)
    call = f", {args}" if args else ""
    src = (f"async def f({sig}):\n"
           f"    return await _invoke_script({handle.name!r}{call})\n")
    ns = {"_invoke_script": _invoke_script}
    exec(src, ns)  # noqa: S102 动态签名是本模块的设计（schema 源自脚本声明）
    fn = ns["f"]
    fn.__name__ = f"script_{handle.key}"
    return fn


def build_server() -> MCPServer:
    """组装小元AI 本地 MCP：发现 + 全部脚本调用工具"""
    server = MCPServer(name="xiaoyuan", description="小元AI 本地智能体——发现与调用（分析脚本/采集），跨系统执行")

    def list_local_agents() -> str:
        """发现本地智能体清单：统筹/自动化/脚本/计划/桌宠状态。"""
        lines = ["本地智能体（小元AI）：", ""]
        lines.append("- 统筹 Orchestrator：云端对话的本地执行者（意图路由 + 脚本直调），"
                    "经托盘 Agent 承载")
        lines.append("- 自动化 Agent：浏览器自动化（react 多步自主），经托盘 Agent 承载")
        lines.append("")
        lines.append(f"分析脚本（{len(_ANALYSIS.iter_handles())} 个）：")
        for h in _ANALYSIS.iter_handles():
            lines.append(f"  - script_{h.key}：{h.description or h.name}")
        lines.append(f"采集脚本（{len(_CRAWL.iter_handles())} 个）：")
        for h in _CRAWL.iter_handles():
            lines.append(f"  - script_{h.key}：{h.description or h.name}")
        try:
            from agent.pet_events import last_state
            pet = last_state() or "未运行"
        except Exception:
            pet = "未运行"
        lines.append("")
        lines.append(f"桌宠状态：{pet}")
        lines.append("计划队列与云端会话经网站操作（手机定计划、电脑执行）。")
        return "\n".join(lines)

    server.add_tool(list_local_agents)
    for h in _ANALYSIS.iter_handles():
        server.add_tool(_make_script_tool(h), description=h.description or h.name)
    for h in _CRAWL.iter_handles():
        server.add_tool(_make_script_tool(h), description=h.description or h.name)
    return server


if __name__ == "__main__":
    # stdio 循环（CC 以子进程拉起本模块，JSON-RPC 走 stdin/stdout；
    # mcp 2.x 的 run() 是同步入口，内部 anyio.run 管理事件循环）
    build_server().run()
