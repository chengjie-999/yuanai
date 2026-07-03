"""自动化子 Agent：浏览器控制 + 题目审核 + 截图监控"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from yuanai_core.core.lc import get_llm
from agent.tools import load_agent_tools
from agent.agents.base import AgentBase
from config.settings import AGENT_MODEL_MAP

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是自动化操作专家，负责浏览器控制和题目审核。

你可以使用以下工具：
【浏览器基础操作】
- launch_new_browser / close_browser：启动/关闭浏览器
- get_website_info / open_website_by_code / open_website_by_name / open_custom_url：打开网页
- get_browser_status / get_current_url：查看浏览器状态
- refresh_page / load_cookies / save_cookies：页面操作
- take_browser_screenshot / take_screenshot：截图

【小猿众包题目审核（18个工具）】
- get_task_cards / start_task：查看和开始审核任务
- get_question_info：获取题目截图和参考信息
- scroll_canvas / click_canvas：滚动画布查看更多内容
- zoom_question / restore_question_view：缩放题目
- mark_question_correct：标记正确
- submit_task / confirm_rejection：提交或驳回
- get_page_status / go_home / save_page_html：页面辅助
- load_page_cookies / save_page_cookies：登录状态管理

【审核知识库】
- retrieve_annotation_spec：检索标注规范
- retrieve_audit_steps：检索操作步骤
- save_audit_feedback / get_audit_feedback：保存/查看反馈
- analyze_audit_errors：分析错误分布

工作流程（审核任务）：
1. 调用 get_page_status 了解当前页面状态
2. 如在小猿众包首页，调用 get_task_cards 获取任务列表
3. 调用 start_task 开始审核
4. 调用 get_question_info 获取题目截图
5. 用 scroll_canvas 滚动查看完整题目（可能需要多次）
6. 调用 retrieve_annotation_spec 检索相关标注规范
7. 根据规范判断标注是否正确
8. 调用 mark_question_correct 或 submit_task 处理
9. 循环处理下一题"""


class AutomationAgent(AgentBase):
    name = "automation"
    model_name = AGENT_MODEL_MAP["automation"]

    def __init__(self):
        super().__init__()
        self._tools = None

    @property
    def tools(self):
        if self._tools is None:
            self._tools = load_agent_tools()
        return self._tools

    def run(self, prompt: str) -> str:
        llm = get_llm("doubao-seed-2-0-pro-260215", temperature=0.3, verbose=False)
        agent = create_react_agent(llm, self.tools)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        try:
            result = agent.invoke({"messages": messages})
            return result["messages"][-1].content
        except Exception as e:
            logger.error("自动化 Agent 异常: %s", e)
            return f"自动化操作失败: {e}"
