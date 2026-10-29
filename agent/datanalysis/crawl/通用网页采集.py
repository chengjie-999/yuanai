# %% [markdown]
# # 通用网页采集
# 抓取网页中的表格和列表数据，保存为 CSV。支持翻页。

# %%
import os, sys, csv, time
from datetime import datetime

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

# C10（2026-10-29）：请求一律走 guarded_get（robots 判定 + 同域限流 +
# 统一可识别 UA XiaoYuanBot/1.0 + safe_get SSRF 守卫）——此前裸 requests.get
# 可绕过 SSRF 校验（重定向/分页）且无 robots 尊重
from yuanai_core.pure.crawl_compliance import guarded_get, check_robots

爬取目录 = os.path.join(root_path(), "data", "crawl")

__script_name__ = "通用网页采集"
__script_desc__ = "采集指定网页中的结构化数据（表格/列表），支持翻页。参数: url(必填), max_pages(可选,默认3), selector(可选,CSS选择器)"
__script_tags__ = ["网页采集"]
__script_params__ = [{"name": "url", "type": "url"}, {"name": "max_pages", "type": "int"}, {"name": "selector", "type": "enum"}]

# %% [markdown]
# ### 参数

# %%
目标URL = sys.argv[1] if len(sys.argv) > 1 else ""
最大页数 = int(sys.argv[2]) if len(sys.argv) > 2 else 3
CSS选择器 = sys.argv[3] if len(sys.argv) > 3 else ""

# %% [markdown]
# ### 辅助函数

# %%
def _构建分页URL(url: str, page: int) -> str:
    if page == 1:
        return url
    if "page=" in url:
        return url.replace(f"page={page - 1}", f"page={page}")
    if "pn=" in url:
        return url.replace(f"pn={page - 1}", f"pn={page}")
    if url.endswith(".html"):
        return url.replace(".html", f"_{page}.html")
    if "?" in url:
        return f"{url}&page={page}"
    return f"{url}?page={page}"


def _提取数据(soup, selector: str = ""):
    """自动检测页面中的表格或列表"""
    if selector:
        return _按选择器提取(soup, selector)

    for table in soup.select("table"):
        rows = list(table.select("tr"))
        if len(rows) < 2:
            continue
        headers = [th.get_text(strip=True) for th in rows[0].select("th, td")]
        if not headers:
            continue
        result = []
        for tr in rows[1:]:
            cells = [td.get_text(strip=True) for td in tr.select("td, th")]
            if len(cells) == len(headers) and any(cells):
                result.append(dict(zip(headers, cells)))
        if result:
            print(f"自动检测到表格，{len(result)} 行")
            return result

    items = soup.select("ul li, ol li")
    if items and len(items) >= 3:
        print(f"自动检测到列表，{len(items)} 项")
        return [{"内容": li.get_text(strip=True)} for li in items if li.get_text(strip=True)]

    return []


def _按选择器提取(soup, selector: str):
    elements = soup.select(selector)
    if not elements:
        return []
    result = []
    for el in elements:
        cells = el.select("td, th")
        if cells:
            result.append({f"列{i}": c.get_text(strip=True) for i, c in enumerate(cells, 1)})
        else:
            text = el.get_text(strip=True)
            if text:
                result.append({"内容": text})
    return result


# %% [markdown]
# ### 采集

# %%
if not 目标URL:
    raise ValueError("请设置「目标URL」参数")

all_rows = []
os.makedirs(爬取目录, exist_ok=True)

# 来源与 robots 状态（合规审计第 12 条：采集记录附来源/robots 状态）
_robots_verdict, _robots_note = check_robots(目标URL)

for page in range(1, 最大页数 + 1):
    page_url = _构建分页URL(目标URL, page)
    print(f"正在采集第 {page} 页: {page_url}")

    try:
        resp = guarded_get(page_url, timeout=20, max_bytes=10 * 1024 * 1024)
        resp.raise_for_status()
    except PermissionError as e:
        raise RuntimeError(f"{e}（已尊重 robots.txt 拒绝采集）")
    except Exception as e:
        if page == 1:
            raise RuntimeError(f"请求失败: {e}")
        break

    # bytes 直喂 BeautifulSoup：由 meta charset 自动识别编码（safe_fetch 只给 utf-8 replace）
    soup = BeautifulSoup(resp.content, "html.parser")
    rows = _提取数据(soup, CSS选择器)
    if not rows and page == 1:
        raise RuntimeError("未在页面中找到表格或列表数据，请指定 CSS选择器")
    if not rows:
        break

    all_rows.extend(rows)
    print(f"第 {page} 页采集 {len(rows)} 条，累计 {len(all_rows)} 条")

    if len(rows) < 5:
        break
    time.sleep(1.5)

if not all_rows:
    raise RuntimeError("未采集到任何数据")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_path = os.path.join(爬取目录, f"crawl_{timestamp}.csv")
keys = list(all_rows[0].keys())
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    writer.writerows(all_rows)

print(f"\n采集完成，共 {len(all_rows)} 条记录。")
print(f"字段: {', '.join(keys)}")
print(f"\n前 5 条预览:")
for row in all_rows[:5]:
    print("  " + " | ".join(f"{k}: {v}" for k, v in row.items()))
print(f"\n文件: {csv_path}")
# C10（2026-10-29）：采集记录附来源与 robots 状态（合规审计第 12 条）
print(f"来源: {目标URL}")
print(f"robots: {_robots_verdict}" + (f"（{_robots_note}）" if _robots_note else ""))
