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

ARTICLE_PROMPT = """你是知识编辑，把思维导图大纲改写成一本**书的章节**：像技术书籍一样有「第X章 / X.Y 节」编号的线性文章，而不是带层级的要点清单。阅读体验优先。

硬约束：
1. 大纲给出的标题编号必须**原样保留**：「第X章」用 ##，「X.Y 节」用 ###，编号文字一个字都不要改
2. ### 小节标题之下全部是连贯段落（每段 80-200 字），严禁列表、要点符号、缩进层级；段落之间自然衔接
3. 大纲中没有编号标题的内容一律融入段落，不得自行加标题
4. 不得编造大纲中不存在的数字、版本号、API 名、日期；允许常识性衔接语
5. 代码、英文术语、链接原样保留（代码可以放在行内或段落中，不要用列表）
6. 内容稀少的分支并入相邻段落，不硬凑字数
7. 直接输出 Markdown 正文：不要 ``` 包裹，不要"以下是根据导图…"之类前言
8. 末尾不要加"总结"章节

大纲中的「（备注：…）」是节点备注，「（图片: …）」是图片链接——图片必须原样输出为 ![图片](链接)，放在最相关段落的后面，一张都不要丢。"""

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


def _annotate_numbers(children: list[dict]):
    """书式编号标注：一级分支 = 第X章，二级 = X.Y 节（就地写入节点 num 字段）"""
    for ci, ch in enumerate(children, 1):
        ch["num"] = f"第{ci}章"
        for si, sub in enumerate(ch.get("children", []), 1):
            sub["num"] = f"{ci}.{si}"


def _node_notes(node: dict, image_base: str) -> str:
    """节点备注与图片标注行（无标题）"""
    parts = []
    if node.get("content"):
        parts.append(f"（备注：{node['content'].strip().splitlines()[0][:120]}）")
    if image_base and node.get("images"):
        for img in node["images"]:
            # data:URI 是旧版导入残留，跳过避免 LLM 把 base64 写进笔记
            if not img["src"].startswith("data:"):
                parts.append(f"（图片: {image_base.rstrip('/')}/{img['src']}）")
    return "\n".join(parts)


def _subtree_bullets(node: dict, image_base: str) -> str:
    """更深层子树 → 缩进要点（三级以下不再编号，交给 LLM 融入段落）"""
    body = tree_to_outline_md({"children": node.get("children", [])}, image_base=image_base)
    notes = _node_notes(node, image_base)
    return "\n".join(x for x in (notes, body) if x)


def _section_outline(s: dict, image_base: str) -> str:
    """章节块 → 带书式编号的大纲文本（供 LLM 改写）"""
    if s.get("whole"):
        return ""
    node = s["node"]
    num = node.get("num", "")
    lines: list[str] = []
    if (node.get("level") or 1) <= 1:
        # 整章块：## 第X章 + 二级子节点按 X.Y 编号做 ### 小节
        if node["title"]:
            lines.append(f"## {num} {node['title']}" if num else f"## {node['title']}")
        lines.append(_node_notes(node, image_base))
        for sub in node["children"]:
            if not sub["title"]:
                continue
            sub_num = sub.get("num", "")
            lines.append(f"### {sub_num} {sub['title']}" if sub_num else f"### {sub['title']}")
            lines.append(_subtree_bullets(sub, image_base))
    else:
        # 被切分出来的节：本章首节先补 ## 第X章 章标题（否则正文里永远没有章标题）
        if s.get("lead_chapter") and len(s["path"]) > 1 and s["path"][0]:
            chapter_no = (num or "1").split(".")[0]
            lines.append(f"## 第{chapter_no}章 {s['path'][0]}")
        ctx = " > ".join(s["path"][:-1])
        lines.append(f"【上下文】{ctx}")
        if node["title"]:
            lines.append(f"### {num} {node['title']}" if num else f"### {node['title']}")
        lines.append(_subtree_bullets(node, image_base))
    return "\n".join(x for x in lines if x).strip()


def _outline_fallback(s: dict, image_base: str = "") -> str:
    """LLM 失败时的兜底：把子树压成段落式文本（书式编号标题 + 附图片）"""
    node = s["node"]
    num = node.get("num", "")
    if (node.get("level") or 1) <= 1:
        lines = [f"## {num} {node['title']}" if num else f"## {node['title']}"]
        if node.get("content"):
            lines.append(node["content"].strip())
        for sub in node["children"]:
            sub_num = sub.get("num", "")
            lines.append(f"### {sub_num} {sub['title']}" if sub_num else f"### {sub['title']}")
            lines.append(_fallback_prose(sub, image_base))
        return "\n".join(x for x in lines if x)
    lines = [f"### {num} {node['title']}" if num else f"### {node['title']}"]
    lines.append(_fallback_prose(node, image_base))
    return "\n".join(x for x in lines if x)


def _fallback_prose(node: dict, image_base: str) -> str:
    """子树 → 顿号串接的段落式文本 + 图片"""
    parts: list = []
    imgs: list = []

    def walk(nodes):
        for n in nodes:
            parts.append(f"{n['title']}：{n['content'].strip()}" if n.get("content") else n["title"])
            if image_base and n.get("images"):
                for img in n["images"]:
                    if not img["src"].startswith("data:"):
                        imgs.append(f"![图片]({image_base.rstrip('/')}/{img['src']})")
            walk(n.get("children", []))

    walk(node.get("children", []))
    lines = ["、".join(parts)] if parts else []
    lines.extend(imgs)
    return "\n".join(x for x in lines if x)


# ---------------- LLM 调用 ----------------

def _invoke_llm(model: str, user_text: str, system: str = ARTICLE_PROMPT) -> str:
    """单次调用（带重试 1 次）。模型名必须显式传——call_llm 默认名在本仓库会炸。
    reasoning=False：文章改写不需要 beta 推理端点，跳过思考 token 大幅提速。"""
    from langchain_core.messages import HumanMessage, SystemMessage
    from yuanai_core.core.lc import get_llm

    llm = get_llm(model, reasoning=False, temperature=0.3, timeout=LLM_TIMEOUT_S, usage_purpose="planet_article")
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


def _clean_article(text: str) -> str:
    """去每行首尾空白（LLM 偶带缩进，markdown 会渲染成代码块/嵌套列表）+ 压缩 3+ 空行。
    注：prompt 约束代码只允许行内/段落内，无围栏代码块，故全局去缩进安全。"""
    out: list[str] = []
    blank = 0
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(ln)
    return "\n".join(out).strip()


def _renumber_headings(text: str) -> str:
    """确定性重编号：## → 第X章（全局顺序），### → X.Y 节（章内顺序）。

    不依赖模型是否保留编号（豆包 lite 实测时丢时乱）——书式编号 100% 一致。
    标题先剥掉模型可能自带的编号前缀（第X章/数字.数字），再统一重排。"""
    out: list[str] = []
    chapter = 0
    sub = 0
    for ln in text.splitlines():
        m2 = re.match(r"^##\s+(.+)$", ln)
        m3 = re.match(r"^###\s+(.+)$", ln)
        if m2:
            chapter += 1
            sub = 0
            # 剥掉模型可能自带的编号：数字前缀（1. / 1、）与「第X章」（含抄写 prompt 的字面 X）两种
            title = re.sub(r"^\d+(\.\d+)*[\.、\s]*", "", m2.group(1))
            title = re.sub(r"^(第\s*[0-9Xx一二三四五六七八九十百]+\s*[章节篇]\s*)", "", title).strip()
            if not title:
                continue  # 空标题章：丢弃该标题行
            out.append(f"## 第{chapter}章 {title}")
        elif m3:
            sub += 1
            title = re.sub(r"^\d+(\.\d+)*[\.、\s]*", "", m3.group(1)).strip()
            if not title:
                continue  # 空标题节：丢弃该标题行
            out.append(f"### {chapter}.{sub} {title}")
        else:
            out.append(ln)
    return "\n".join(out)


def _assemble(tree: dict, drafts: list[str], model: str) -> str:
    """大树第二阶段：标题清单 → 导语 + 过渡句，注入草稿合并。
    标题兼容 ## 章 / ### 节（书式编号后分节块只有 ###）。"""
    headings = []
    for d in drafts:
        for line in d.splitlines():
            m = re.match(r"^(#{2,3})\s+(.+)$", line)
            if m:
                headings.append(m.group(2).strip())
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
            first_line = d.strip().splitlines()[0] if d.strip() else ""
            m = re.match(r"^(#{2,3})\s+(.+)$", first_line)
            if m and i > 0:
                t = trans_map.get(m.group(2).strip())
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

    _annotate_numbers(children)  # 书式编号（第X章 / X.Y 节）
    sections = build_sections(tree)
    # 分章块：每个章的第一节标记 lead_chapter（正文中唯一补章标题的位置）
    last_chapter = ""
    for s in sections:
        node = s.get("node")
        if not node or (node.get("level") or 1) <= 1:
            continue
        num = node.get("num", "1.1")
        chapter_no = num.split(".")[0]
        if chapter_no != last_chapter:
            s["lead_chapter"] = True
            last_chapter = chapter_no
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
            return "\n\n".join(_outline_fallback(s, image_base) for s in batch)

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

    content = _clean_article(content)
    content = _renumber_headings(content)
    if on_progress:
        on_progress(total, total, "完成")
    return {"content": content, "warnings": warnings}
