"""数据采集子 Agent：网页爬取 + 数据抓取"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from yuanai_core.core.lc import get_llm
from yuanai_core.tools.crawl_tools import (
    fetch_url, parse_html, save_crawl_data, list_crawl_data, get_crawl_detail,
)
from yuanai_core.tools.file_tools import save_data_csv, list_data_files, read_data_file

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是数据采集专家。

你可以使用以下工具：
- fetch_url：抓取指定网页的 HTML 内容
- parse_html：从 HTML 中提取结构化数据（表格、列表等）
- save_crawl_data：保存爬取结果
- list_crawl_data：列出所有已保存的爬取记录
- get_crawl_detail：查看某条爬取记录的详细信息
- save_data_csv：保存数据为 CSV 文件
- list_data_files / read_data_file：文件管理

工作流程：
1. 先用 fetch_url 获取目标网页
2. 用 parse_html 提取需要的数据
3. 用 save_data_csv 或 save_crawl_data 保存结果
4. 向用户报告采集到的数据条数和摘要"""


class CollectionAgent:
    def __init__(self):
        self._tools = [
            fetch_url, parse_html, save_crawl_data, list_crawl_data, get_crawl_detail,
            save_data_csv, list_data_files, read_data_file,
        ]

    def run(self, prompt: str) -> str:
        llm = get_llm("doubao-seed-2-0-lite-260215", temperature=0.3, verbose=False)
        agent = create_react_agent(llm, self._tools)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        try:
            result = agent.invoke({"messages": messages})
            return result["messages"][-1].content
        except Exception as e:
            logger.error("数据采集 Agent 异常: %s", e)
            return f"数据采集失败: {e}"
