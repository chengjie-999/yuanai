"""文章化转换管线单测 — mock LLM 调用，不花钱

运行：pytest test/test_planet_convert.py -v
"""
import pytest

from yuanai_core.planet_convert import (
    ARTICLE_PROMPT,
    BUDGET_CHARS,
    build_sections,
    convert_tree,
    plan_batches,
)
from yuanai_core.pure.mindmap_parser import tree_to_outline_md


def _leaf(title: str, level: int, content: str = ""):
    return {"level": level, "title": title, "content": content, "images": [], "children": []}


def _branch(title: str, level: int, kids: list):
    return {"level": level, "title": title, "content": "", "images": [], "children": kids}


@pytest.fixture
def small_tree():
    return {
        "meta": {"title": "Python 基础", "format": "md", "quality": "full",
                 "node_count": 9, "max_depth": 4},
        "children": [
            _branch("变量与类型", 1, [
                _branch("命名规范", 2, [
                    _leaf("见名知义", 3, "不要用拼音"),
                    _leaf("下划线分隔", 3),
                ]),
                _branch("类型", 2, [
                    _leaf("int/float/str", 3),
                ]),
            ]),
            _branch("流程控制", 1, [
                _leaf("if 条件判断", 2),
                _leaf("for 循环", 2),
            ]),
        ],
    }


def test_build_sections(small_tree):
    sections = build_sections(small_tree)
    assert len(sections) == 2  # 两个一级分支
    assert [s["title"] for s in sections] == ["变量与类型", "流程控制"]


def test_plan_batches_pack(small_tree):
    sections = build_sections(small_tree)
    batches = plan_batches(sections, budget=BUDGET_CHARS)
    assert len(batches) == 1  # 小树单箱


def test_plan_batches_split_large():
    # 构造多个大分支逼出多箱：每分支塞 3000 字备注
    big = {"meta": {"title": "t", "max_depth": 2}, "children": []}
    for i in range(5):
        big["children"].append(_branch(f"分支{i}", 1, [
            _leaf("叶子", 2, content="x" * 3000),
        ]))
    sections = build_sections(big)
    batches = plan_batches(sections)
    assert len(batches) >= 2


def test_convert_tree_single_batch(small_tree, monkeypatch):
    calls = []

    def fake_llm(model, user_text, system=ARTICLE_PROMPT):
        calls.append(user_text)
        return "## 变量与类型\n扩写后的段落内容。\n## 流程控制\n条件与循环的说明。\n"

    monkeypatch.setattr("yuanai_core.planet_convert._invoke_llm", fake_llm)

    progress = []
    result = convert_tree(small_tree, model="deepseek-v4-flash",
                          on_progress=lambda d, t, m: progress.append((d, t, m)))
    assert "变量与类型" in result["content"]
    assert "流程控制" in result["content"]
    assert result["warnings"] == []
    assert len(calls) == 1
    assert progress[-1][0] == progress[-1][1]  # 最终 done==total


def test_convert_tree_batch_failure_fallback(small_tree, monkeypatch):
    """单箱 LLM 失败 → 大纲原文兜底，其余箱继续，任务不整体失败"""
    from yuanai_core.planet_convert import build_sections as bs

    def fake_llm(model, user_text, system=ARTICLE_PROMPT):
        raise RuntimeError("模拟 LLM 抖动")

    monkeypatch.setattr("yuanai_core.planet_convert._invoke_llm", fake_llm)
    result = convert_tree(small_tree, model="deepseek-v4-flash")
    assert result["warnings"], "失败应有 warnings"
    assert "变量与类型" in result["content"], "兜底应保留大纲标题"
    assert "见名知义" in result["content"]


def test_convert_tree_large_two_phase(monkeypatch):
    """大树触发两阶段：逐箱 + 装配"""
    big = {"meta": {"title": "大树", "max_depth": 5}, "children": []}
    for i in range(3):
        big["children"].append(_branch(f"章{i}", 1, [
            _branch(f"节{i}a", 2, [_leaf("点", 3, "y" * 5000)]),
            _branch(f"节{i}b", 2, [_leaf("点", 3, "y" * 5000)]),
        ]))

    def fake_llm(model, user_text, system=ARTICLE_PROMPT):
        if system == ARTICLE_PROMPT:
            # 书式编号后分节块只有 ### 标题
            heads = [ln for ln in user_text.splitlines() if ln.startswith("### ") or ln.startswith("## ")]
            return "\n".join(f"{h}\n{draft}段落。" for h, draft in zip(heads, ["甲", "乙"]))
        # 装配调用：从 system 的标题清单里取前两个真实标题做过渡
        import re as _re
        heads = [ln for ln in system.splitlines() if _re.fullmatch(r"\d+\.\d+.*", ln.strip())]
        t1 = heads[0] if heads else "1.1 节0a"
        t2 = heads[1] if len(heads) > 1 else "1.2 节0b"
        return f"这是导语段落。\n<!--break-->\n1. {t1}: 过渡一\n2. {t2}: 过渡二"

    monkeypatch.setattr("yuanai_core.planet_convert._invoke_llm", fake_llm)
    result = convert_tree(big, model="deepseek-v4-flash")
    assert "这是导语段落" in result["content"]
    # 第一章不加过渡（prompt 约定「除第一章外」），第二章起注入
    assert "过渡二" in result["content"]


def test_renumber_headings():
    from yuanai_core.planet_convert import _renumber_headings

    raw = """导语段。

## 1. 基础语法（模型乱编号）
段落甲。
### 变量
段落乙。
## 第3章 流程控制
段落丙。
### 1.4 空值：NoneType
段落丁。"""
    out = _renumber_headings(raw)
    lines = out.splitlines()
    assert "## 第1章 基础语法（模型乱编号）" in lines
    assert "### 1.1 变量" in lines
    assert "## 第2章 流程控制" in lines
    assert "### 2.1 空值：NoneType" in lines


def test_clean_article_dedent():
    from yuanai_core.planet_convert import _clean_article

    raw = "  段落一  \n\n\n\n  段落二\n  段落三\n"
    out = _clean_article(raw)
    assert out == "段落一\n\n段落二\n段落三"


def test_outline_with_image_base(small_tree):
    small_tree["children"][0]["children"][0]["images"] = [{"alt": "", "src": "img1.png"}]
    md = tree_to_outline_md(small_tree, image_base="/api/v1/planet/asset/1/2")
    assert "（图片: /api/v1/planet/asset/1/2/img1.png）" in md
