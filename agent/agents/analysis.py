"""数据分析子 Agent：pandas 统计 + matplotlib 图表"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from yuanai_core.core.lc import get_llm
from yuanai_core.tools.data_tools import list_datasets, preview_dataset, analyze_dataset
from yuanai_core.tools.calculator import calculate_sum, calculate_multiply
from yuanai_core.tools.file_tools import save_data_csv, list_data_files, read_data_file

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是数据分析专家。

你可以使用以下工具：
- list_datasets：列出所有可用数据集
- preview_dataset：预览数据集前 N 行
- analyze_dataset：对数据集执行完整分析（统计描述 + 图表生成）
- calculate_sum / calculate_multiply：精确计算
- list_data_files / read_data_file / save_data_csv：文件管理

工作流程：
1. 如果用户提到了具体的文件名，先 list_datasets 确认文件存在
2. 用 preview_dataset 了解数据结构
3. 用 analyze_dataset 执行分析
4. 解读分析结果，用中文向用户说明关键发现
5. 如需保存结果，用 save_data_csv"""


class AnalysisAgent:
    def __init__(self):
        self._tools = [
            list_datasets, preview_dataset, analyze_dataset,
            calculate_sum, calculate_multiply,
            list_data_files, read_data_file, save_data_csv,
        ]

    def run(self, prompt: str) -> str:
        llm = get_llm("doubao-seed-2-0-pro-260215", temperature=0.3, verbose=False)
        agent = create_react_agent(llm, self._tools)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        try:
            result = agent.invoke({"messages": messages})
            return result["messages"][-1].content
        except Exception as e:
            logger.error("数据分析 Agent 异常: %s", e)
            return f"数据分析失败: {e}"
