import base64
import os.path
from typing import Optional, Union, List  # 核心修复：导入List（替代list）
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseLanguageModel

# 导入自定义模块（保持原有路径）
from utils.data_path import root_path
from yuanai.core.lc import get_llm


# ===================== 核心：图片转Base64（保留，为后续扩展） =====================
def local_img_to_base64(img_path: Union[str, Path]) -> Optional[str]:
    """
    本地图片转Base64编码字符串（带格式前缀）
    :param img_path: 图片路径（字符串/Path对象）
    :return: Base64编码字符串（带data:image前缀），失败返回None
    """
    # 1. 路径合法性校验
    img_path = Path(img_path)
    if not img_path.exists():
        print(f"❌ 图片路径不存在：{img_path}")
        return None

    # 2. 图片格式校验（仅支持常见格式）
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp")
    if img_path.suffix.lower() not in valid_extensions:
        print(f"❌ 不支持的图片格式：{img_path.suffix}，仅支持{valid_extensions}")
        return None

    # 3. 读取并编码（增加异常捕获）
    try:
        with open(img_path, "rb") as f:
            img_bytes = f.read()
            base64_str = base64.b64encode(img_bytes).decode("utf-8")

        # 4. 根据图片后缀自动匹配MIME类型
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp"
        }.get(img_path.suffix.lower(), "image/png")

        return f"data:{mime_type};base64,{base64_str}"

    except Exception as e:
        print(f"❌ 图片转Base64失败：{str(e)}")
        return None


# ===================== 核心：兼容纯文本模型的消息构建（修复类型注解） =====================
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


# ===================== 核心：通用模型调用（兼容纯文本/多模态） =====================
def call_llm(
        messages: List[Union[SystemMessage, HumanMessage]],  # 核心修复：List替代list
        model_name: str = "deepseek-chat",  # 纯文本模型（无多模态API时用这个）
        base_url: str = "https://api.deepseek.com/v1",
        temperature: float = 0.1
) -> Optional[str]:
    """
    调用LLM并返回结果（兼容纯文本/多模态模型）
    :param messages: 消息列表
    :param model_name: 模型名称（纯文本：deepseek-chat；多模态：deepseek-vl2）
    :param base_url: 模型接口地址
    :param temperature: 生成温度
    :return: 模型回答文本，失败返回None
    """
    # 1. 初始化模型
    llm: BaseLanguageModel = get_llm(
        base_url=base_url,
        model_name=model_name,
        temperature=temperature,
        verbose=False
    )

    # 2. 调用模型（增加异常捕获）
    try:
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        print(f"❌ 模型调用失败：{str(e)}")
        return None


# ===================== 主函数（无多模态API也能运行） =====================
if __name__ == '__main__':
    # 配置开关：是否启用多模态（无API时设为False）
    USE_MULTIMODAL = False  # 核心开关：后续有API后改为True即可

    # 1. 构建图片路径
    img_path = Path(root_path()) / "data/file/img/home.jpg"

    # 2. 图片转Base64（保留逻辑，为后续扩展）
    img_base64 = local_img_to_base64(img_path)

    # 3. 构建消息（纯文本模式，自动忽略图片）
    messages = build_message(
        text="识别这张图片的内容",
        img_base64=img_base64,  # 传了但会被忽略
        is_multimodal=USE_MULTIMODAL
    )

    # 4. 调用纯文本模型（deepseek-chat）
    response_text = call_llm(
        messages=messages,
        model_name="deepseek-chat",  # 纯文本模型
        temperature=0.1
    )

    # 5. 输出结果
    if response_text:
        print("\n✅ 模型回答：")
        print(response_text)
    else:
        print("\n❌ 未获取到模型回答")