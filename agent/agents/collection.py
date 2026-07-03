"""数据采集 Agent：LLM 意图匹配 → 派发爬虫脚本"""
from agent.agents.base import ScriptDispatchAgent
from config.settings import AGENT_MODEL_MAP


class CollectionAgent(ScriptDispatchAgent):
    name = "collection"
    script_dir = "agent/datanalysis/crawl"
    model_name = AGENT_MODEL_MAP["collection"]

    system_prompt = """你是数据采集专家。根据用户需求，从可用操作中选择最合适的，提取参数。

返回 JSON 格式（只返回 JSON，不要其他文字）：
{"script": "脚本名", "params": {"参数名": "值"}}
如果无法匹配任何操作，返回：
{"script": null, "reason": "原因"}
如果用户没提供必要的参数（如 URL），先在 reason 中说明要用户补充什么，不要直接选脚本。
如果用户提供了一个 URL 想快速看一下内容，用 "builtin_fetch_url"。"""

    builtins = {
        "builtin_fetch_url": "抓取指定网页内容，参数 url",
        "builtin_parse_html": "解析 HTML 提取标题/正文/链接，参数 html",
        "builtin_save_crawl_data": "保存爬取数据到文件和数据库，参数 url, data",
        "builtin_list_crawl_data": "列出爬取历史记录",
        "builtin_get_crawl_detail": "查看单条爬取记录完整内容，参数 record_id",
    }

    def _dispatch_builtin(self, name: str, params: dict) -> str:
        from yuanai_core.tools.crawl_tools import (
            fetch_url, parse_html, save_crawl_data, list_crawl_data, get_crawl_detail,
        )

        handlers = {
            "builtin_fetch_url": lambda: fetch_url.invoke(
                {"url": params.get("url", ""), "retype": params.get("retype", "text")}
            ),
            "builtin_parse_html": lambda: parse_html.invoke(
                {"html": params.get("html", "")}
            ),
            "builtin_save_crawl_data": lambda: save_crawl_data.invoke(
                {"url": params.get("url", ""), "data": params.get("data", ""),
                 "data_type": params.get("data_type", "text")}
            ),
            "builtin_list_crawl_data": lambda: list_crawl_data.invoke(
                {"page": params.get("page", 1), "limit": params.get("limit", 10)}
            ),
            "builtin_get_crawl_detail": lambda: get_crawl_detail.invoke(
                {"record_id": params.get("record_id", 0)}
            ),
        }
        handler = handlers.get(name)
        return handler() if handler else f"未知内置操作: {name}"
