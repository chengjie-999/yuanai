from langchain_core.tools import tool
from yuanai.pure.cookie import cookies_to_dict, cookies_to_header_str


@tool
def cookies_to_requests(site_name: str) -> str:
    """将指定网站的本地 Cookie 转换为 requests 可用的参数字典。site_name: 网站名称。"""
    try:
        import json
        result = cookies_to_dict(site_name)
        if not result:
            return f"❌ 未找到 [{site_name}] 的 Cookie 文件"
        return f"✅ [{site_name}] Cookie 已转换，共 {len(result)} 个键值对\n{json.dumps(result, ensure_ascii=False)}"
    except Exception as e:
        return f"❌ 转换失败: {e}"


@tool
def cookies_to_header(site_name: str, filter_domain: str = "") -> str:
    """将指定网站的本地 Cookie 转换为 HTTP Header。site_name: 网站名称，filter_domain: 可选域名过滤。"""
    try:
        result = cookies_to_header_str(site_name, filter_domain)
        if not result:
            return f"❌ 未找到 [{site_name}] 的 Cookie 文件"
        return f"✅ [{site_name}] Cookie Header 已生成\n{result}"
    except Exception as e:
        return f"❌ 转换失败: {e}"
