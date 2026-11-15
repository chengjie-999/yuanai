"""小元AI 本地 MCP 服务器测试（T13 A1，2026-11-15 大方向核心）。

协议层（JSON-RPC/stdio）由 mcp SDK 负责，这里测业务面：
工具清单/发现内容/动态签名/schema 透传/执行截断/桌宠联动/未知脚本报错。
不触发真实网络；脚本执行经 fake handle 注入。"""

import asyncio
import inspect

import agent.mcp_server as m


def test_build_server_tool_inventory():
    """11 个工具：list_local_agents + 9 分析脚本 + 1 采集脚本"""
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
