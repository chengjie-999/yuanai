from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class TaskResult:
    success: bool
    summary: str                           # 给用户看的文字摘要
    data: Any = None                       # 结构化结果，供后续处理
    files: List[str] = field(default_factory=list)   # 生成的文件路径


class BaseScript:
    """每个任务脚本继承此类，实现 name / description / run 三个成员。

    name: str         — 脚本标识，LLM 用来匹配（如 "crawl_product_list"）
    description: str  — 功能描述，给 LLM 看的（如 "爬取 example.com 产品列表"）
    """

    name: str = ""
    description: str = ""

    def run(self, **params) -> TaskResult:
        raise NotImplementedError
