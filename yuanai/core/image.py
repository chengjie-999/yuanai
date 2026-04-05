import base64
from typing import Optional, Union, List  # 核心修复：导入List（替代list）
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseLanguageModel

# 导入自定义模块（保持原有路径）
from utils.data_path import root_path
from yuanai.core.build_message import build_message
from yuanai.core.lc import get_llm, call_llm


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
