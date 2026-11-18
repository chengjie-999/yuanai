"""小元AI 本地 MCP 服务器（T13 A1+A2，2026-11-15 大方向定版核心）。

项目大方向（用户拍板）：网站/移动端=主对话入口；本地以终端形式运行——
**直接用 Claude Code 终端**，经本服务器具备本地其他智能体的**发现与调用**
能力与跨系统运行能力。

本模块 = stdio MCP 服务器（Python 官方 mcp SDK 2.x）：
- 发现：`list_local_agents`——统筹/自动化/分析脚本/采集脚本/计划/记忆/
  知识星球/云端对话/桌宠状态
- 调用（A1）：`script_*`（9 个分析脚本 + 通用网页采集，签名与校验规则从
  ScriptRegistry 动态生成——与统筹 function calling 同一咽喉，参数校验/
  看板缓存/停止联动全复用）
- 调用（A2，2026-11-18）：`run_automation`（浏览器自动化 react Agent）/
  `create_plan`/`execute_plan`/`plan_status`（计划闭环）/`get_memory`/
  `remember`（长期记忆）/`retrieve_planet_knowledge`（知识星球）/
  `cloud_chat`（云端小元AI——与网站同一主对话，桥接云端统筹）
- 云端依赖工具（计划/记忆/星球/云端对话）需本机 Agent 设备凭据
  （data/agent_identity.json，双路径判定与 Agent 工具同一咽喉）；
  离线能力（脚本/自动化/发现）无凭据可用
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


# ==================== A2 调用面（2026-11-18） ====================

def _check_identity() -> dict:
    """云端依赖工具的前置检查：返回本机设备身份；未注册返回 None（调用方
    给人话引导）。计划/记忆/星球工具内部按同一身份走双路径（is_remote_agent
    → /api/v1/agent/* HTTP 设备凭据，身份由云端绑定推导）——与 Agent 工具
    同一咽喉，不另建通道。"""
    from yuanai_core.pure.agent_remote import read_identity
    ident = read_identity()
    if ident.get("agent_id") and ident.get("server_url"):
        return ident
    return None


def _identity_hint(what: str) -> str:
    return (f"本机未注册小元AI Agent（{what}需要设备凭据）——请先到网站设置页"
            "「本地 Agent 下载」安装并注册，注册后本工具即可用；"
            "离线能力（脚本/自动化/发现）不受影响。")


def _automation_agent():
    """自动化 react Agent 惰性构造（selenium 等重依赖只在调用时导入）"""
    from agent.agents.automation import AutomationAgent
    return AutomationAgent()


async def run_automation(prompt: str) -> str:
    """浏览器自动化 react Agent（本机执行；多步自主，与托盘 Agent 同款）"""
    if not (prompt or "").strip():
        return "请描述要自动化的任务（例如：打开 xx 网站搜索 xx 并截图）"
    _emit_pet("working", tool="run_automation")
    try:
        agent = _automation_agent()
        out = await asyncio.to_thread(agent.run, prompt)
    except Exception as e:
        _emit_pet("error")
        return f"自动化执行失败：{type(e).__name__}: {str(e)[:300]}"
    _emit_pet("idle")
    return out[:MAX_OUTPUT] + ("\n...(输出过长已截断)" if len(out) > MAX_OUTPUT else "")


def _call_tool(tool, **params) -> str:
    """langchain 工具 → MCP 输出（工具返回即 str；异常转人话）"""
    try:
        out = tool.invoke(params)
    except Exception as e:
        return f"调用失败：{type(e).__name__}: {str(e)[:300]}"
    out = str(out)
    return out[:MAX_OUTPUT] + ("\n...(输出过长已截断)" if len(out) > MAX_OUTPUT else "")


async def create_plan(title: str, goal: str, steps: str) -> str:
    if _check_identity() is None:
        return _identity_hint("计划")
    from yuanai_core.tools.plan_tools import create_plan as _t
    return _call_tool(_t, title=title, goal=goal, steps=steps)


async def execute_plan(plan_id: int = 0) -> str:
    if _check_identity() is None:
        return _identity_hint("计划")
    from yuanai_core.tools.plan_tools import execute_plan as _t
    return _call_tool(_t, plan_id=int(plan_id or 0))


async def plan_status(plan_id: int = 0) -> str:
    if _check_identity() is None:
        return _identity_hint("计划")
    from yuanai_core.tools.plan_tools import get_plan_status as _t
    return _call_tool(_t, plan_id=int(plan_id or 0))


async def get_memory(query: str = "") -> str:
    if _check_identity() is None:
        return _identity_hint("记忆")
    from yuanai_core.tools.user_memory import get_user_memory as _t
    return _call_tool(_t, query=query or "")


async def remember(info: str) -> str:
    if _check_identity() is None:
        return _identity_hint("记忆")
    from yuanai_core.tools.user_memory import remember_user_info as _t
    return _call_tool(_t, info=info or "")


async def retrieve_planet_knowledge(query: str, planet: str = "") -> str:
    if _check_identity() is None:
        return _identity_hint("知识星球检索")
    from yuanai_core.tools.planet_tool import retrieve_planet_knowledge as _t
    return _call_tool(_t, query=query, planet=planet or "")


_chat_client_cache = {"client": None, "ident_sig": ""}


def _chat_client():
    """云端对话客户端（懒建 + 身份变化重建；token 懒取内置）"""
    ident = _check_identity()
    if ident is None:
        return None
    sig = f"{ident.get('server_url')}|{ident.get('agent_id')}"
    if _chat_client_cache["client"] is None or _chat_client_cache["ident_sig"] != sig:
        from agent.chat_client import CloudChatClient
        _chat_client_cache["client"] = CloudChatClient(
            ident["server_url"], ident["agent_id"], ident.get("agent_secret", ""))
        _chat_client_cache["ident_sig"] = sig
    return _chat_client_cache["client"]


async def cloud_chat(message: str, session_id: str = "", backend: str = "auto") -> str:
    """与小元AI 对话（云端统筹，与网站同一会话——默认主对话，发的消息网页
    立即可见；可选 session_id 指定会话；backend: auto/cloud/local）。"""
    if not (message or "").strip():
        return "请提供要发送的消息内容"
    client = _chat_client()
    if client is None:
        return _identity_hint("云端对话")
    _emit_pet("thinking")
    try:
        sid = (session_id or "").strip() or client.main_session_id()
        hist = client.load_messages(sid) or []
        # 与终端客户端同口径：history 剥掉末条用户消息（本轮 prompt 后端另发）
        msgs = [{"role": m.get("role") or "", "content": m.get("content") or ""}
                for m in hist]
        if msgs and msgs[-1].get("role") == "user":
            msgs = msgs[:-1]
        parts: list = []
        tools: list = []
        approval_denied = False
        async for ev in client.stream(sid, message, msgs, backend=backend):
            t = ev.get("type")
            if t == "token" and isinstance(ev.get("data"), str):
                parts.append(ev["data"])
            elif t == "tool_start":
                name = str((ev.get("data") or {}).get("name") or "未知工具")
                tools.append(name)
                _emit_pet("working", tool=name)
            elif t == "tool_end":
                _emit_pet("thinking")
            elif t == "approval":
                # MCP 无交互审批通道——默认拒绝（fail-closed，与平台 120s 超时
                # 同口径但立即决议，不干等）
                approval_denied = True
                did = (ev.get("data") or {}).get("decision_id", "")
                if did:
                    try:
                        await asyncio.to_thread(client.send_decision, did, False)
                    except Exception:
                        pass
            elif t == "error":
                raise RuntimeError(str(ev.get("data", ""))[:300])
        _emit_pet("idle")
        text = "".join(parts).strip()
        if not text:
            return "云端未返回回答（可能被停止或触发了内容安全拦截）"
        notes = []
        if tools:
            notes.append(f"工具调用 {len(tools)} 次：{', '.join(dict.fromkeys(tools))}")
        if approval_denied:
            notes.append("检测到需要审批的操作，已按默认拒绝（MCP 无交互审批通道）")
        out = text + ("\n\n" + "；".join(notes) if notes else "")
        return out[:MAX_OUTPUT] + ("\n...(输出过长已截断)" if len(out) > MAX_OUTPUT else "")
    except Exception as e:
        _emit_pet("error")
        return f"云端对话失败：{type(e).__name__}: {str(e)[:300]}"


def build_server() -> MCPServer:
    """组装小元AI 本地 MCP：发现 + 脚本调用 + A2 调用面"""
    server = MCPServer(name="xiaoyuan", description="小元AI 本地智能体——发现与调用（脚本/自动化/计划/记忆/知识星球/云端对话），跨系统执行")

    def list_local_agents() -> str:
        """发现本地智能体清单：统筹/自动化/脚本/计划/记忆/知识星球/云端对话/桌宠状态。"""
        lines = ["本地智能体（小元AI）：", ""]
        lines.append("- 统筹 Orchestrator：云端对话的本地执行者（意图路由 + 脚本直调），"
                    "经托盘 Agent 承载")
        lines.append("- 自动化 Agent：浏览器自动化（react 多步自主），run_automation 直调")
        lines.append("")
        lines.append(f"分析脚本（{len(_ANALYSIS.iter_handles())} 个）：")
        for h in _ANALYSIS.iter_handles():
            lines.append(f"  - script_{h.key}：{h.description or h.name}")
        lines.append(f"采集脚本（{len(_CRAWL.iter_handles())} 个）：")
        for h in _CRAWL.iter_handles():
            lines.append(f"  - script_{h.key}：{h.description or h.name}")
        lines.append("")
        lines.append("平台能力（经云端，需本机 Agent 已注册）：")
        lines.append("  - create_plan / execute_plan / plan_status：手机定计划、电脑执行")
        lines.append("  - get_memory / remember：用户长期记忆")
        lines.append("  - retrieve_planet_knowledge：个人知识星球检索")
        lines.append("  - cloud_chat：与小元AI 云端对话（与网站同一主对话）")
        if _check_identity() is None:
            lines.append("  注：本机尚未注册 Agent（上述工具需设备凭据），离线能力不受影响")
        try:
            from agent.pet_events import last_state
            pet = last_state() or "未运行"
        except Exception:
            pet = "未运行"
        lines.append("")
        lines.append(f"桌宠状态：{pet}")
        return "\n".join(lines)

    server.add_tool(list_local_agents)
    for h in _ANALYSIS.iter_handles():
        server.add_tool(_make_script_tool(h), description=h.description or h.name)
    for h in _CRAWL.iter_handles():
        server.add_tool(_make_script_tool(h), description=h.description or h.name)
    # A2 调用面
    server.add_tool(run_automation, description="浏览器自动化（react 多步自主 Agent，本机执行）：自动打开网页、填写表单、点击操作、截图监控等")
    server.add_tool(create_plan, description="创建可执行计划（手机定计划、电脑执行；只建草稿，用户说「执行」才运行）。steps 为 JSON 数组字符串，每步 {\"skill\":\"analysis|collection\",\"script\":\"可选脚本名\",\"desc\":\"自包含步骤描述\",\"params\":{}}")
    server.add_tool(execute_plan, description="把计划加入执行队列（本机 Agent 自动拉取执行）。plan_id: 0=最近一个草稿计划")
    server.add_tool(plan_status, description="查询计划状态与各步骤进度。plan_id: 0=最近一个计划")
    server.add_tool(get_memory, description="读取用户长期记忆（平台云端存储，与网站对话共用）。query 可选过滤关键词")
    server.add_tool(remember, description="追加一条用户长期记忆（事实性信息，追加不覆盖）")
    server.add_tool(retrieve_planet_knowledge, description="检索用户个人知识星球（思维导图与线性笔记，只读）。planet 可选限定星球名")
    server.add_tool(cloud_chat, description="与小元AI 云端对话（与网站同一主对话，消息两边同步可见）。session_id 可选指定会话；backend: auto/cloud/local")
    return server


if __name__ == "__main__":
    # stdio 循环（CC 以子进程拉起本模块，JSON-RPC 走 stdin/stdout；
    # mcp 2.x 的 run() 是同步入口，内部 anyio.run 管理事件循环）
    build_server().run()
