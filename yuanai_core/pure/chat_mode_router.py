"""聊天模式自主路由（2026-10-22）— 关键词强信号（零成本）+ 豆包 lite 兜底判定

工作/娱乐双模式：每轮消息判定一次，**单向切换**——当前工作只找娱乐信号、
当前娱乐只找工作信号；信号抵消（score==0）保持现状。闲聊「谢谢」不误切、
来回横跳天然免疫。

判定两层：
1. 关键词打分（零成本）：work 信号 +1 / entertainment 信号 -1，绝大多数消息命中
2. 无信号且消息较长（≥8 字）→ 豆包 lite 一次判定（~1 token 输出，约 0.0001 元/次；
   环境变量 CHAT_MODE_ROUTER_LLM=0 关闭纯关键词）

判定产物供 /stream 消费：模式切换时回传 mode_event（前端分段开关跟随），
本轮 system 人设/桥接路由随之切换。
"""
from __future__ import annotations

import re

# 工作强信号（办事类：分析/任务/自动化/采集/文档）
WORK_SIGNALS = (
    "分析", "数据", "统计", "图表", "可视化", "报告", "表格", "清洗", "预处理",
    "回归", "聚类", "预测", "模型", "训练", "计划", "任务", "爬", "采集", "抓取",
    "自动化", "脚本", "代码", "编程", "开发", "部署", "测试", "服务器", "数据库",
    "接口", "医学", "文献", "基因", "药物", "知识库", "数据集", "审核", "检测",
    "浏览器", "下载", "解析", "计算", "汇总", "整理", "文档", "ppt", "excel",
    "需求", "方案", "工作", "项目", "指标", "监控", "日志", "bug",
)

# 娱乐强信号（陪伴类：闲聊/八卦/情感/玩梗/兴趣话题）
ENT_SIGNALS = (
    "聊天", "聊聊", "八卦", "吃瓜", "陪聊", "唠", "梗", "开玩笑", "笑话", "段子",
    "明星", "歌手", "演员", "偶像", "电视剧", "电影", "综艺", "动漫", "动画",
    "游戏", "音乐", "听歌", "唱歌", "情感", "恋爱", "对象", "表白", "分手", "失恋",
    "心情", "烦", "郁闷", "无聊", "摸鱼", "逛街", "美食", "餐厅", "旅游", "拍照",
    "穿搭", "化妆", "星座", "算命", "塔罗", "运势", "宠物", "猫", "狗", "吵架",
    "安慰", "哄", "夸我", "可爱", "帅", "女神", "男神", "吃了吗", "在吗", "晚安",
    "早安", "讲个", "故事", "小说",
)


def _score(text: str) -> int:
    """work 信号 +1 / 娱乐信号 -1；返回净得分（>0 偏工作，<0 偏娱乐，0 无信号）"""
    score = 0
    for w in WORK_SIGNALS:
        score += text.count(w)
    for w in ENT_SIGNALS:
        score -= text.count(w)
    return score


def _llm_judge(text: str) -> str | None:
    """豆包 lite 一次判定（输出 1 词）。失败返回 None（保持现状）"""
    try:
        from config.settings import CHAT_MODE_ROUTER_MODEL
        from yuanai_core.core.lc import get_llm

        llm = get_llm(CHAT_MODE_ROUTER_MODEL, reasoning=False, temperature=0, max_tokens=8)
        # 静态前缀放前面——上下文缓存友好（DeepSeek/豆包前缀缓存命中）
        resp = llm.invoke([("system", (
            "你是对话模式路由器。判断这条用户消息属于哪种对话模式，只回复一个词：\n"
            "「work」=工作助手类（数据分析/任务计划/自动化/采集/文档处理等办事诉求）；\n"
            "「entertainment」=娱乐陪伴类（闲聊/八卦/情感/玩梗等陪伴诉求）。\n"
            "拿不准回复「keep」。")),
            ("human", text)])
        out = str(resp.content if hasattr(resp, "content") else resp).strip().lower()
        if "entertainment" in out:
            return "entertainment"
        if "work" in out:
            return "work"
        return None
    except Exception:
        return None


def route_chat_mode(text: str, current_mode: str, llm_fallback: bool | None = None) -> str:
    """判定本轮消息的聊天模式：'work' 或 'entertainment'。

    current_mode: 当前模式（'work'/'entertainment'）——单向切换：只在与当前
    相反的信号占优时切换，信号抵消或无信号保持现状。
    llm_fallback: None → 读 settings.CHAT_MODE_ROUTER_LLM。
    """
    text = re.sub(r"\s+", "", text or "")
    if not text:
        return current_mode

    score = _score(text)
    if score > 0:
        return "work"
    if score < 0:
        return "entertainment"

    # 无强信号：短消息保持现状；较长消息用 LLM 兜底判定（默认开，可 env 关闭）
    if len(text) < 8:
        return current_mode
    if llm_fallback is None:
        from config.settings import CHAT_MODE_ROUTER_LLM
        llm_fallback = CHAT_MODE_ROUTER_LLM
    if not llm_fallback:
        return current_mode
    judged = _llm_judge(text)
    return judged if judged in ("work", "entertainment") else current_mode
