"""独立技能模块 — 直接从 core 层重新导出，零额外逻辑。"""
from yuanai_core.pure.calculate import add, multiply
from yuanai_core.pure.crawl import fetch_url, parse_html
from yuanai_core.pure.stats import get_system_stats
from yuanai_core.pure.files import list_files, read_file_content
