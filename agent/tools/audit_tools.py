from langchain_core.tools import tool
from db.session import AgentDatabase
from agent.rag import get_all_specs, search_spec, search_steps
import os
from datetime import datetime

db = AgentDatabase()

IMPORTANT_EXAMPLES_FILE = "data/file/important_examples.jsonl"


@tool
def retrieve_annotation_spec(query: str = "") -> str:
    """
    检索标注规范，需要判断内容是否合规时调用。
    输入：待审核的内容关键词（必填，如 '独立批改' '黄框' '举报' '数学' '长文本' '答案不全'）
    输出：相关规范段落（向量检索，按语义匹配）
    """
    if not query:
        return "请提供关键词进行检索，如：独立批改、黄框、举报、数学、长文本"
    return search_spec(query) if search_spec(query) else get_all_specs()


@tool
def retrieve_audit_steps(query: str = "") -> str:
    """
    检索审核操作步骤和工具使用方法。
    输入：关键词（可选，如 '操作流程' '错误处理' '工具'）
    输出：相关操作步骤
    """
    result = search_steps(query) if query else search_steps("操作")
    return result if result else "操作步骤文档为空"


@tool
def save_audit_feedback(
    image_id: str,
    ai_is_correct: bool,
    ai_error_type: str = "",
    user_is_correct: bool = None,
    user_error_type: str = None,
    reason: str = "",
    is_important: bool = False,
    user_instruction: str = ""
) -> str:
    """
    保存人工审核反馈，用于优化审核策略。
    输入：
        - image_id: 图片唯一标识
        - ai_is_correct: AI判断是否正确
        - ai_error_type: AI判断的错误类型
        - user_is_correct: 用户确认的判断（可选）
        - user_error_type: 用户纠正的错误类型（可选）
        - reason: 原因说明
        - is_important: 是否作为重要参考案例（可选）
        - user_instruction: 给AI的额外指导（可选）
    输出：保存结果
    """
    timestamp = datetime.now().isoformat()
    
    feedback_data = {
        "image_id": image_id,
        "ai_is_correct": ai_is_correct,
        "ai_error_type": ai_error_type,
        "user_is_correct": user_is_correct if user_is_correct is not None else ai_is_correct,
        "user_error_type": user_error_type if user_error_type else ai_error_type,
        "reason": reason,
        "is_important": is_important,
        "user_instruction": user_instruction,
        "timestamp": timestamp
    }
    
    db.set_state(f"audit_feedback_{image_id}", feedback_data)
    
    result_msg = f"反馈已保存: {image_id}"
    
    # 如果标记为重要参考，同时保存到文件
    if is_important:
        try:
            save_to_important_examples(feedback_data)
            result_msg += "（重要参考已保存）"
        except Exception as e:
            result_msg += f"（警告：重要参考保存失败: {e}）"
    
    return result_msg


def save_to_important_examples(feedback_data: dict):
    """保存重要参考案例到文件"""
    from utils.data_path import root_path
    
    file_path = os.path.join(root_path(), IMPORTANT_EXAMPLES_FILE)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # 追加写入 JSONL 格式
    import json
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(feedback_data, ensure_ascii=False) + '\n')


@tool
def get_important_examples(limit: int = 10) -> str:
    """获取重要参考案例，用于优化规范"""
    from utils.data_path import root_path
    
    file_path = os.path.join(root_path(), IMPORTANT_EXAMPLES_FILE)
    
    if not os.path.exists(file_path):
        return "暂无重要参考案例"
    
    import json
    examples = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    
    if not examples:
        return "暂无重要参考案例"
    
    # 返回最近的案例
    examples = examples[-limit:] if len(examples) > limit else examples
    
    result = [f"共 {len(examples)} 条重要参考案例："]
    for i, ex in enumerate(examples, 1):
        result.append(
            f"{i}. 图片:{ex.get('image_id')}, "
            f"AI判断:{ex.get('ai_is_correct')}, "
            f"用户判断:{ex.get('user_is_correct')}, "
            f"用户纠正:{ex.get('user_error_type')}"
        )
    
    return '\n'.join(result)


@tool
def get_audit_feedback(image_id: str) -> str:
    """
    获取指定图片的审核反馈。
    输入：图片唯一标识
    输出：反馈详情
    """
    feedback = db.get_state(f"audit_feedback_{image_id}")
    if feedback:
        return str(feedback)
    return "无反馈记录"


@tool
def get_recent_feedbacks(limit: int = 10) -> str:
    """
    获取最近的审核反馈，用于分析AI判断准确率。
    输入：返回数量限制
    输出：反馈列表
    """
    all_states = db.get_all_states()
    feedback_list = []
    
    for key, value in all_states.items():
        if key.startswith("audit_feedback_"):
            feedback_list.append(value)
    
    feedback_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    if limit:
        feedback_list = feedback_list[:limit]
    
    if not feedback_list:
        return "暂无反馈记录"
    
    total = len(feedback_list)
    ai_correct = sum(1 for f in feedback_list if f.get("ai_is_correct") == f.get("user_is_correct"))
    accuracy = ai_correct / total * 100 if total > 0 else 0
    
    result = [f"共 {total} 条反馈，AI准确率: {accuracy:.1f}%"]
    
    for f in feedback_list[:5]:
        result.append(
            f"图片: {f.get('image_id', 'N/A')}, "
            f"AI: {'✓' if f.get('ai_is_correct') else '✗'+f.get('ai_error_type','')}, "
            f"用户: {'✓' if f.get('user_is_correct') else '✗'+f.get('user_error_type','')}"
        )
    
    return '\n'.join(result)


@tool
def analyze_audit_errors() -> str:
    """
    分析审核错误类型分布，用于优化规范。
    输出：错误类型统计
    """
    all_states = db.get_all_states()
    error_counts = {}
    
    for key, value in all_states.items():
        if key.startswith("audit_feedback_"):
            if not value.get("user_is_correct", True):
                error_type = value.get("user_error_type", "未知")
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
    
    if not error_counts:
        return "暂无错误数据分析"
    
    sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
    
    result = ["错误类型分布："]
    for error_type, count in sorted_errors:
        result.append(f"  {error_type}: {count}次")
    
    return '\n'.join(result)