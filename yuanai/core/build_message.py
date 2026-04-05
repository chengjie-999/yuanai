from typing import List, Union

from langchain_core.messages import SystemMessage, HumanMessage


def build_message(
        text: str,
        img_base64: str = None,
        is_multimodal: bool = False  # 开关：是否启用多模态
) -> List[Union[SystemMessage, HumanMessage]]:  # 核心修复：List替代list
    """
    构建提示词消息（兼容纯文本/多模态模型）
    :param text: 用户提问文本
    :param img_base64: 图片Base64编码字符串（可选）
    :param is_multimodal: 是否启用多模态（无API时设为False）
    :return: 可直接传给LLM的消息列表
    """
    # 系统提示词：降级处理（纯文本模型时告知用户无法识别图片）
    system_msg = SystemMessage(content="""
    如果你是纯文本模型，无法识别图片内容，请友好告知用户，并告知图片是否传递成功；
    如果你是多模态模型，请正常识别图片并回答问题。
    """)

    if is_multimodal and img_base64:
        # 多模态模式：文本+图片（后续接入API后只需打开开关）
        human_msg = HumanMessage(
            content=[
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": img_base64}}
            ]
        )
    else:
        # 纯文本模式：仅文本，忽略图片（无多模态API时用这个）
        human_msg = HumanMessage(
            content=[
                {"type": "text", "text": text}
            ]
        )

    return [system_msg, human_msg]
