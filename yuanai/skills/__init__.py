# 独立技能模块 — 可脱离 LangChain 直接 import 调用
from yuanai.skills.calculator import add, multiply
from yuanai.skills.crawler import fetch_url, parse_html
from yuanai.skills.cookie import cookies_to_dict, cookies_to_header_str
from yuanai.skills.stats import get_system_stats
from yuanai.skills.files import list_files, read_file_content
