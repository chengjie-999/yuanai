"""思维导图解析器 — 纯函数，零框架依赖。

把多种导图格式统一解析为树形结构，schema 与 yuanai_core.rag._flatten_tree 兼容：

    node = {"level": 1, "title": "...", "content": "", "images": [{"alt","src"}], "children": [...]}

保真度排序（导入时同 stem 择优）：html > md > xmind > mm > opml > emmx > txt

- html:  万兴脑图导出的 HTML —— `ed:parentid` 属性含完整父子层级（高保真主路径）
- md:    heading + 缩进列表构成的 Markdown（万兴脑图导出的通用格式）
- xmind: XMind zip（新版 content.json / 旧版 content.xml）
- mm:    FreeMind XML
- opml:  OPML outline
- emmx:  万兴脑图原生文件（zip 容器，节点文本明文内嵌于 mmpage/*.bin；
         实测父子层级不可恢复 → quality="text-only"，仅作兜底）
- txt:   纯文本兜底（整文作为根节点 content）

实测基准（仓库真实文件 data/aiprompt/01_Python.emmx / .html）：
  html 789 个节点、360 个有子节点、56 张图（含 base64 内嵌）；emmx 每页约 500 条明文文本。
"""
from __future__ import annotations

import io
import re
import json
import zipfile
import xml.etree.ElementTree as ET

# 保真度排序（高 → 低，txt 为末位兜底）
FIDELITY = ["html", "md", "xmind", "mm", "opml", "emmx", "txt"]


# ====================== 基础工具 ======================

def _local(tag: str) -> str:
    """去掉 lxml/ET 的命名空间前缀：'{http://www.w3.org/2000/svg}g' -> 'g'"""
    return tag.rsplit("}", 1)[-1].lower()


def _new_node(level: int, title: str, content: str = "", images: list | None = None) -> dict:
    return {"level": level, "title": title, "content": content, "images": images or [], "children": []}


def _count(nodes: list, depth: int = 0) -> tuple[int, int]:
    """返回 (节点总数, 最大深度)"""
    total, deepest = 0, depth
    for n in nodes:
        total += 1
        c, d = _count(n["children"], depth + 1)
        total += c
        deepest = max(deepest, d)
    return total, deepest


def _meta(fmt: str, quality: str, title: str, warnings: list, source_filename: str, children: list) -> dict:
    node_count, max_depth = _count(children)
    return {
        "meta": {
            "format": fmt, "quality": quality, "title": title,
            "node_count": node_count, "max_depth": max_depth,
            "warnings": warnings, "source_filename": source_filename, "fallbacks": [],
        },
        "children": children,
    }


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return data.decode("utf-8", errors="ignore")


# ====================== 格式探测 ======================

def detect_format(filename: str, data: bytes) -> str:
    """两级探测：① 扩展名 ② 内容魔数/特征。返回 FIDELITY 中的格式名。"""
    name = (filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""

    # zip 容器（emmx / xmind）
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = " ".join(zf.namelist())
        except zipfile.BadZipFile:
            names = ""
        if ext == "emmx" or "mmpage/" in names or "mm.bkiwi" in names:
            return "emmx"
        if ext == "xmind" or "content.json" in names or "content.xml" in names:
            return "xmind"

    head = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n")
    # XML 家族（mm / opml）
    if head.startswith(b"<"):
        try:
            root = ET.fromstring(data)
            tag = _local(root.tag)
            if tag == "opml":
                return "opml"
            if tag == "map":
                return "mm"
        except ET.ParseError:
            pass
        if ext == "mm":
            return "mm"
        if ext == "opml":
            return "opml"

    # HTML（万兴导出，含 <html> 或 <svg>）
    if re.search(rb"<html|<svg|<!doctype\s+html", data[:2048], re.I):
        return "html"

    if ext in ("html", "htm"):
        return "html"
    if ext in ("md", "markdown"):
        return "md"

    # 内容探测：heading/列表为主的纯文本视为 md（万兴导出偶无扩展名）
    text = _decode(data[:4096])
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines:
        headingish = sum(1 for ln in lines if re.match(r"^\s*#{1,6}\s|^\s*[-*+]\s+", ln))
        if headingish >= max(1, len(lines) // 3):
            return "md"
    return "txt"


# ====================== 万兴 HTML（高保真主路径） ======================

_BINARY_RUN_RE = re.compile(r"\b[01]{4,}\b|\b[0-9a-fA-F]{8,}\b")


def _clean_text(s: str) -> str:
    """去空白 + 剔除二进制装饰串（如 '010111010101'）"""
    s = _BINARY_RUN_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _collect_text(el, parts: list):
    """收集 group 内文本；遇到带 id 的子节点 g 只收其 tail（子节点文本归子节点），
    无 id 的容器/装饰 g 继续下钻。"""
    if el.text:
        parts.append(el.text)
    for child in el:
        if _local(child.tag) == "g" and child.get("id"):
            if child.tail:
                parts.append(child.tail)
            continue
        _collect_text(child, parts)
        if child.tail:
            parts.append(child.tail)


def _href_of(el) -> str:
    for k, v in el.attrib.items():
        if k == "href" or k.endswith(":href") or k.endswith("}href"):
            return v
    return ""


def _collect_images(el, symbols: dict) -> list:
    """收集节点图片。万兴 HTML 的图片在 <symbol> 内定义、经 <use xlink:href='#id'> 引用。"""
    imgs, seen = [], set()

    def walk(e):
        for child in e:
            if _local(child.tag) == "g" and child.get("id"):
                continue  # 子节点图片归子节点
            if _local(child.tag) == "use":
                ref = _href_of(child).lstrip("#")
                src = symbols.get(ref)
                if src and src not in seen:
                    seen.add(src)
                    imgs.append({"alt": "", "src": src})
            walk(child)

    walk(el)
    return imgs


def parse_edraw_html(data: bytes) -> dict:
    """解析万兴脑图导出的 HTML：ed:parentid 重建层级（实测 789 节点全还原）。

    多页导图导出为多根森林；parentid 缺失/指向不存在 id 的节点按根处理。
    """
    from lxml import html as lxml_html

    text = _decode(data)
    root = lxml_html.fromstring(text)

    id2el = {}
    for el in root.iter():
        if _local(el.tag) == "g" and el.get("id"):
            id2el[el.get("id")] = el
    if not id2el:
        raise ValueError("HTML 中未找到 edraw 节点（g 元素）")

    # symbol id → 图片 src（<symbol><image xlink:href=.../></symbol> 定义处）
    symbols = {}
    for el in root.iter():
        if _local(el.tag) == "symbol" and el.get("id"):
            for d in el.iter():
                if _local(d.tag) == "image":
                    href = _href_of(d)
                    if href:
                        symbols[el.get("id")] = href
                    break

    # id -> 节点；先建壳，再挂父子
    children_map = {gid: [] for gid in id2el}
    roots = []
    for gid, el in id2el.items():
        pid = el.get("ed:parentid")
        if pid and pid in id2el:
            children_map[pid].append(gid)
        else:
            roots.append(gid)

    def build(gid: str, level: int) -> dict:
        el = id2el[gid]
        parts: list = []
        _collect_text(el, parts)
        title = _clean_text("".join(parts))
        node = _new_node(level, title, "", _collect_images(el, symbols))
        node["children"] = [build(c, level + 1) for c in children_map.get(gid, [])]
        return node

    children = [build(gid, 1) for gid in roots]
    # 丢弃纯空壳根（无文本无子无图）
    children = [c for c in children if c["title"] or c["children"] or c["images"]]
    title = children[0]["title"] if children else ""
    warnings = []
    if len(children) > 1:
        warnings.append(f"导图包含 {len(children)} 个独立根（多页或多主题），已按多根树保留")
    return _meta("html", "full", title, warnings, "", children)


# ====================== Markdown（heading + 缩进列表） ======================

def parse_mindmap_markdown(text: str) -> list[dict]:
    """解析 Markdown：heading (#) + 列表项 (-) 共同构成树（rag._parse_mindmap_md 同款算法）。"""
    root = {"level": 0, "title": "ROOT", "children": [], "content": "", "images": []}
    stack = [root]
    current_heading_level = 0

    for line in text.splitlines():
        h_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        list_match = re.match(r"^(\s*)[-*+]\s+(.+)$", line)

        if h_match:
            level = len(h_match.group(1))
            title = h_match.group(2).strip()
            current_heading_level = level

            while stack and stack[-1]["level"] >= level:
                stack.pop()
            if not stack:
                stack = [root]

            parent = stack[-1]
            node = {"level": level, "title": title, "children": [], "content": "", "images": []}
            parent["children"].append(node)
            stack.append(node)

        elif list_match:
            indent = len(list_match.group(1))
            title = list_match.group(2).strip()
            list_level = current_heading_level + max(1, indent // 2 + 1)

            while stack and stack[-1]["level"] >= list_level:
                stack.pop()
            if not stack:
                stack = [root]

            parent = stack[-1]
            node = {"level": list_level, "title": title, "children": [], "content": "", "images": []}
            parent["children"].append(node)
            stack.append(node)

        else:
            stripped = line.strip()
            if stripped and stack and stack[-1]["level"] > 0:
                stack[-1]["content"] += stripped + "\n"
                for m in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", stripped):
                    stack[-1]["images"].append({"alt": m.group(1), "src": m.group(2)})

    return root["children"]


def parse_markdown(data: bytes) -> dict:
    children = parse_mindmap_markdown(_decode(data))
    if not children:
        raise ValueError("Markdown 中未解析出内容")
    title = children[0]["title"] if children else ""
    return _meta("md", "full", title, [], "", children)


# ====================== FreeMind .mm ======================

def parse_freemind_mm(data: bytes) -> dict:
    root = ET.fromstring(data)

    def walk(el, level: int) -> dict:
        title = el.attrib.get("TEXT", "").strip()
        content = ""
        rich = el.find("richcontent")
        if rich is not None:
            parts = [t.strip() for t in rich.itertext() if t and t.strip()]
            content = "\n".join(parts)
        node = _new_node(level, title, content)
        node["children"] = [walk(c, level + 1) for c in el if _local(c.tag) == "node"]
        return node

    top_nodes = [walk(c, 1) for c in root if _local(c.tag) == "node"]
    if not top_nodes:
        raise ValueError("FreeMind 文件中没有 node 节点")
    title = top_nodes[0]["title"] if top_nodes else ""
    return _meta("mm", "full", title, [], "", top_nodes)


# ====================== XMind（zip） ======================

def _xmind_topic(topic: dict, level: int) -> dict:
    node = _new_node(level, (topic.get("title") or "").strip())
    notes = (topic.get("notes") or {}).get("plain") or {}
    node["content"] = (notes.get("content") or "").strip()
    kids = (topic.get("children") or {})
    for sub in kids.get("attached", []) + kids.get("detached", []):
        node["children"].append(_xmind_topic(sub, level + 1))
    return node


def parse_xmind(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "content.json" in zf.namelist():
            sheets = json.loads(zf.read("content.json"))
            if not isinstance(sheets, list) or not sheets:
                raise ValueError("content.json 无工作表")
            top = []
            for sh in sheets:
                if sh.get("rootTopic"):
                    top.append(_xmind_topic(sh["rootTopic"], 1))
            if not top:
                raise ValueError("content.json 无根主题")
            title = top[0]["title"] if top else ""
            return _meta("xmind", "full", title, [], "", top)

        content = zf.read("content.xml")
    root = ET.fromstring(content)

    def walk(el, level: int) -> dict:
        title = el.attrib.get("title", "").strip()
        node = _new_node(level, title)
        for sub in el:
            if _local(sub.tag) == "topic":
                node["children"].append(walk(sub, level + 1))
        return node

    sheets = [c for c in root if _local(c.tag) == "sheet"]
    top = []
    for sh in sheets:
        rt = [c for c in sh if _local(c.tag) == "topic"]
        if rt:
            top.append(walk(rt[0], 1))
    if not top:
        raise ValueError("XMind XML 中无 sheet/topic")
    return _meta("xmind", "full", top[0]["title"] if top else "", [], "", top)


# ====================== OPML ======================

def parse_opml(data: bytes) -> dict:
    root = ET.fromstring(data)

    def walk(el, level: int) -> dict:
        title = el.attrib.get("text", "").strip()
        node = _new_node(level, title, (el.attrib.get("_note") or "").strip())
        node["children"] = [walk(c, level + 1) for c in el if _local(c.tag) == "outline"]
        return node

    body = [c for c in root if _local(c.tag) == "body"]
    outlines = []
    if body:
        outlines = [walk(c, 1) for c in body[0] if _local(c.tag) == "outline"]
    if not outlines:
        raise ValueError("OPML 中没有 outline 节点")
    return _meta("opml", "full", outlines[0]["title"] if outlines else "", [], "", outlines)


# ====================== 万兴原生 .emmx（text-only 兜底） ======================

_EMMX_RUN_RE = re.compile(rb"(?:[\x20-\x7e]|[\xc2-\xf4][\x80-\xbf]{1,3}){2,}")
_THEME_RE = re.compile(r"^[A-Za-z]*(主题\s*\d*)$")


def _extract_emmx_texts(raw: bytes) -> list[str]:
    """从 mmpage/*.bin 抽取明文 UTF-8 文本（tag 字节 + varint 长度 + 文本 + 0x00 内嵌）"""
    out, seen = [], set()
    for m in _EMMX_RUN_RE.finditer(raw):
        try:
            s = m.group().decode("utf-8", "strict")
        except UnicodeDecodeError:
            continue
        s = s.strip("\x00 \t\r\n").lstrip("?！!：:;；,，")
        if len(s) < 2 or s in seen:
            continue
        if sum(1 for c in s if c.isprintable()) / len(s) < 0.8:
            continue
        if not (re.search(r"[一-鿿]", s) or len(s) >= 4):
            continue  # 无 CJK 且太短 → 大概率是二进制噪声
        if re.fullmatch(r"[\W_]+", s) or re.fullmatch(r"\d+", s):
            continue
        if re.fullmatch(r"[01]{4,}", s):
            continue
        if _THEME_RE.match(s):
            continue
        if not re.search(r"[一-鿿]", s):
            # 纯 ASCII：要求词形（全字母/纯数字/点分版本号），剔除 '4e!E'、'(H<I<J' 等二进制残渣
            if not (re.fullmatch(r"[A-Za-z]{2,}[0-9]*", s) or re.fullmatch(r"\d+(\.\d+)*", s)):
                continue
        seen.add(s)
        out.append(s)
    return out


def parse_emmx(data: bytes) -> dict:
    """解析万兴原生 .emmx：仅恢复纯文本（实测父子层级不可恢复）"""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("无效的 emmx 文件（非 zip 容器）")

    # document.xml 的 Pages 属性定义页序（如 'page;page-1;page-2;page-3'）
    page_order = []
    try:
        doc = _decode(zf.read("document.xml"))
        m = re.search(r'Pages\s+V="([^"]+)"', doc)
        if m:
            page_order = [p.strip() for p in m.group(1).split(";") if p.strip()]
    except KeyError:
        pass

    bins = [n for n in zf.namelist() if n.startswith("mmpage/") and n.endswith(".bin")]
    if page_order:
        key = {name: f"mmpage/{name}.bin" for name in page_order}
        bins = sorted(bins, key=lambda n: list(key.values()).index(n) if n in key.values() else 99)
    else:
        bins = sorted(bins)

    texts, seen = [], set()
    for name in bins:
        for s in _extract_emmx_texts(zf.read(name)):
            if s not in seen:
                seen.add(s)
                texts.append(s)
    if not texts:
        raise ValueError("emmx 中未提取到有效文本")

    children = [_new_node(1, t) for t in texts]
    return _meta(
        "emmx", "text-only", texts[0],
        ["emmx 原生解析仅恢复纯文本，父子层级已丢失；如需完整层级请同时拖入该文件的 .html 或 .md 导出"],
        "", children,
    )


# ====================== 调度与降级 ======================

_PARSERS = {
    "html": parse_edraw_html,
    "md": parse_markdown,
    "xmind": parse_xmind,
    "mm": parse_freemind_mm,
    "opml": parse_opml,
    "emmx": parse_emmx,
}


def parse_any(filename: str, data: bytes) -> dict:
    """按探测格式解析，失败沿保真度降级链重试，末位 txt 兜底。"""
    fmt = detect_format(filename, data)
    errors: list[str] = []
    order = [fmt] + [f for f in FIDELITY if f not in (fmt, "txt")]
    for f in order:
        parser = _PARSERS.get(f)
        if parser is None:
            continue
        try:
            result = parser(data)
            if not result["children"]:
                raise ValueError("解析结果为空")
            if f != fmt:
                result["meta"]["fallbacks"].append(fmt)
            return result
        except Exception as e:  # 单格式失败不致命，记录并降级
            errors.append(f"{f}: {e}")

    text = _decode(data).strip()
    title = (filename.rsplit(".", 1)[0] or "未命名导图").strip()
    children = [_new_node(1, title, content=text[:5000])]
    return _meta("txt", "flat", title, errors + ["无法解析为已知格式，已按纯文本导入"], filename, children)


# ====================== 树 → 大纲 / 降级 ======================

def tree_to_outline_md(tree, image_base: str = "") -> str:
    """树 → 缩进 Markdown 大纲（导图大纲视图 + LLM 输入共用）。

    一级分支 #，二级 ##，更深层用缩进列表；节点备注附（备注：…）；
    image_base 非空时图片以（图片: {image_base}/{src}）标注（供 LLM 转换定位图片）。
    """
    children = tree["children"] if isinstance(tree, dict) and "children" in tree else tree
    title = tree.get("meta", {}).get("title", "") if isinstance(tree, dict) else ""
    lines = []
    # 标题与首根同名时（如 html 导出 meta.title 取首根）不重复输出标题
    emit_title = bool(title) and (not children or title != children[0]["title"])
    offset = 1 if emit_title else 0  # 有总标题时根分支降为 ##
    if emit_title:
        lines.append(f"# {title}")

    def note_line(prefix: str, node: dict):
        if node.get("content"):
            first = node["content"].strip().splitlines()[0][:120]
            lines.append(f"{prefix}（备注：{first}）")
        if image_base and node.get("images"):
            for img in node["images"]:
                # data:URI 是旧版导入残留，无法经资产路由提供，跳过避免 LLM 把 base64 写进笔记
                if img["src"].startswith("data:"):
                    continue
                lines.append(f"{prefix}（图片: {image_base.rstrip('/')}/{img['src']}）")

    def walk(nodes, indent: int):
        for n in nodes:
            depth = (n.get("level", 1) or 1) + offset  # 按节点自身层级，子视图深度不乱
            if depth <= 2:
                lines.append("#" * max(depth, 1) + " " + n["title"])
                note_line("", n)
                walk(n["children"], 0)
            else:
                prefix = "  " * indent + "- "
                lines.append(prefix + n["title"])
                note_line(prefix + "  ", n)
                walk(n["children"], indent + 1)

    walk(children, 0)
    return "\n".join(lines)


def strip_tree(nodes: list, keep_levels: int = 3) -> list:
    """超大树降级：保留 keep_levels 以内节点 + 其一层叶子要点，砍掉更深层。"""
    out = []
    for n in nodes:
        if n["level"] <= keep_levels:
            node = _new_node(n["level"], n["title"], n.get("content", ""), n.get("images"))
            node["children"] = [
                _new_node(c["level"], c["title"], c.get("content", ""), c.get("images"))
                for c in n["children"]
            ]
            out.append(node)
    return out
