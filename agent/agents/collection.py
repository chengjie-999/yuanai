"""数据采集 Agent：LLM 意图匹配 → 派发爬虫脚本。
配置从 skills/collection/skill.yaml 加载。"""

from agent.agents.base import ScriptDispatchAgent
from skills import skill_registry


class CollectionAgent(ScriptDispatchAgent):
    def __init__(self):
        super().__init__(skill_registry.get("collection"))

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
