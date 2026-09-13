"""导图树 → 文章化线性笔记（LLM 转换管线，纯逻辑 + get_llm，不依赖 FastAPI）

分块策略：按一级/二级分支装箱（缩进大纲文本，省 token、模型更听话），
单分支超预算沿子分支二次切分，祖先路径作为上下文头；大树两阶段
（逐箱草稿 → 标题清单生成导语+过渡句回填）；MAX_LLM_CALLS 硬上限，
超出 strip_tree 降级单次生成；单箱失败落大纲原样——永不因一次 LLM 抖动丢掉整篇笔记。
"""
from __future__ import annotations

import re
import threading

from yuanai_core.pure.mindmap_parser import strip_tree, tree_to_outline_md

BUDGET_CHARS = 6000          # 单箱输入预算（中文≈1 token/字）
MAX_LLM_CALLS = 12           # 硬上限：超出即降级
LARGE_TREE_CHARS = 5 * BUDGET_CHARS
LARGE_TREE_DEPTH = 4
LLM_TIMEOUT_S = 120
PARALLEL_BATCHES = 3         # 并发箱数：豆包实测 ~28 字/秒，串行 11 箱要 30 分钟，并行砍到 1/3

ARTICLE_PROMPT = """你是知识编辑，把思维导图大纲改写成一篇可读的线性笔记文章，阅读体验优先。

硬约束：
1. 大纲中每一层标题保留为 Markdown 标题（一级分支用 ##，二级用 ###），标题文字不改写
2. 每个叶子要点扩写为完整段落（每段 80-200 字），保持信息完整，不遗漏大纲中的任何要点
3. 不得编造大纲中不存在的数字、版本号、API 名、日期；允许常识性衔接语
4. 代码、英文术语、链接原样保留
5. 仅并列项 ≥3 时使用列表，其余用连贯段落
6. 直接输出 Markdown 正文：不要 ``` 包裹，不要"以下是根据导图…"之类前言
7. 内容稀少的分支并入相邻段落，不硬凑字数
8. 末尾不要加"总结"章节

大纲中的「（备注：…）」是节点备注，「（图片: …）」是图片链接，图片按原位置输出为 ![图片](链接)。"""

ASSEMBLE_PROMPT = """你是知识编辑。下面是笔记的章节标题清单，请为整篇笔记写一段 3-5 句的导语，并为除第一章外的每个章节写一句不超过 30 字的过渡句。

章节标题清单：
{headings}

直接输出，格式如下（导语与清单之间用单独一行 <!--break--> 分隔）：
<导语段落>
<!--break-->
1. <章节名>: <过渡句>
2. <章节名>: <过渡句>"""


# ---------------- 分块 ----------------

def _outline_of(tree: dict, image_base: str = "") -> str:
    return tree_to_outline_md(tree, image_base=image_base)


def _outline_size(nodes: list, path: str = "") -> int:
    """粗略字符数（用于分箱判断）"""
    total = 0
    for n in nodes:
        cur = (path + " > " if path else "") + n["title"]
        total += len(cur) + len(n.get("content", ""))
        total += _outline_size(n["children"], cur)
    return total


def build_sections(tree: dict) -> list[dict]:
    """把树切成「章节块」：一级分支为章；章超预算时二级分支为节（带祖先上下文头）"""
    children = tree.get("children", [])
    title = tree.get("meta", {}).get("title", "")
    sections: list[dict] = []

    def walk(node: dict, ancestors: list, level: int):
        path = ancestors + [node["title"]]
        size = _outline_size([node])
        if size <= BUDGET_CHARS:
            sections.append({"path": path, "title": node["title"], "node": node})
            return
        # 超预算：沿子分支切分
        if node["children"]:
            for c in node["children"]:
                walk(c, path, level + 1)
        else:
            sections.append({"path": path, "title": node["title"], "node": node})

    for c in children:
        walk(c, [], 1)

    # 无分支可用（空树/单根）→ 整树一块
    if not sections and children:
        sections = [{"path": [], "title": title, "node": None, "whole": True}]
    return sections


def plan_batches(sections: list[dict], budget: int = BUDGET_CHARS) -> list[list[dict]]:
    """按序装箱，每箱 ≤ budget，绝不在分支中间切"""
    batches: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for s in sections:
        s_size = _outline_size([s["node"]]) if s.get("node") else budget
        if current and size + s_size > budget:
            batches.append(current)
            current, size = [], 0
        current.append(s)
        size += s_size
    if current:
        batches.append(current)
    return batches


def _section_outline(s: dict, image_base: str) -> str:
    if s.get("whole"):
        return ""
    node = s["node"]
    header = f"【上下文】{' > '.join(s['path'][:-1])}" if len(s["path"]) > 1 else ""
    body = tree_to_outline_md({"children": [node]}, image_base=image_base)
    return (header + "\n" + body).strip()


def _outline_fallback(s: dict) -> str:
    """LLM 失败时的兜底：大纲原样转成标题+列表 markdown"""
    node = s["node"]
    lines = [f"## {node['title']}"]
    if node.get("content"):
        lines.append(node["content"].strip())

    def walk(nodes, indent):
        for n in nodes:
            lines.append("  " * indent + "- " + n["title"])
            if n.get("content"):
                lines.append("  " * (indent + 1) + n["content"].strip())
            walk(n["children"], indent + 1)

    walk(node["children"], 1)
    return "\n".join(lines)


# ---------------- LLM 调用 ----------------

def _invoke_llm(model: str, user_text: str, system: str = ARTICLE_PROMPT) -> str:
    """单次调用（带重试 1 次）。模型名必须显式传——call_llm 默认名在本仓库会炸。
    reasoning=False：文章改写不需要 beta 推理端点，跳过思考 token 大幅提速。"""
    from langchain_core.messages import HumanMessage, SystemMessage
    from yuanai_core.core.lc import get_llm

    llm = get_llm(model, reasoning=False, temperature=0.3, timeout=LLM_TIMEOUT_S)
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            # langchain 的 timeout 参数实测不可靠（个别请求无限挂起），用并发 future 硬性限时。
            # 注意：不能用 with（__exit__ 会 shutdown(wait=True) 等待挂起线程，等于没超时），
            # 必须 shutdown(wait=False) 让挂起线程在守护线程池里自行飘散。
            import concurrent.futures
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = pool.submit(
                    llm.invoke, [SystemMessage(content=system), HumanMessage(content=user_text)])
                resp = future.result(timeout=LLM_TIMEOUT_S)
            finally:
                pool.shutdown(wait=False)
            content = resp.content if hasattr(resp, "content") else str(resp)
            content = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", content.strip())
            if content:
                return content
        except concurrent.futures.TimeoutError:
            last_err = TimeoutError(f"LLM 调用超时（>{LLM_TIMEOUT_S}s，第 {attempt + 1} 次）")
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"LLM 调用失败: {last_err}")


def _assemble(tree: dict, drafts: list[str], model: str) -> str:
    """大树第二阶段：标题清单 → 导语 + 过渡句，注入草稿合并"""
    headings = []
    for d in drafts:
        for line in d.splitlines():
            if line.startswith("## "):
                headings.append(line[3:].strip())
                break
    if len(headings) <= 1:
        return "\n\n".join(drafts)
    try:
        raw = _invoke_llm(model, "", system=ASSEMBLE_PROMPT.format(headings="\n".join(headings)))
        intro, _, transitions = raw.partition("<!--break-->")
        intro = intro.strip()
        trans_map: dict[str, str] = {}
        for line in transitions.splitlines():
            m = re.match(r"^\d+\.\s*(.+?)[:：]\s*(.+)$", line.strip())
            if m:
                trans_map[m.group(1).strip()] = m.group(2).strip()
        parts = []
        if intro:
            parts.append(intro + "\n")
        for i, d in enumerate(drafts):
            first = next((l for l in d.splitlines() if l.startswith("## ")), "")
            if first and i > 0:
                t = trans_map.get(first[3:].strip())
                if t:
                    parts.append(f"*{t}*\n")
            parts.append(d)
        return "\n\n".join(parts)
    except Exception:  # 装配失败不致命：直接拼接草稿
        return "\n\n".join(drafts)


# ---------------- 主流程 ----------------

def convert_tree(tree: dict, model: str, image_base: str = "",
                 on_progress=None) -> dict:
    """导图树 → {content, warnings}。on_progress(done, total, message) 每步回调。"""
    warnings: list[str] = []
    children = tree.get("children", [])
    total_chars = _outline_size(children)
    max_depth = tree.get("meta", {}).get("max_depth", 0)

    sections = build_sections(tree)
    is_large = total_chars > LARGE_TREE_CHARS or max_depth > LARGE_TREE_DEPTH

    if is_large and len(plan_batches(sections)) > MAX_LLM_CALLS:
        stripped = strip_tree(children, keep_levels=3)
        tree = {"meta": tree.get("meta", {}), "children": stripped}
        warnings.append("导图过大，已裁剪至 3 层要点后生成（完整内容可在导图视图查看）")
        sections = build_sections(tree)

    batches = plan_batches(sections)
    total = len(batches) + (1 if is_large and len(batches) > 1 else 0)
    drafts: list[str] = []
    done_count = 0
    lock = threading.Lock()

    def gen_one(i: int, batch: list[dict]) -> str:
        """单箱生成（线程池内并发执行）；失败落大纲原样"""
        user_text = "\n\n".join(_section_outline(s, image_base) for s in batch)
        try:
            return _invoke_llm(model, user_text)
        except Exception as e:  # noqa: BLE001
            with lock:
                warnings.append(f"第 {i + 1} 箱生成失败（{e}），已用大纲原文兜底")
            return "\n\n".join(_outline_fallback(s) for s in batch)

    if len(batches) > 1:
        # 并发生成（豆包 28 字/秒串行太慢，PARALLEL_BATCHES 并发砍总时长）
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_BATCHES) as pool:
            futures = [pool.submit(gen_one, i, b) for i, b in enumerate(batches)]
            for fut in futures:
                drafts.append(fut.result())
                done_count += 1
                if on_progress:
                    on_progress(done_count, total, f"生成章节 {done_count}/{len(batches)}")
    else:
        for i, batch in enumerate(batches):
            drafts.append(gen_one(i, batch))
            done_count += 1
            if on_progress:
                on_progress(done_count, total, f"生成章节 {done_count}/{len(batches)}")

    if is_large and len(batches) > 1:
        if on_progress:
            on_progress(len(batches), total, "装配导语与章节过渡")
        content = _assemble(tree, drafts, model)
    else:
        content = "\n\n".join(drafts)

    if on_progress:
        on_progress(total, total, "完成")
    return {"content": content.strip(), "warnings": warnings}
