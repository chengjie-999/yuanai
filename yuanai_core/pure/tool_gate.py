# -*- coding: utf-8 -*-
"""工具动作分级 gate（V1-2 审批分层，2026-11-05）

云端直连工具链的动作护栏（本地 Agent 有独立审批/护栏体系，不经此 gate）：
- L0 只读直执行
- L1 可逆写直执行（配合写入校验）
- L2 不可逆需确认（SSE 审批卡，用户 approve 才执行；超时/拒绝 = deny fail-closed）
- L3 高危强制拦截，仅人工操作
**未登记工具默认 L3**（fail-closed）——新增工具必须在此登记，否则云端直连不可用。

单一事实源：加新工具先在这里补一行登记。
"""

LEVEL_L0 = "L0"  # 只读直执行
LEVEL_L1 = "L1"  # 可逆写直执行（写入校验）
LEVEL_L2 = "L2"  # 不可逆需确认（审批卡）
LEVEL_L3 = "L3"  # 高危拦截仅人工

# 只读工具（无副作用：查询/计算/检索/预览）
_L0 = {
    "add_days", "analyze_dataset", "assess_drug_feasibility", "calculate_average",
    "calculate_date_diff", "calculate_divide", "calculate_multiply",
    "calculate_percentage", "calculate_sum", "check_url", "convert_area",
    "convert_length", "convert_temperature", "convert_weight", "correlate_columns",
    "count_words", "describe_column", "extract_html_table", "extract_numbers",
    "fetch_url", "format_json", "get_article_detail", "get_crawl_detail",
    "get_current_time", "get_plan_status", "get_species_info", "get_system_stats",
    "get_today_weather", "get_tomorrow_forecast", "get_user_memory", "get_weekday",
    "list_crawl_data", "list_data_files", "list_datasets", "parse_html",
    "preview_dataset", "read_data_file", "retrieve_knowledge",
    "retrieve_planet_knowledge", "search_clinical_trials", "search_pubmed",
    "search_web", "text_to_table",
}

# 可逆写（执行 + 校验 / 用户可在界面撤销）
_L1 = {
    "create_plan",          # 只建草稿不执行，可删
    "remember_user_info",   # 记忆追加，设置页可删
    "save_crawl_data",      # 采集数据落盘
    "save_data_csv",        # CSV 落盘（verified_write 校验）
    "set_theme",            # UI 偏好，可逆
    "set_chat_backend",     # N3 执行后端偏好，可逆
    "transform_dataset",    # 生成新数据集，可删
}

# 不可逆需确认（审批卡）
_L2 = {
    "execute_plan",          # 触发计划队列执行（跑脚本/爬虫等真实动作）
    "organize_user_memory",  # 记忆整单重写（含删除条目）
}

# 高危强制拦截（云端直连一律拒绝，仅人工/管理入口）——当前无，未登记默认 L3

BLOCK_MESSAGE = "已拦截：该操作属于高危动作（仅支持人工操作），本次未执行。"
NO_APPROVAL_CHANNEL_MESSAGE = ("该操作需要用户确认，当前模型通道不支持交互审批，"
                               "已拒绝执行（安全优先）。请换用 DeepSeek 模型或由用户手动操作。")


def gate(tool_name: str, args: dict = None, ctx: dict = None) -> dict:
    """判定工具动作级别。

    返回 {"level", "ask", "block", "reason"}：
    - L0/L1: ask=False block=False（直执行，无感）
    - L2:    ask=True  block=False（需审批卡确认）
    - L3:    ask=False block=True （拦截）
    未登记工具 → L3（fail-closed）。
    """
    if tool_name in _L0:
        return {"level": LEVEL_L0, "ask": False, "block": False, "reason": ""}
    if tool_name in _L1:
        return {"level": LEVEL_L1, "ask": False, "block": False, "reason": ""}
    if tool_name in _L2:
        return {"level": LEVEL_L2, "ask": True, "block": False,
                "reason": "该操作不可逆，需用户确认"}
    return {"level": LEVEL_L3, "ask": False, "block": True,
            "reason": f"未登记工具（{tool_name}）默认高危拦截（fail-closed）"}
