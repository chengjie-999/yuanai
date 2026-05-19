"""纯业务逻辑层 — 无 LangChain 依赖，任何代码可直接调用。"""
from yuanai_core.pure.calculate import add, multiply
from yuanai_core.pure.crawl import fetch_url, parse_html
from yuanai_core.pure.stats import get_system_stats
from yuanai_core.pure.files import list_files, read_file_content
