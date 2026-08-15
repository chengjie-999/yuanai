"""
零成本意图分类器 — 关键词匹配 + LLM 降级（仅低置信度时调用 mini LLM）

设计原则：
1. 关键词匹配 100% 零 API 成本
2. 高置信度 (>2 关键词命中) 直接返回结果
3. 低置信度时才降级到 mini LLM（不带工具，token 极少）
4. 直接命令（如 "200+300"）绕过 LLM 直接执行
"""

import re
from typing import List, Optional, Dict, Tuple


class IntentMatch:
    """意图分类结果"""

    def __init__(self, group: str, confidence: float, is_direct: bool = False):
        self.group = group
        self.confidence = confidence  # 0.0 - 1.0
        self.is_direct = is_direct    # True = 跳过 LLM，直接执行工具

    def __repr__(self):
        return f"IntentMatch({self.group}, conf={self.confidence:.2f}, direct={self.is_direct})"


# 意图 → 工具类别映射
INTENT_TOOL_GROUPS: Dict[str, List[str]] = {
    "simple_query":           ["general"],
    "data_task":              ["data", "file", "stats", "general"],
    "crawl_task":             ["crawl", "file", "general"],
    "memory_task":            ["memory", "knowledge", "general"],
    "knowledge_q":            ["knowledge", "general"],
    "delegate_analysis":      ["general", "delegate_analysis"],
    "delegate_collection":    ["general", "delegate_collection"],
    "delegate_automation":    ["general", "delegate_automation"],
    "delegate_claude":        ["general", "delegate_claude"],
    "general_chat":           ["general", "memory", "knowledge", "delegate_all"],
}

# 每个意图的中英文关键词
_KEYWORDS: Dict[str, set] = {
    "calculate":             {"计算", "加", "减", "乘", "除", "求和", "平均数",
                               "百分比", "sum", "average", "+", "-", "×", "÷",
                               "算一下", "等于多少", "多少加多少"},
    "weather":               {"天气", "气温", "温度", "下雨", "台风", "weather",
                               "多少度", "冷不冷", "热不热", "forecast"},
    "time":                  {"时间", "日期", "今天", "明天", "星期", "几点",
                                "几号", "time", "date", "现在"},
    "convert":               {"换算", "单位", "转换", "厘米", "公斤", "千克",
                               "convert", "公里", "英里", "平方", "华氏", "摄氏"},
    "data_task":             {"数据", "数据集", "分析", "统计", "图表", "dataset",
                               "csv", "列", "表格", "预览", "describe", "文件",
                               "有几行", "有几列", "什么类型", "查看数据"},
    "crawl_task":            {"爬虫", "爬取", "抓取", "网页", "url", "html",
                               "网址", "crawl", "fetch", "采集", "网站",
                               "打开链接", "获取内容", "解析"},
    "memory_task":           {"记住", "记忆", "我叫", "我的", "memory", "remember",
                               "别忘了", "保存下来"},
    "knowledge_q":           {"知识库", "检索", "搜索", "retrieve", "查找",
                               "相关知识"},
    "delegate_analysis":     {"复杂分析", "回归", "rfm", "基因", "客户分群",
                               "流失预测", "分类数据", "生物信息", "相关性",
                               "热力图", "3d散点", "火山图", "roc", "聚类"},
    "delegate_collection":   {"大量采集", "批量", "自动采集", "数据采集"},
    "delegate_automation":   {"浏览器", "审核", "自动化", "截图", "xiaoyuan",
                               "启动浏览器", "打开网页", "操控", "题目审核",
                               "打开chrome", "start browser"},
    "delegate_claude":       {"claude", "code", "写代码", "改代码", "编程",
                               "终端命令", "命令行", "本地运行", "git", "重构",
                               "修bug", "修复bug", "实现功能", "跑命令",
                               "运行测试", "本地文件", "仓库"},
}

# 直接命令正则（匹配后跳过 LLM）
_DIRECT_PATTERNS: List[Tuple[str, str, str]] = [
    # (pattern, tool_name, description)
    # 纯加法
    (r'^[\d\s\.\,，]+[\+＋][\d\s\.\,，]+$', "calculate_sum", "calc"),
    # 纯减法
    (r'^[\d\s\.\,，]+[\-－][\d\s\.\,，]+$', "calculate_sum", "calc"),
    # 纯乘法
    (r'^[\d\s\.\,，]+[\*×][\d\s\.\,，]+$', "calculate_multiply", "calc"),
    # 纯除法
    (r'^[\d\s\.\,，]+[\/÷][\d\s\.\,，]+$', "calculate_divide", "calc"),
    # 今天星期几
    (r'(今天|今天是个?|现在)星期几', "get_weekday", "get_weekday"),
    # 现在几点
    (r'^(现在几点|几点了|当前时间)$', "get_current_time", "get_current_time"),
]


class IntentClassifier:
    """零成本意图分类器"""

    def classify(self, message: str) -> IntentMatch:
        """关键词匹配 → IntentMatch。低置信度时 group='general_chat'。"""
        if not message.strip():
            return IntentMatch("general_chat", 0.0)

        # Step 1: 直接命令匹配
        msg = message.strip().replace(" ", "").replace("　", "")
        direct = self._match_direct(msg)
        if direct:
            return direct

        # Step 2: 关键词打分
        scores = {}
        for intent, keywords in _KEYWORDS.items():
            hit = sum(1 for kw in keywords if kw.lower() in msg.lower())
            if hit > 0:
                scores[intent] = hit

        if not scores:
            return IntentMatch("general_chat", 0.0)

        # Step 3: 取最高分意图
        best = max(scores, key=scores.get)
        best_score = scores[best]
        total = sum(scores.values())
        confidence = best_score / max(total, 1)

        # 合并简单查询
        if best in ("calculate", "weather", "time", "convert") and confidence >= 0.3:
            return IntentMatch("simple_query", confidence)

        if confidence >= 0.4:
            return IntentMatch(best, confidence)

        return IntentMatch("general_chat", confidence)

    def _match_direct(self, msg: str) -> Optional[IntentMatch]:
        """匹配直接命令模式。"""
        for pattern, tool_name, group in _DIRECT_PATTERNS:
            if re.match(pattern, msg, re.IGNORECASE):
                return IntentMatch("direct", 1.0, is_direct=True)
        return None

    @staticmethod
    def get_tool_categories(intent: IntentMatch) -> List[str]:
        """获取应加载的工具类别列表。"""
        if intent.is_direct:
            return ["general"]
        return INTENT_TOOL_GROUPS.get(intent.group, ["general"])

    @staticmethod
    def needs_fallback_llm(intent: IntentMatch) -> bool:
        """是否需要降级 LLM 分类。"""
        return intent.confidence < 0.4 or intent.group == "general_chat"


# 降级 LLM 分类提示词（仅在高置信度失败时使用，无工具调用，token 极省）
LLM_CLASSIFIER_PROMPT = """Classify this user message into ONE category. Reply ONLY with the category name.

Categories:
simple_query - calculation, weather, datetime, unit conversion
data_task - dataset, statistics, analysis, preview
crawl_task - web scraping, URL fetching, HTML parsing
memory_task - remember/recall user personal info
knowledge_q - knowledge base search
delegate_analysis - complex data analysis needing sub-agent
delegate_collection - massive crawling needing sub-agent
delegate_automation - browser control, auditing, automation
delegate_claude - coding, writing/modifying code, terminal commands, git, local file creation

Message: {message}
Category:"""


# 全局单例
classifier = IntentClassifier()
