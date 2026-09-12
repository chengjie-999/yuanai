"""思维导图解析器单测 — 真实 emmx/html（仓库 data/aiprompt 文件）+ 合成 md/mm/xmind/opml 样例

运行：pytest test/test_mindmap_parser.py -v
"""
import io
import os
import zipfile

import pytest

from yuanai_core.pure.mindmap_parser import (
    FIDELITY,
    detect_format,
    parse_any,
    parse_mindmap_markdown,
    strip_tree,
    tree_to_outline_md,
)
from utils.data_path import root_path

AIPROMPT_DIR = os.path.join(root_path(), "data", "aiprompt")


# ---------------- 格式探测 ----------------

def test_detect_md():
    data = "# 标题\n## 分支\n- 叶子\n".encode("utf-8")
    assert detect_format("x.md", data) == "md"
    assert detect_format("noext", data) == "md"  # 无扩展名靠内容探测


def test_detect_mm():
    data = b'<map version="1.0.1"><node TEXT="root"></node></map>'
    assert detect_format("a.mm", data) == "mm"


def test_detect_opml():
    data = b'<?xml version="1.0"?><opml><body><outline text="r"/></body></opml>'
    assert detect_format("a.opml", data) == "opml"


def test_detect_xmind_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("content.json", '[{"rootTopic":{"title":"t"}}]')
    assert detect_format("a.xmind", buf.getvalue()) == "xmind"


def test_detect_emmx_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mmpage/page.bin", b"dummy")
        zf.writestr("mm.bkiwi", b"dummy")
    assert detect_format("a.emmx", buf.getvalue()) == "emmx"


def test_detect_html():
    data = b"<html><body><svg><g id='1' ed:parentid='0'>x</g></svg></body></html>"
    assert detect_format("a.html", data) == "html"


def test_detect_txt():
    data = "纯文本段落，没有任何结构。".encode("utf-8")
    assert detect_format("a.txt", data) == "txt"


# ---------------- Markdown 树解析 ----------------

MD_SAMPLE = """# Python
## 变量与数据类型
- 命名规范
  - 见名知义（不要用拼音）
- 类型
  - int / float / str
正文备注内容。
![示例](img/a.png)
"""


def test_parse_markdown_structure():
    children = parse_mindmap_markdown(MD_SAMPLE)
    assert children[0]["title"] == "Python"
    assert children[0]["level"] == 1
    branch = children[0]["children"][0]
    assert branch["title"] == "变量与数据类型"
    leaf = branch["children"][0]["children"][0]
    assert leaf["title"] == "见名知义（不要用拼音）"
    # 正文与图片归入最近的节点（- int / float / str 列表项）
    node_type = branch["children"][1]
    assert node_type["title"] == "类型"
    node_leaf = node_type["children"][0]
    assert "正文备注内容" in node_leaf["content"]
    assert node_leaf["images"][0]["src"] == "img/a.png"


def test_parse_markdown_empty():
    assert parse_mindmap_markdown("") == []
    assert parse_mindmap_markdown("只有正文没有标题") == []


# ---------------- FreeMind / XMind / OPML 合成样例 ----------------

MM_SAMPLE = """<map version="1.0.1">
  <node TEXT="根" POSITION="right">
    <node TEXT="子一"/>
    <node TEXT="子二">
      <richcontent TYPE="NOTE"><html><body><p>备注文本</p></body></html></richcontent>
    </node>
  </node>
</map>""".encode("utf-8")


def test_parse_freemind_mm():
    r = parse_any("a.mm", MM_SAMPLE)
    assert r["meta"]["format"] == "mm"
    assert r["meta"]["quality"] == "full"
    root = r["children"][0]
    assert root["title"] == "根"
    assert root["children"][1]["title"] == "子二"
    assert "备注文本" in root["children"][1]["content"]


OPML_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0"><head><title>大纲</title></head><body>
  <outline text="根" _note="根备注">
    <outline text="叶一"/>
    <outline text="叶二"/>
  </outline>
</body></opml>""".encode("utf-8")


def test_parse_opml():
    r = parse_any("a.opml", OPML_SAMPLE)
    assert r["meta"]["format"] == "opml"
    root = r["children"][0]
    assert root["title"] == "根"
    assert root["content"] == "根备注"
    assert len(root["children"]) == 2


def _xmind_bytes():
    content = json_dumps_xmind()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("content.json", content)
    return buf.getvalue()


def json_dumps_xmind():
    import json
    sheet = {
        "title": "Sheet 1",
        "rootTopic": {
            "title": "中心主题",
            "notes": {"plain": {"content": "中心备注"}},
            "children": {"attached": [
                {"title": "分支A", "children": {"attached": [{"title": "叶A1"}]}},
                {"title": "分支B"},
            ]},
        },
    }
    return json.dumps([sheet])


def test_parse_xmind():
    r = parse_any("a.xmind", _xmind_bytes())
    assert r["meta"]["format"] == "xmind"
    root = r["children"][0]
    assert root["title"] == "中心主题"
    assert root["content"] == "中心备注"
    assert root["children"][0]["title"] == "分支A"
    assert root["children"][0]["children"][0]["title"] == "叶A1"


# ---------------- 真实文件（仓库 data/aiprompt） ----------------

def test_parse_emmx_real():
    path = os.path.join(AIPROMPT_DIR, "01_Python.emmx")
    if not os.path.exists(path):
        pytest.skip("缺少真实样例 data/aiprompt/01_Python.emmx")
    with open(path, "rb") as f:
        r = parse_any("01_Python.emmx", f.read())
    assert r["meta"]["format"] == "emmx"
    assert r["meta"]["quality"] == "text-only"
    # 实测约 1000 条明文文本；断言宽松下界防抽取退化
    assert r["meta"]["node_count"] >= 300
    titles = " ".join(n["title"] for n in r["children"])
    assert "Python基础语法" in titles
    assert any("层级" in w for w in r["meta"]["warnings"])


def test_parse_edraw_html_real():
    path = os.path.join(AIPROMPT_DIR, "01_Python.html")
    if not os.path.exists(path):
        pytest.skip("缺少真实样例 data/aiprompt/01_Python.html")
    with open(path, "rb") as f:
        r = parse_any("01_Python.html", f.read())
    assert r["meta"]["format"] == "html"
    assert r["meta"]["quality"] == "full"
    # 实测 789 节点、深度 12、45+ 节点图片
    assert r["meta"]["node_count"] >= 700
    assert r["meta"]["max_depth"] >= 4
    titles = " ".join(n["title"] for n in r["children"])
    assert "Python" in titles

    def collect(ns):
        total = 0
        for n in ns:
            total += len(n["images"])
            total += collect(n["children"])
        return total

    assert collect(r["children"]) >= 20
    # 有层级：至少一个根有子节点
    assert any(n["children"] for n in r["children"])


# ---------------- 大纲往返 / 降级 / 兜底 ----------------

def test_outline_roundtrip():
    tree = {
        "meta": {"title": "根", "format": "md", "quality": "full"},
        "children": [
            {"level": 1, "title": "根", "content": "", "images": [], "children": [
                {"level": 2, "title": "分支", "content": "备注一", "images": [], "children": [
                    {"level": 3, "title": "叶子", "content": "", "images": [], "children": []},
                ]},
            ]},
        ],
    }
    md = tree_to_outline_md(tree)
    # 标题与首根同名 → 不重复输出
    assert md.count("根") == 1
    back = parse_mindmap_markdown(md)
    assert back[0]["title"] == "根"
    assert back[0]["children"][0]["title"] == "分支"
    assert back[0]["children"][0]["content"].strip() == "（备注：备注一）" or "备注一" in back[0]["children"][0]["content"]


def test_outline_roundtrip_distinct_title():
    tree = {
        "meta": {"title": "导图标题", "format": "md", "quality": "full"},
        "children": [
            {"level": 1, "title": "分支一", "content": "", "images": [], "children": []},
            {"level": 1, "title": "分支二", "content": "", "images": [], "children": []},
        ],
    }
    md = tree_to_outline_md(tree)
    lines = md.splitlines()
    assert lines[0] == "# 导图标题"
    assert "## 分支一" in lines and "## 分支二" in lines


def test_strip_tree():
    nodes = [
        {"level": 1, "title": "A", "content": "", "images": [], "children": [
            {"level": 2, "title": "A1", "content": "", "images": [], "children": [
                {"level": 3, "title": "A1x", "content": "", "images": [], "children": []},
            ]},
            {"level": 2, "title": "A2", "content": "", "images": [], "children": []},
        ]},
    ]
    stripped = strip_tree(nodes, keep_levels=2)
    assert stripped[0]["title"] == "A"
    # 保留一层叶子要点，砍掉更深层
    assert [c["title"] for c in stripped[0]["children"]] == ["A1", "A2"]
    assert stripped[0]["children"][0]["children"] == []


def test_parse_any_txt_fallback():
    # 坏 zip（PK 头 + 垃圾）→ emmx 解析失败 → txt 兜底，warnings 记录失败链
    r = parse_any("broken.emmx", b"PK\x03\x04" + b"\x00\x01garbage" * 10)
    assert r["meta"]["format"] == "txt"
    assert r["meta"]["quality"] == "flat"
    assert r["meta"]["warnings"]
    assert "无法解析" in r["meta"]["warnings"][-1]


def test_fidelity_order():
    # 保真度排序固定：html > md > xmind > mm > opml > emmx > txt
    assert FIDELITY == ["html", "md", "xmind", "mm", "opml", "emmx", "txt"]
