from selenium import webdriver
import time

# ------------------- 核心的 API 地址提取函数 -------------------
from spiderlx.auto.web.selenium.main import open_web, able_web


def get_api_urls(
        driver: webdriver.Chrome,
        target_url: str,
        api_features: list = None,
        wait_time: float = 8.0  # 延长等待时间
) -> list:
    """
    向已初始化的浏览器注入 JS，提取 API 地址（核心逻辑）
    """
    try:
        # 第一步：先访问空白页，确保脚本注入到干净的上下文
        driver.get("about:blank")

        # 第二步：注入监听脚本（此时页面空白，脚本不会被覆盖）
        inject_js = """
        // 持久化监听：即使页面跳转，也重新注入监听
        function injectListener() {
            window.apiUrls = window.apiUrls || new Set();
            const features = ["/api/", ".json", "/v1/", "/v2/", "/api/v"];

            // 监听 XMLHttpRequest
            if (!window.xhrListened) {
                const originalXHRopen = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function(method, url) {
                    if (features.some(feature => url.includes(feature))) {
                        window.apiUrls.add(url);
                    }
                    return originalXHRopen.apply(this, arguments);
                };
                window.xhrListened = true;
            }

            // 监听 Fetch API
            if (!window.fetchListened) {
                const originalFetch = window.fetch;
                window.fetch = function(url, options) {
                    const requestUrl = typeof url === 'string' ? url : url.url;
                    if (features.some(feature => requestUrl.includes(feature))) {
                        window.apiUrls.add(requestUrl);
                    }
                    return originalFetch.apply(this, arguments);
                };
                window.fetchListened = true;
            }
        }

        // 立即注入监听
        injectListener();
        // 监听页面跳转，重新注入（关键：解决页面刷新后脚本失效）
        window.addEventListener('beforeunload', injectListener);
        """
        driver.execute_script(inject_js)

        # 第三步：加载目标页面（此时监听脚本已生效）
        info = able_web()
        name = open_web(driver, info, url=target_url)

        # 第四步：延长等待时间，确保动态加载的 API 请求被捕获
        # 主动滚动页面，触发更多 API 请求（知乎需要滚动加载内容）
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)

        # 提取 API 地址（确保兼容性）
        api_urls = driver.execute_script("""
            if (window.apiUrls) {
                return Array.from(window.apiUrls);
            } else {
                return [];
            }
        """)
        return api_urls

    except Exception as e:
        print(f"提取 API 地址失败: {str(e)}")
        raise
