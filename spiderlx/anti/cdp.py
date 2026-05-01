def get_anti_detect_script() -> str:
    """返回 CDP 反检测脚本，导航前注入页面"""
    return """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
"""
