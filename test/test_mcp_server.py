"""小元AI 本地 MCP 服务器测试（T13 A1，2026-11-15 大方向核心）。

协议层（JSON-RPC/stdio）由 mcp SDK 负责，这里测业务面：
工具清单/发现内容/动态签名/schema 透传/执行截断/桌宠联动/未知脚本报错。
不触发真实网络；脚本执行经 fake handle 注入。"""

import asyncio
import inspect

import agent.mcp_server as m


def test_build_server_tool_inventory():
    """19 个工具：list_local_agents + 10 脚本 + 8 A2 调用面"""
    server = m.build_server()

    async def _run():
        tools = await server.list_tools()
        names = [t.name for t in tools]
        assert names[0] == "list_local_agents"
        assert len([n for n in names if n.startswith("script_")]) == 10
        # 关键脚本在场
        for key in ("script_descriptive_stats", "script_correlation",
                    "script_generic_crawl"):
            assert key in names
        # A2 调用面（2026-11-18）
        for key in ("run_automation", "create_plan", "execute_plan",
                    "plan_status", "get_memory", "remember",
                    "retrieve_planet_knowledge", "cloud_chat"):
            assert key in names
    asyncio.run(_run())


def test_list_local_agents_discovers_agents():
    server = m.build_server()

    async def _run():
        res = await server.call_tool("list_local_agents", {})
        text = res.content[0].text
        assert "统筹 Orchestrator" in text
        assert "自动化 Agent" in text
        assert "分析脚本（9 个）" in text
        assert "script_descriptive_stats" in text
        assert "桌宠状态" in text
    asyncio.run(_run())


def test_list_local_agents_mentions_a2_capabilities():
    server = m.build_server()

    async def _run():
        res = await server.call_tool("list_local_agents", {})
        text = res.content[0].text
        assert "run_automation 直调" in text
        assert "create_plan / execute_plan / plan_status" in text
        assert "cloud_chat" in text
        assert "知识星球" in text
    asyncio.run(_run())


def test_cloud_tools_without_identity_give_hint(monkeypatch):
    """未注册 Agent → 云端依赖工具给注册引导（离线能力不受影响）"""
    from yuanai_core.pure import agent_remote
    monkeypatch.setattr(agent_remote, "read_identity", lambda: {})

    async def _run():
        for fn, kwargs in ((m.create_plan, {"title": "t", "goal": "g", "steps": "[]"}),
                           (m.execute_plan, {}),
                           (m.plan_status, {}),
                           (m.get_memory, {}),
                           (m.remember, {"info": "x"}),
                           (m.retrieve_planet_knowledge, {"query": "q"}),
                           (m.cloud_chat, {"message": "hi"})):
            out = await fn(**kwargs)
            assert "本机未注册小元AI Agent" in out, out
            assert "本地 Agent 下载" in out
    asyncio.run(_run())


def test_memory_tool_passthrough(monkeypatch):
    """记忆工具透传底层 langchain 工具（身份存在时不拦截）"""
    from yuanai_core.pure import agent_remote
    monkeypatch.setattr(agent_remote, "read_identity",
                        lambda: {"agent_id": "1", "server_url": "wss://cjyuanai.cn",
                                 "agent_secret": "s"})

    class FakeMem:
        def invoke(self, params):
            return "记忆内容A"
    monkeypatch.setattr("yuanai_core.tools.user_memory.get_user_memory",
                        FakeMem(), raising=False)
    import yuanai_core.tools.user_memory as um
    monkeypatch.setattr(um, "get_user_memory", FakeMem())
    out = asyncio.run(m.get_memory(query="x"))
    assert out == "记忆内容A"


def test_cloud_chat_collects_stream_and_denies_approval(monkeypatch):
    """cloud_chat：流收集 token/工具名；审批默认拒绝（fail-closed）"""
    from yuanai_core.pure import agent_remote
    monkeypatch.setattr(agent_remote, "read_identity",
                        lambda: {"agent_id": "1", "server_url": "wss://cjyuanai.cn",
                                 "agent_secret": "s"})

    class FakeClient:
        denied = []

        def main_session_id(self):
            return "sid-1"

        def load_messages(self, sid):
            return [{"role": "user", "content": "旧问题"},
                    {"role": "assistant", "content": "旧回答"},
                    {"role": "user", "content": "本轮消息"}]

        async def stream(self, sid, prompt, history, backend="auto"):
            assert sid == "sid-1"
            assert prompt == "新问题"
            assert history[-1]["content"] == "旧回答"  # 末条用户消息已剥
            yield {"type": "token", "data": "你好"}
            yield {"type": "tool_start", "data": {"name": "search_web"}}
            yield {"type": "approval", "data": {"decision_id": "d1"}}
            yield {"type": "token", "data": "！"}

        def send_decision(self, did, approve):
            self.denied.append((did, approve))

    fake = FakeClient()
    monkeypatch.setattr(m, "_chat_client", lambda: fake)
    out = asyncio.run(m.cloud_chat("新问题"))
    assert out == "你好！\n\n工具调用 1 次：search_web；检测到需要审批的操作，已按默认拒绝（MCP 无交互审批通道）"
    assert fake.denied == [("d1", False)]


def test_cloud_chat_empty_message():
    assert "请提供" in asyncio.run(m.cloud_chat(""))


def test_dynamic_script_signature_from_decl():
    """脚本工具签名来自 __script_params__ 声明（与 registry 校验同源）"""
    from agent.scripts.registry import ScriptRegistry
    reg = ScriptRegistry("agent/datanalysis/scripts", skill="analysis")
    handles = list(reg.iter_handles())
    rfm = next(h for h in handles if h.key == "rfm_cluster")
    fn = m._make_script_tool(rfm)
    assert fn.__name__ == "script_rfm_cluster"
    sig = inspect.signature(fn)
    assert "file_path" in sig.parameters
    assert "user_info_path" in sig.parameters
    # 声明的类型映射进签名（path 类型 → str；exec 继承模块 future 注解故为
    # 字符串形式，mcp SDK 的 schema 生成两者皆可——已实测 input_schema 正确）
    assert sig.parameters["file_path"].annotation in (str, "str")


def test_invoke_script_passthrough_and_truncation(monkeypatch):
    """执行透传 fake handle：参数非空过滤 + 输出截断 + 成功返回"""
    class FakeHandle:
        key = "test_key"
        name = "测试脚本"
        description = "测试"

        def __init__(self):
            self.calls = []

        def run(self, **params):
            self.calls.append(params)
            return "x" * (m.MAX_OUTPUT + 100)

    handle = FakeHandle()
    monkeypatch.setattr(m, "_handle_of", lambda name: handle)
    # 桌宠联动静默（文件协议写失败静默——这里直接验证不抛）
    out = asyncio.run(m._invoke_script("测试脚本", file_path=None, label_col="a"))
    assert handle.calls == [{"label_col": "a"}]  # None 参数被过滤
    assert out.endswith("...(输出过长已截断)")
    assert len(out) == m.MAX_OUTPUT + len("\n...(输出过长已截断)")


def test_invoke_script_unknown_name():
    monkeypatch = None  # 未注册脚本名 → 人话报错
    assert "未知脚本" in asyncio.run(m._invoke_script("不存在的脚本"))


def test_invoke_script_error_reported(monkeypatch):
    """执行异常 → 人话报错（类型 + 截断）"""
    class BoomHandle:
        key = "boom"
        name = "坏脚本"

        def run(self, **params):
            raise RuntimeError("boom" * 100)

    monkeypatch.setattr(m, "_handle_of", lambda name: BoomHandle())
    out = asyncio.run(m._invoke_script("坏脚本"))
    assert out.startswith("执行失败：RuntimeError:")
    assert len(out) <= 260
