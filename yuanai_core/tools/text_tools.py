TOOL_CATEGORY = "general"

"""Text processing utilities"""
import re
import json
from langchain_core.tools import tool


@tool
def count_words(text: str) -> str:
    """Count characters, words, lines in text. text: input string."""
    if not text:
        return "文本为空"
    chars = len(text)
    cn = len(re.findall(r'[一-鿿]', text))
    en = len(re.findall(r'[a-zA-Z]+', text))
    lines = text.count('\n') + 1
    nums = len(re.findall(r'\d+', text))
    return f"字符: {chars} | 中文: {cn} | 英文词: {en} | 行: {lines} | 数字段: {nums}"


@tool
def extract_numbers(text: str) -> str:
    """Extract all numbers from text. text: input string. Returns sum + top 10."""
    nums = re.findall(r'-?\d+\.?\d*', text)
    if not nums:
        return "未找到数字"
    floats = [float(n) for n in nums]
    top = sorted(floats, reverse=True)[:10]
    return f"共 {len(nums)} 个数字 | 总和: {sum(floats):.2f}\n前10: {', '.join(str(f) for f in top)}"


@tool
def text_to_table(text: str, delimiter: str = ",") -> str:
    """Convert CSV/TSV text to Markdown table. text: content, delimiter: ,|\\t|\\s."""
    if not text.strip():
        return "文本为空"
    if delimiter == "\\t": delimiter = "\t"
    elif delimiter == "\\s": delimiter = r"\s+"
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if len(lines) < 2:
        return "至少需要表头+1行"
    rows = [re.split(delimiter, line) if delimiter != r"\s+" else re.split(r'\s+', line) for line in lines]
    mc = max(len(r) for r in rows)
    for r in rows:
        while len(r) < mc: r.append("")
    md = ["| " + " | ".join(str(c)[:30] for c in rows[0]) + " |"]
    md.append("|" + "|".join("---" for _ in range(mc)) + "|")
    for row in rows[1:11]:
        md.append("| " + " | ".join(str(c)[:40] for c in row) + " |")
    if len(rows) > 11:
        md.append(f"\n*共 {len(rows)-1} 行, 显示前10行*")
    return "\n".join(md)


@tool
def format_json(data: str) -> str:
    """Pretty-print JSON string. data: raw JSON."""
    try:
        return json.dumps(json.loads(data), ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return f"JSON 解析失败: {e}"
