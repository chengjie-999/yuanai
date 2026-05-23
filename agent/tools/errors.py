"""工具层异常分类 — 区分可重试错误和致命错误，让 Agent 能做出合理决策"""

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    InvalidSessionIdException,
    WebDriverException,
    NoSuchWindowException,
)

RETRYABLE = (
    StaleElementReferenceException,
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
)

FATAL = (
    InvalidSessionIdException,
    NoSuchWindowException,
)


def classify_error(e: Exception, context: str = "") -> str:
    """分类异常并返回带标签的错误消息"""
    msg = str(e) or type(e).__name__

    if isinstance(e, RETRYABLE):
        tag = "❌ [可重试]"
    elif isinstance(e, FATAL):
        tag = "❌ [致命]"
    elif isinstance(e, WebDriverException):
        tag = "❌ [致命] 浏览器驱动异常:"
    elif isinstance(e, ValueError):
        tag = "❌ [参数错误]"
    else:
        tag = "❌"

    if context:
        return f"{tag} {context}：{msg}"
    return f"{tag} {msg}"
