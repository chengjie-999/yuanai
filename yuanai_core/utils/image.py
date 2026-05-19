import base64
from typing import List, Any


class ImageProcessingError(Exception):
    """图片处理错误"""
    pass


def process_uploaded_images(uploaded_files: List[Any]) -> tuple:
    """
    将上传的文件列表转换为 base64 data URL 列表
    返回: (images_base64, errors)
    """
    images_base64 = []
    errors = []

    if not uploaded_files:
        return images_base64, errors

    for file in uploaded_files:
        try:
            bytes_data = file.getvalue()
            base64_image = base64.b64encode(bytes_data).decode('utf-8')
            mime_type = file.type
            img_url = f"data:{mime_type};base64,{base64_image}"
            images_base64.append(img_url)
        except Exception as e:
            errors.append(f"{file.name}: {str(e)}")

    return images_base64, errors


def validate_image_files(uploaded_files: List[Any], allowed_types: List[str] = None) -> tuple:
    """
    验证上传的图片文件
    返回: (is_valid, error_message)
    """
    if allowed_types is None:
        allowed_types = ["image/jpeg", "image/png"]

    for file in uploaded_files:
        if file.type not in allowed_types:
            return False, f"不支持的文件类型: {file.type}，仅支持 jpg/jpeg/png"

    return True, ""