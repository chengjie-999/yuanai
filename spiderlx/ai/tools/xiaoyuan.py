from typing import Any, Dict, List, Optional, Type

from langchain.tools import BaseTool, StructuredTool, tool
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.pydantic_v1 import BaseModel, Field

# 导入原有模块中的 SeleniumXiaoYuan 类
from spiderlx.auto.web.selenium.xiaoyuan.xiaoyuan import SeleniumXiaoYuan  # 请将 your_original_module 替换为实际的模块名
from selenium.webdriver.chrome.webdriver import WebDriver


# ====================== 工具输入参数模型 ======================
class StartTaskInput(BaseModel):
    """开始任务的输入参数模型"""
    card: Any = Field(description="任务卡片元素对象")


class HomeInput(BaseModel):
    """主页操作的输入参数模型"""
    like: str = Field(default="单题标答-审核", description="想要匹配的任务名称关键词")


class GoQuestionInput(BaseModel):
    """处理任务的输入参数模型"""
    name: str = Field(description="任务名称")
    true: str = Field(default="1", description="是否标记为正确")
    up: bool = Field(default=False, description="是否调整题目大小")


class CompeteInput(BaseModel):
    """提交任务的输入参数模型"""
    status: str = Field(description="任务状态")
    cause: Optional[str] = Field(default=None, description="驳回理由")


class QuestionResizeInput(BaseModel):
    """调整题目大小的输入参数模型"""
    down: bool = Field(default=True, description="是否缩小（True=缩小，False=放大）")
    count: int = Field(default=6, description="点击缩放按钮的次数")


# ====================== LangChain 工具类 ======================
class SeleniumXiaoYuanToolkit:
    """小猿众包 Selenium 操作的 LangChain 工具集"""

    def __init__(self, web_driver: WebDriver):
        """
        初始化工具集

        Args:
            web_driver: Chrome WebDriver 实例
        """
        self.xiaoyuan = SeleniumXiaoYuan(web_driver)
        self.tools = self._get_all_tools()

    def _get_all_tools(self) -> List[BaseTool]:
        """获取所有可用的 LangChain 工具"""
        return [
            # 基础操作工具
            StructuredTool.from_function(
                func=self.get_html,
                name="get_html",
                description="获取当前页面的 HTML 源码并保存",
            ),
            StructuredTool.from_function(
                func=self.start_task,
                name="start_task",
                description="点击任务卡片开始任务",
                args_schema=StartTaskInput,
            ),
            StructuredTool.from_function(
                func=self.get_home_tasks,
                name="get_home_tasks",
                description="获取小猿众包主页的所有任务卡片",
                args_schema=HomeInput,
            ),
            # 任务处理工具
            StructuredTool.from_function(
                func=self.process_question,
                name="process_question",
                description="处理不同类型的任务（单题标答审核、改错补答、抄写图形题审核等）",
                args_schema=GoQuestionInput,
            ),
            StructuredTool.from_function(
                func=self.go_back_home,
                name="go_back_home",
                description="返回小猿众包首页",
            ),
            StructuredTool.from_function(
                func=self.submit_task,
                name="submit_task",
                description="提交任务（支持提交领下一任务、提交回首页、整题驳回等）",
                args_schema=CompeteInput,
            ),
            # 题目调整工具
            StructuredTool.from_function(
                func=self.resize_question,
                name="resize_question",
                description="放大或缩小单题标答审核的题目",
                args_schema=QuestionResizeInput,
            ),
            StructuredTool.from_function(
                func=self.restore_question,
                name="restore_question",
                description="将题目恢复到正常大小",
            ),
            # 其他辅助工具
            StructuredTool.from_function(
                func=self.confirm_rejection,
                name="confirm_rejection",
                description="确认驳回操作",
            ),
            StructuredTool.from_function(
                func=self.handle_task_box,
                name="handle_task_box",
                description="处理任务消息提示框（如任务包处理完毕提示）",
            ),
            StructuredTool.from_function(
                func=self.enter_question_detail,
                name="enter_question_detail",
                description="进入抄写题目的详情页面",
            ),
            StructuredTool.from_function(
                func=self.close_question_detail,
                name="close_question_detail",
                description="关闭抄写题目的详情页面并保存",
            ),
            StructuredTool.from_function(
                func=self.get_question_info,
                name="get_question_info",
                description="获取题目的标记答案和参考答案，支持截图保存",
            ),
        ]

    # ====================== 工具函数实现（一一映射原有方法） ======================
    def get_html(self, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """获取页面HTML并保存"""
        self.xiaoyuan.get_html()
        return "成功获取并保存页面HTML"

    def start_task(self, card: Any, run_manager: Optional[CallbackManagerForToolRun] = None) -> bool:
        """开始任务"""
        result = self.xiaoyuan.start(card)
        return result

    def get_home_tasks(self, like: str = "单题标答-审核", run_manager: Optional[CallbackManagerForToolRun] = None) -> Dict[
        str, Any]:
        """获取主页任务卡片"""
        task_cards = self.xiaoyuan.home(like)
        return {
            "task_count": len(task_cards),
            "tasks": list(task_cards.keys()),
            "task_elements": task_cards
        }

    def process_question(self, name: str, true: str = "1", up: bool = False,
                         run_manager: Optional[CallbackManagerForToolRun] = None) -> List[str]:
        """处理题目"""
        result = self.xiaoyuan.go_question(name, true, up)
        return result if result else ["任务处理完成"]

    def go_back_home(self, run_manager: Optional[CallbackManagerForToolRun] = None) -> bool:
        """返回首页"""
        result = self.xiaoyuan.go_home()
        return result

    def submit_task(self, status: str, cause: Optional[str] = None,
                    run_manager: Optional[CallbackManagerForToolRun] = None) -> bool:
        """提交任务"""
        result = self.xiaoyuan.compete(status, cause)
        return result

    def resize_question(self, down: bool = True, count: int = 6,
                        run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """调整题目大小"""
        self.xiaoyuan.question_resize(down, count)
        return f"已{'缩小' if down else '放大'}题目{count}次"

    def restore_question(self, run_manager: Optional[CallbackManagerForToolRun] = None) -> bool:
        """恢复题目大小"""
        result = self.xiaoyuan.question_restore()
        return result

    def confirm_rejection(self, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """确认驳回"""
        result = self.xiaoyuan.rejection_confirmation()
        return f"驳回确认完成，按钮文本：{result}"

    def handle_task_box(self, go_on: bool = True, run_manager: Optional[CallbackManagerForToolRun] = None) -> bool:
        """处理提示框"""
        result = self.xiaoyuan.box(go_on)
        return result

    def enter_question_detail(self, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """进入题目详情"""
        self.xiaoyuan.to_detail()
        return "已进入题目详情页面"

    def close_question_detail(self, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """关闭题目详情"""
        self.xiaoyuan.close_detail()
        return "已关闭题目详情页面并保存"

    def get_question_info(self, screenshot: bool = True,
                          run_manager: Optional[CallbackManagerForToolRun] = None) -> List[Any]:
        """获取题目信息"""
        result = self.xiaoyuan.question_info(screenshot)
        return result


def get_tools(web_driver: WebDriver):
    # 初始化小猿工具集
    xiaoyuan_toolkit = SeleniumXiaoYuanToolkit(web_driver)

    # 获取所有工具（可用于 LangChain Agent）
    tools = xiaoyuan_toolkit.tools
    return xiaoyuan_toolkit, tools


# ====================== 使用示例 ======================
def example_usage():
    """工具集使用示例"""
    # 1. 初始化 WebDriver（请根据你的实际配置调整）
    from selenium import webdriver
    driver = webdriver.Chrome()
    xiaoyuan_toolkit = get_tools(driver)[0]
    # 4. 直接调用工具方法（示例）
    try:
        # 访问小猿众包网站
        driver.get("https://xiaoyuan.zhipin.com/")

        # 获取主页任务
        tasks = xiaoyuan_toolkit.get_home_tasks(like="单题标答-审核")
        print(f"找到 {tasks['task_count']} 个任务：")
        for task_name in tasks['tasks']:
            print(f"- {task_name}")

        # 如果有任务，选择第一个任务开始
        if tasks['task_count'] > 0:
            first_task_name = tasks['tasks'][0]
            first_task_card = tasks['task_elements'][first_task_name]
            start_result = xiaoyuan_toolkit.start_task(first_task_card)
            print(f"开始任务结果：{start_result}")

            # 处理题目
            process_result = xiaoyuan_toolkit.process_question(first_task_name)
            print(f"处理题目结果：{process_result}")

            # 提交任务
            submit_result = xiaoyuan_toolkit.submit_task("提交领下一任务")
            print(f"提交任务结果：{submit_result}")

    finally:
        # 关闭浏览器
        driver.quit()


if __name__ == "__main__":
    example_usage()
