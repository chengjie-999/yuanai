PENDING_AUDIT_KEY = "pending_audit_result"


def format_audit_result(audit_data: dict) -> tuple:
    """格式化审核结果，返回 (content, display_images)"""
    result = audit_data.get("result", {})
    images = audit_data.get("images", [])
    raw_response = audit_data.get("raw_response", "")
    tool_used = audit_data.get("tool_used", [])
    user_feedback = audit_data.get("user_feedback", {})
    is_feedback = audit_data.get("is_feedback", False)

    status_emoji = "✅" if result.get("is_correct") else "❌"
    status_text = "通过" if result.get("is_correct") else "需要修改"

    content_lines = []

    if is_feedback:
        content_lines.append("【用户反馈已提交】")
    else:
        content_lines.append("【AI 审核结果】")

    content_lines.append("")
    content_lines.append(f"{status_emoji} AI 审核结论: {status_text}")
    content_lines.append(f"📝 错误类型: {result.get('error_type', '无') or '无'}")
    content_lines.append(f"📊 错误数量: {result.get('error_count', 0)}")
    content_lines.append(f"💬 原因: {result.get('reason', '')}")

    if user_feedback:
        confirms = user_feedback.get("confirms_ai")
        user_type = user_feedback.get("user_error_type")
        instruction = user_feedback.get("user_instruction", "")
        is_important = user_feedback.get("is_important", False)

        content_lines.append("")
        content_lines.append("---")
        content_lines.append("👤 用户反馈：")
        content_lines.append(f"  您认为: {'✅ 正确' if confirms else '❌ 错误，我来纠正'}")
        content_lines.append(f"  选择类型: {user_type or '无'}")
        if instruction:
            content_lines.append(f"  💬 指导: {instruction}")
        if is_important:
            content_lines.append(f"  ⭐ 已标记为重要参考")

    if tool_used:
        content_lines.append(f"🔧 调用的工具: {', '.join(tool_used)}")

    if raw_response and not is_feedback:
        content_lines.append("")
        content_lines.append("---")
        content_lines.append("📄 AI 原始回复:")
        content_lines.append(raw_response[:500])

    content = "\n".join(content_lines)
    display_images = [] if is_feedback else images

    return content, display_images