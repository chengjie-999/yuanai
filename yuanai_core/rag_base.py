"""
向量知识库公共基建 — 云边共用（yuanai_core/rag.py 通用知识库 + agent/rag.py 审核知识库）

共享面：文本分块（中文一级标题切分 + 定长滑窗）、标注规范文档兼容接口
（get_all_specs / split_spec_sections / search_spec_sections）、原始文本兜底、
LangChain retrieve_specification 工具工厂。

连接与 Embedding 策略、集合级构建/检索由各库自持——
yuanai_core/rag.py 面向云端通用知识库（远程 Milvus 或 .db、火山 Ark Embedding、用户隔离）；
agent/rag.py 面向本地审核库（固定 Lite 文件、按默认模型服务商选 Embedding 通道、audit_knowledge 集合）。
"""
from __future__ import annotations
import os
import re
from utils.data_path import root_path

# ====================== 配置 ======================
SPEC_FILE_PATH = os.path.join(root_path(), "data", "aiprompt", "annotation_spec.txt")
STEPS_FILE_PATH = os.path.join(root_path(), "data", "aiprompt", "audit_steps.txt")
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


# ====================== 文本切分 ======================
def chunk_text(text: str, source: str, path_prefix: str | None = None,
               level: int = 0, images: str = "[]", user_id: int = 0) -> list[dict]:
    """按一级标题（一、二、…）切分 + 定长滑窗，返回 [{text, title, source, ...}]。

    path_prefix 非 None 时附带 path/level/images/user_id 元数据（通用知识库检索展示用）；
    默认只出 {text, title, source}（审核知识库契约）。
    """
    chunks = []
    sections = re.split(r'\n(?=[一二三四五六七八九十]、)', text)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split('\n')
        title = lines[0].strip()
        body = '\n'.join(lines)
        base: dict = {"source": source}
        if path_prefix is not None:
            base.update({
                "path": f"{path_prefix} > {title}",
                "level": level,
                "images": images,
                "user_id": user_id,
            })
        if len(body) > CHUNK_SIZE:
            for i in range(0, len(body), CHUNK_SIZE - CHUNK_OVERLAP):
                chunk = body[i:i + CHUNK_SIZE]
                if chunk.strip():
                    chunks.append({"text": chunk, "title": title, **base})
        else:
            chunks.append({"text": body, "title": title, **base})
    return chunks


# ====================== 规范文档兼容接口（两库共用同一 aiprompt 文件） ======================
def get_all_specs() -> str:
    """获取全部规范（兼容旧接口）"""
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def split_spec_sections() -> list:
    """将标注规范按一级标题切分为段落列表 [(标题, 正文)]（兼容旧接口）"""
    text = get_all_specs()
    if not text:
        return []
    chunks = re.split(r'\n(?=[一二三四五六七八九十]、)', text)
    result = []
    for c in chunks:
        lines = c.strip().split('\n')
        title = lines[0].strip() if lines else ""
        result.append((title, c.strip()))
    return result


def search_spec_sections(keyword: str = "") -> str:
    """按关键词检索规范段落（兼容旧接口，降级为非向量匹配）"""
    sections = split_spec_sections()
    if not sections:
        return ""
    if not keyword:
        return "\n\n".join(c for _, c in sections)
    keyword_lower = keyword.lower()
    matched = [c for t, c in sections if keyword_lower in c.lower()]
    return "\n\n".join(matched) if matched else (sections[0][1] if sections else "")


def get_all_raw_text() -> str:
    """无向量库时直接返回原始文本（降级方案）"""
    parts = []
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            parts.append(f.read())
    if os.path.exists(STEPS_FILE_PATH):
        with open(STEPS_FILE_PATH, "r", encoding="utf-8") as f:
            parts.append(f.read())
    return "\n\n".join(parts)


# ====================== LangChain Tool 工厂 ======================
def make_retrieve_specification(get_all_specs_fn, search_spec_fn):
    """retrieve_specification 工具工厂——各库绑定自己的 search_spec（检索各自集合）。

    返回 LangChain tool；langchain_core 不可用时返回 None（__all__ 相应不含该工具）。
    """
    try:
        from langchain_core.tools import tool
    except ImportError:
        return None

    @tool
    def retrieve_specification(query: str = "") -> str:
        """
        检索数据标注规范，需要判断内容是否合规时调用。
        输入：待审核的内容关键词（必填，如 '独立批改' '黄框' '举报'）
        输出：相关规范段落
        """
        if not query:
            return get_all_specs_fn()
        return search_spec_fn(query)

    return retrieve_specification
