import base64
import os
from typing import List, Union, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from yuanai.core.lc import get_llm
from yuanai.audit.parser import AuditResult, parse_audit_result
from yuanai.rag import get_all_specs


# ==================== 扩展数据类型 ====================
class AuditDetailResult:
    """带完整信息的审核结果"""

    def __init__(
            self,
            is_correct: bool,
            error_type: Optional[str],
            error_count: int,
            reason: str,
            images: List[str],
            raw_response: str,
            tool_used: List[str] = None,
            image_id: str = None
    ):
        self.is_correct = is_correct
        self.error_type = error_type
        self.error_count = error_count
        self.reason = reason
        self.images = images  # AI 看到的图片（Base64）
        self.raw_response = raw_response  # AI 原始回复
        self.tool_used = tool_used or []  # 调用的工具
        self.image_id = image_id  # 图片唯一标识


# ==================== 获取标注规范 ====================
SPEC_TEMPLATE = """

标注规范（请严格遵守）：
{specs}

---
"""


SYSTEM_PROMPT_TEMPLATE = """你是一个中小学题目标注审核专家，审核标准从严。
只要有一处不符合规范，就判错误，不要给"勉强可以"的通过。
{specs_content}截图说明：
- 第1张: 题目全屏截图（由于题干为画布标签，会出现显示不全的情况，可尝试调用滚动工具，若无工具须提醒用户）
- 第2张: 参考答案图片
- 第3张+: 其他标记答案

请逐步推理后返回严格的 JSON 格式：
{
    "is_correct": true或false,  // 标注是否正确，任一项不符合规范即为false
    "error_type": "错误原因"或null,  // 错误类型：格式问题较多, 文本压线, 黄框压题干, 最终答案, 不独立, 出框, 少答案, 字太小, 答案错
    "error_count": 数字,  // 错误标注数量
    "reason": "判断理由"  // 简要说明判断原因
}"""


def get_system_prompt() -> str:
    """获取完整的系统提示"""
    specs = get_all_specs()
    specs_content = SPEC_TEMPLATE.format(specs=specs) if specs else ""
    template = SYSTEM_PROMPT_TEMPLATE.replace("{specs_content}", specs_content)
    return template


def normalize_to_image(img_data: Union[bytes, str]) -> Optional[str]:
    """
    将任意格式的图片转换为可直接使用的图片格式
    优化：HTTP URL 直接返回，不下载转换，节省 token
    :param img_data: bytes(二进制) / str(URL或本地路径)
    :return: Base64 或 URL 字符串，失败返回 None
    """
    if img_data is None:
        return None

    if isinstance(img_data, bytes):
        # 二进制 → 转 Base64
        base64_str = base64.b64encode(img_data).decode('utf-8')
        return f"data:image/png;base64,{base64_str}"
    elif isinstance(img_data, str):
        img_data = img_data.strip()
        if img_data.startswith('http'):
            # HTTP URL → 直接返回（节省 token！）
            return img_data
        elif os.path.exists(img_data):
            # 本地文件 → 转 Base64
            try:
                with open(img_data, 'rb') as f:
                    img_bytes = f.read()
                base64_str = base64.b64encode(img_bytes).decode('utf-8')
                return f"data:image/png;base64,{base64_str}"
            except Exception as e:
                print(f"读取图片失败: {e}")
                return None
        else:
            print(f"未知图片路径: {img_data}")
            return None
    else:
        print(f"不支持的图片类型: {type(img_data)}")
        return None


def normalize_images(images: List) -> List[str]:
    """
    将图片列表转换为可直接使用的格式列表
    优化：HTTP URL 直接返回，本地文件/二进制转 Base64
    :param images: 图片列表（支持 bytes/URL/本地路径）
    :return: 图片列表（URL 或 Base64）
    """
    result = []
    for i, img in enumerate(images):
        if img is None:
            continue
        normalized = normalize_to_image(img)
        if normalized:
            result.append(normalized)
        else:
            print(f"图片 {i} 转换失败，跳过")
    return result


def build_multimodal_message(images: List[str], prompt: str = None) -> List:
    """
    构建多模态消息
    :param images: 图片列表（URL 或 Base64）
    :param prompt: 文本提示
    :return: LangChain 消息列表
    """
    if not prompt:
        prompt = "请分析这些题目截图，判断标注是否正确。"

    user_content = [{"type": "text", "text": prompt}]
    for img_b64 in images:
        user_content.append({"type": "image_url", "image_url": {"url": img_b64}})

    return [SystemMessage(content=get_system_prompt()), HumanMessage(content=user_content)]


def call_audit_llm(images: List[str], model: str = "doubao-seed-2-0-pro-260215") -> str:
    """
    调用 LLM 进行审核（多模态模型）
    :param images: Base64 图片列表
    :param model: 模型名称（默认豆包 Seed 多模态）
    :return: AI 返回文本
    """
    messages = build_multimodal_message(images)
    llm = get_llm(model, temperature=0.1, verbose=False)

    try:
        response = llm.invoke(messages)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        error_msg = str(e).replace('"', "'").replace('\n', ' ')
        print(f"LLM 调用失败 ({model}): {error_msg}")
        return f'{{"is_correct": false, "error_type": "答案错", "error_count": 1, "reason": "AI调用失败: {error_msg}"}}'


def call_audit_agent(images: List[str], model: str = "doubao-seed-2-0-pro-260215") -> str:
    """
    调用 LangGraph Agent 进行审核（支持工具调用）
    :param images: Base64 图片列表
    :param model: 模型名称
    :return: AI 返回文本
    """
    from yuanai.core.lc import get_langgraph_agent, get_llm
    from yuanai.tools import all_tools as tools
    
    llm = get_llm(model, temperature=0.1, verbose=False)
    agent = get_langgraph_agent(llm, tools)
    
    prompt_text = "请分析这些题目截图，根据标注规范判断标注是否正确。"
    
    if images:
        user_content = [{"type": "text", "text": prompt_text}]
        for img_url in images:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
        messages = [
            ("system", get_system_prompt()),
            ("user", user_content)
        ]
    else:
        messages = [
            ("system", get_system_prompt()),
            ("user", prompt_text)
        ]
    
    try:
        result = agent.invoke({"messages": messages})
        return result["messages"][-1].content
    except Exception as e:
        error_msg = str(e).replace('"', "'").replace('\n', ' ')
        print(f"Agent 调用失败 ({model}): {error_msg}")
        return f'{{"is_correct": false, "error_type": "答案错", "error_count": 1, "reason": "Agent调用失败: {error_msg}"}}'


def audit_question(images: List, model: str = "doubao-seed-2-0-pro-260215") -> AuditResult:
    """
    审核题目图片（主接口）
    :param images: question_info() 返回的图片列表
    :param model: 模型名称
    :return: AuditResult 判断结果
    """
    if not images:
        return AuditResult(
            is_correct=False,
            error_type="答案错",
            error_count=1,
            reason="获取题目图片失败"
        )

    # 转换为图片格式（URL 或 Base64）
    images_normalized = normalize_images(images)
    if not images_normalized:
        return AuditResult(
            is_correct=False,
            error_type="答案错",
            error_count=1,
            reason="图片转换失败"
        )

    # 调用 LLM
    ai_response = call_audit_llm(images_normalized, model)
    print(f"AI 响应: {ai_response[:200]}...")

    # 解析结果
    return parse_audit_result(ai_response)


def quick_audit(images: List, model: str = "doubao-seed-2-0-pro-260215") -> bool:
    """
    快速审核（仅返回是否正确）
    :param images: 图片列表
    :param model: 模型名称
    :return: True=正确, False=错误
    """
    result = audit_question(images, model)
    return result.is_correct


def audit_question_detail(
        images: List,
        model: str = "doubao-seed-2-0-pro-260215"
) -> AuditDetailResult:
    """
    审核题目图片（带完整详情版本）
    :param images: question_info() 返回的图片列表
    :param model: 模型名称
    :return: AuditDetailResult 带完整详情的审核结果
    """
    if not images:
        return AuditDetailResult(
            is_correct=False,
            error_type="答案错",
            error_count=1,
            reason="获取题目图片失败",
            images=[],
            raw_response="",
            tool_used=[]
        )

    # 转换为图片格式（URL 或 Base64）
    images_normalized = normalize_images(images)
    if not images_normalized:
        return AuditDetailResult(
            is_correct=False,
            error_type="答案错",
            error_count=1,
            reason="图片转换失败",
            images=[],
            raw_response="",
            tool_used=[]
        )

    # 调用 LangGraph Agent（支持工具调用）
    try:
        ai_response = call_audit_agent(images_normalized, model)
    except Exception as e:
        print(f"Agent失败，回退到普通LLM: {e}")
        ai_response = call_audit_llm(images_normalized, model)
    
    print(f"AI 响应: {ai_response[:200]}...")

    # 解析结果
    parsed_result = parse_audit_result(ai_response)

    return AuditDetailResult(
        is_correct=parsed_result.is_correct,
        error_type=parsed_result.error_type,
        error_count=parsed_result.error_count,
        reason=parsed_result.reason,
        images=images_normalized,
        raw_response=ai_response,
        tool_used=[]
    )


def build_audit_prompt(audit_cause: str = "") -> str:
    """动态构建审核系统提示，只注入相关规范段落"""
    from yuanai.rag import search_spec_sections
    specs = search_spec_sections(audit_cause)
    spec_block = ""
    if specs:
        spec_block = f"\n相关标注规范：\n{specs}\n"
    return f"""你是一个小猿众包题目审核自动化助手。
当前任务：单题标答-审核{spec_block}
操作流程：
1. 如果题目显示不全，先调用 scroll_canvas() 向下滚动查看下方内容
2. 或调用 zoom_question() 缩小视图看到更多内容
3. 滚动/缩放后会自动更新截图，多次操作直到看清完整题目
4. 调用 mark_question_correct() 处理独立答案和批改答案的判定
5. 说明你的判断结果，包括正确的驳回原因（如有）

注意：
- 如有驳回需要，用户会在反馈中处理，AI 只需给出正确的驳回原因
- 如果工具调用失败，请说明失败原因"""


def save_feedback(ai_result: str, user_correct: bool, user_note: str = "", image_id: str = ""):
    """保存用户反馈到数据库"""
    try:
        from db.session import AgentDatabase
        import time
        db = AgentDatabase()
        feedback = {
            "image_id": image_id or f"audit_{int(time.time())}",
            "ai_result": ai_result,
            "user_correct": user_correct,
            "user_note": user_note,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        db.set_state(f"audit_feedback_{feedback['image_id']}", feedback)
    except Exception as e:
        print(f"保存反馈失败: {e}")


if __name__ == '__main__':
    # 本地测试
    test_images = []
    result = audit_question(test_images)
    print(f"结果: {result}")
