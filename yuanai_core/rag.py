"""
向量知识库 — Milvus + OpenAI 兼容 Embedding API
开发模式: Milvus Lite (嵌入式，免 Docker)
生产模式: Milvus Standalone/Cluster (改连接地址即可，API 不变)

支持数据源:
  - data/aiprompt/*.txt         纯文本规范文档
  - data/aiprompt/**/*.md       思维导图 Markdown 导出（支持嵌套文件夹）
"""
from __future__ import annotations
import os
import re
import time
import json
import hashlib
import threading
from contextvars import ContextVar
import numpy as np
from openai import OpenAI
from pymilvus import MilvusClient
from config.settings import DEFAULT_MODEL, MODELS
from utils.data_path import root_path
from utils.sensitive_data import get_api_key

# ====================== 配置 ======================
AIPROMPT_DIR = os.path.join(root_path(), "data", "aiprompt")
SPEC_FILE_PATH = os.path.join(AIPROMPT_DIR, "annotation_spec.txt")
STEPS_FILE_PATH = os.path.join(AIPROMPT_DIR, "audit_steps.txt")
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "knowledge_base"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
TOP_K = 10

EMBEDDING_DIM = 1024

_client: OpenAI | None = None
_db: MilvusClient | None = None
_db_lock = threading.RLock()  # 保护集合创建/写入并发（可重入）
current_user_id: ContextVar[int] = ContextVar("kb_user_id", default=0)  # 当前检索用户上下文


# ====================== Embedding ======================
def _get_openai_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    # Embedding 模型始终用火山引擎 Ark（与对话模型无关）
    api_key = get_api_key("seed")
    base_url = "https://ark.cn-beijing.volces.com/api/v3"

    _client = OpenAI(api_key=api_key, base_url=base_url)
    return _client


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _get_openai_client()
    model = os.getenv("EMBEDDING_MODEL", "")
    if not model:
        print("⚠️ 未配置 EMBEDDING_MODEL 环境变量")
        return [[0.0] * EMBEDDING_DIM for _ in texts]
    try:
        all_embeddings = []
        batch_size = 256  # Ark API 单次最多 256 条
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = client.embeddings.create(model=model, input=batch)
            all_embeddings.extend([d.embedding for d in resp.data])
        return all_embeddings
    except Exception as e:
        print(f"⚠️ Embedding API 调用失败: {e}")
        return [[0.0] * EMBEDDING_DIM for _ in texts]


# ====================== Milvus ======================
def _get_db() -> MilvusClient:
    global _db
    if _db is not None:
        return _db
    uri = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
    _db = MilvusClient(uri=uri)
    return _db


# ====================== Markdown 思维导图解析 ======================
def _parse_mindmap_md(filepath: str) -> list[dict]:
    """解析 Markdown 文件：heading (#) + 列表项 (-) 共同构成树形结构"""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    root = {"level": 0, "title": "ROOT", "children": [], "content": "", "images": []}
    stack = [root]
    # 记录当前 heading 的层级，用于计算列表项的有效层级
    current_heading_level = 0

    for line in lines:
        h_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        list_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)

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
            # 列表项层级 = 当前 heading 层级 + 缩进层级（每 2 空格 = 1 级，最小 +1）
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
                for m in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', stripped):
                    stack[-1]["images"].append({"alt": m.group(1), "src": m.group(2)})

    return root["children"]


def _flatten_tree(nodes: list[dict], folder: str, path: str = "", user_id: int = 0) -> list[dict]:
    """将树形节点拍平为知识块"""
    results = []
    for node in nodes:
        current_path = f"{path} > {node['title']}" if path else node["title"]

        text_parts = [node["title"]]
        if node["content"]:
            text_parts.append(node["content"].strip())
        text_parts.append(f"({current_path})")
        if node["images"]:
            imgs = ", ".join(img["src"] for img in node["images"])
            text_parts.append(f"[图片: {imgs}]")

        results.append({
            "text": "\n".join(text_parts),
            "title": node["title"],
            "path": current_path,
            "level": node["level"],
            "source": folder,
            "user_id": user_id,
            "images": json.dumps([i["src"] for i in node["images"]], ensure_ascii=False),
        })
        results.extend(_flatten_tree(node["children"], folder, current_path, user_id))
    return results


def _scan_mindmap_folders() -> dict[str, list[dict]]:
    """递归扫描 aiprompt 目录下所有 Markdown 文件，支持嵌套文件夹"""
    if not os.path.isdir(AIPROMPT_DIR):
        return {}

    seen_hashes = {}
    sources = {}

    for dirpath, dirnames, filenames in os.walk(AIPROMPT_DIR):
        md_files = [f for f in filenames if f.endswith(".md")]
        if not md_files:
            continue

        for md_file in md_files:
            md_path = os.path.join(dirpath, md_file)
            content_hash = hashlib.md5(open(md_path, "rb").read()).hexdigest()

            # source 命名：去除冗余（文件夹名 = md 名时只用文件夹名）
            rel_dir = os.path.relpath(dirpath, AIPROMPT_DIR).replace("\\", "/")
            md_stem = os.path.splitext(md_file)[0]
            folder_name = os.path.basename(dirpath)
            if folder_name == md_stem:
                source = (rel_dir + "/").replace("./", "") if rel_dir != "." else md_stem
                source = source.rstrip("/")
            else:
                source = f"{rel_dir}/{md_stem}" if rel_dir != "." else md_stem

            if content_hash in seen_hashes:
                print(f"  ⏭️  {source}  内容与 {seen_hashes[content_hash]} 相同，已跳过")
                continue
            seen_hashes[content_hash] = source

            tree = _parse_mindmap_md(md_path)
            chunks = _flatten_tree(tree, folder=source)
            if chunks:
                sources[source] = chunks
                img_count = len([f for f in filenames if f.endswith(".png")])
                print(f"  📄 {source}  → {len(chunks)} chunks (图片 {img_count} 张)")

    return sources


# ====================== 文本切分 ======================
def _chunk_text(text: str, source: str) -> list[dict]:
    chunks = []
    sections = re.split(r'\n(?=[一二三四五六七八九十]、)', text)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split('\n')
        title = lines[0].strip()
        body = '\n'.join(lines)
        base = {"source": source, "path": f"{source} > {title}", "level": 2, "images": "[]", "user_id": 0}
        if len(body) > CHUNK_SIZE:
            for i in range(0, len(body), CHUNK_SIZE - CHUNK_OVERLAP):
                chunk = body[i:i + CHUNK_SIZE]
                if chunk.strip():
                    chunks.append({"text": chunk, "title": title, **base})
        else:
            chunks.append({"text": body, "title": title, **base})
    return chunks


# ====================== 知识库构建 ======================
def build_knowledge_base(force_rebuild: bool = False) -> bool:
    db = _get_db()

    if db.has_collection(COLLECTION_NAME) and not force_rebuild:
        print("✅ 知识库已存在")
        return True

    print("🔍 扫描知识文档...")

    all_chunks: list[dict] = []

    # 1. 纯文本文档
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            all_chunks.extend(_chunk_text(f.read(), "annotation_spec"))
        print(f"  📝 annotation_spec.txt")

    if os.path.exists(STEPS_FILE_PATH):
        with open(STEPS_FILE_PATH, "r", encoding="utf-8") as f:
            all_chunks.extend(_chunk_text(f.read(), "audit_steps"))
        print(f"  📝 audit_steps.txt")

    # 2. 思维导图 Markdown 文件夹
    mindmap_sources = _scan_mindmap_folders()
    for chunks in mindmap_sources.values():
        all_chunks.extend(chunks)

    if not all_chunks:
        print("⚠️ 无知识文档可索引")
        return False

    # 获取向量
    texts = [c["text"] for c in all_chunks]
    print(f"\n🔨 正在为 {len(texts)} 个文本块生成向量...")
    start = time.time()
    embeddings = get_embeddings(texts)
    print(f"   向量生成完成，耗时 {time.time() - start:.1f}s")

    # 重建集合（加锁保护）
    data = []
    for i, chunk in enumerate(all_chunks):
        data.append({
            "id": i,
            "vector": embeddings[i],
            "text": chunk["text"],
            "title": chunk["title"],
            "source": chunk["source"],
            "path": chunk.get("path", ""),
            "level": chunk.get("level", 0),
            "images": chunk.get("images", "[]"),
            "user_id": chunk.get("user_id", 0),
        })

    with _db_lock:
        if db.has_collection(COLLECTION_NAME):
            db.drop_collection(COLLECTION_NAME)
        db.create_collection(COLLECTION_NAME, dimension=EMBEDDING_DIM)
        db.insert(COLLECTION_NAME, data)

    # 统计
    sources = {}
    for c in all_chunks:
        src = c["source"]
        sources[src] = sources.get(src, 0) + 1

    print(f"\n✅ 知识库构建完成，共 {len(data)} 条")
    for src, count in sorted(sources.items()):
        print(f"   {src}: {count} chunks")
    return True


# ====================== 增量操作 ======================
def _ensure_collection():
    """确保集合存在，不存在则创建（线程安全）"""
    db = _get_db()
    with _db_lock:
        if not db.has_collection(COLLECTION_NAME):
            db.create_collection(COLLECTION_NAME, dimension=EMBEDDING_DIM)


def _get_max_id() -> int:
    """获取集合中最大的 ID"""
    db = _get_db()
    if not db.has_collection(COLLECTION_NAME):
        return 0
    try:
        results = db.query(
            COLLECTION_NAME,
            filter="id >= 0",
            output_fields=["id"],
            limit=16384,
        )
        if not results:
            return 0
        return max(r["id"] for r in results)
    except Exception:
        return 0


def remove_source(source: str, user_id: int | None = None) -> int:
    """删除指定来源的所有 chunk（可选按 user_id 限定），返回删除数"""
    db = _get_db()
    if not db.has_collection(COLLECTION_NAME):
        return 0
    filter_parts = [f'source == "{source}"']
    if user_id is not None:
        filter_parts.append(f'user_id == {user_id}')
    try:
        results = db.query(
            COLLECTION_NAME,
            filter=" and ".join(filter_parts),
            output_fields=["id"],
            limit=16384,
        )
    except Exception:
        return 0
    if not results:
        return 0
    ids = [r["id"] for r in results]
    db.delete(COLLECTION_NAME, ids=ids)
    return len(ids)


def add_source_chunks(chunks: list[dict]) -> int:
    """将 chunk 列表生成向量并插入集合，返回插入数"""
    if not chunks:
        return 0

    db = _get_db()
    _ensure_collection()

    texts = [c["text"] for c in chunks]
    print(f"  🔨 生成 {len(texts)} 条向量...")
    start = time.time()
    embeddings = get_embeddings(texts)
    print(f"     耗时 {time.time() - start:.1f}s")

    next_id = _get_max_id() + 1
    data = []
    for i, chunk in enumerate(chunks):
        data.append({
            "id": next_id + i,
            "vector": embeddings[i],
            "text": chunk["text"],
            "title": chunk["title"],
            "source": chunk["source"],
            "path": chunk.get("path", ""),
            "level": chunk.get("level", 0),
            "images": chunk.get("images", "[]"),
            "user_id": chunk.get("user_id", 0),
        })

    with _db_lock:
        db.insert(COLLECTION_NAME, data)
    return len(data)


def get_source_stats() -> list[dict]:
    """获取各来源的统计信息"""
    db = _get_db()
    if not db.has_collection(COLLECTION_NAME):
        return []
    try:
        results = db.query(
            COLLECTION_NAME,
            filter="id >= 0",
            output_fields=["source", "level", "images", "user_id"],
            limit=16384,
        )
    except Exception:
        return []

    stats: dict[str, dict] = {}
    for r in results:
        src = r.get("source", "")
        if src not in stats:
            stats[src] = {"source": src, "chunks": 0, "images": 0, "user_id": r.get("user_id", 0)}
        stats[src]["chunks"] += 1
        imgs = r.get("images", "[]")
        if imgs and imgs != "[]":
            try:
                stats[src]["images"] += len(json.loads(imgs))
            except (json.JSONDecodeError, Exception):
                pass

    return sorted(stats.values(), key=lambda x: x["chunks"], reverse=True)


# ====================== 检索 ======================
def search_knowledge(query: str, top_k: int = TOP_K, source: str | None = None,
                     user_id: int | None = None) -> str:
    """
    向量检索知识库。
    user_id=None   → 仅检索共享知识（user_id=0）
    user_id=123    → 检索共享 + 该用户的私有知识
    """
    if not query.strip():
        return ""

    db = _get_db()
    if not db.has_collection(COLLECTION_NAME):
        if not build_knowledge_base():
            return _get_all_raw_text()

    embeddings = get_embeddings([query])
    if not embeddings or all(v == 0 for v in embeddings[0]):
        return _get_all_raw_text()[:2000]

    # 构建过滤条件
    filters = []
    if source:
        filters.append(f'source == "{source}"')
    if user_id is not None:
        filters.append(f'(user_id == 0 or user_id == {user_id})')

    filter_expr = " and ".join(filters) if filters else None
    output_fields = ["text", "title", "source", "path", "images", "user_id"]

    try:
        results = db.search(
            COLLECTION_NAME,
            data=[embeddings[0]],
            limit=top_k,
            output_fields=output_fields,
            filter=filter_expr,
        )
    except Exception:
        # 旧集合缺少 path/level/images 字段时回退
        results = db.search(
            COLLECTION_NAME,
            data=[embeddings[0]],
            limit=top_k,
            output_fields=["text", "title", "source"],
            filter=filter_expr,
        )

    if not results or not results[0]:
        return _get_all_raw_text()[:2000]

    chunks = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        src = entity.get("source", "")
        title = entity.get("title", "")
        text = entity.get("text", "")
        path = entity.get("path", "")
        images = entity.get("images", "[]")

        header = f"[{src}] {path or title}"
        chunks.append(header + "\n" + text)

        if images and images != "[]":
            try:
                imgs = json.loads(images)
                for img in imgs:
                    # 返回可访问的 URL，前端 Markdown 渲染器可直接显示
                    img_url = f"/api/v1/knowledge/img/{src}/{img}"
                    chunks.append(f"  ![图片]({img_url})")
            except (json.JSONDecodeError, Exception):
                pass

    return "\n---\n".join(chunks)


def search_spec(query: str) -> str:
    return search_knowledge(query, source="annotation_spec")


def search_steps(query: str) -> str:
    return search_knowledge(query, source="audit_steps")


def _get_all_raw_text() -> str:
    parts = []
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            parts.append(f.read())
    if os.path.exists(STEPS_FILE_PATH):
        with open(STEPS_FILE_PATH, "r", encoding="utf-8") as f:
            parts.append(f.read())
    return "\n\n".join(parts)


def list_knowledge_sources() -> list[str]:
    """列出所有已索引的知识库来源"""
    db = _get_db()
    if not db.has_collection(COLLECTION_NAME):
        return []
    sources = set()
    # 简单查询所有数据
    try:
        results = db.query(
            COLLECTION_NAME,
            filter='id >= 0',
            output_fields=["source"],
            limit=10000,
        )
    except Exception:
        return []
    for r in results:
        sources.add(r.get("source", ""))
    return sorted(sources)


# ====================== 兼容旧接口 ======================
def get_all_specs() -> str:
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def search_annotation_spec(query: str) -> str:
    return search_spec(query)


def split_spec_sections() -> list:
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
    sections = split_spec_sections()
    if not sections:
        return ""
    if not keyword:
        return "\n\n".join(c for _, c in sections)
    keyword_lower = keyword.lower()
    matched = [c for t, c in sections if keyword_lower in c.lower()]
    return "\n\n".join(matched) if matched else (sections[0][1] if sections else "")


def rebuild_vector_store():
    build_knowledge_base(force_rebuild=True)


# ====================== LangChain Tool ======================
try:
    from langchain_core.tools import tool

    @tool
    def retrieve_knowledge(query: str) -> str:
        """
        从知识库中检索相关内容，包括 Python 笔记、标注规范、操作步骤等。
        当用户询问技术知识、编程问题、标注规范时调用。
        输入：查询关键词或问题（如 'Python for循环' '数据标注规范'）
        输出：知识库中语义最相关的段落及其路径
        """
        if not query:
            return "知识库包含: " + ", ".join(list_knowledge_sources())
        return search_knowledge(query)

    @tool
    def retrieve_specification(query: str = "") -> str:
        """
        检索数据标注规范，需要判断内容是否合规时调用。
        输入：待审核的内容关键词（必填，如 '独立批改' '黄框' '举报'）
        输出：相关规范段落
        """
        if not query:
            return get_all_specs()
        return search_spec(query)

    __all__ = [
        "retrieve_knowledge", "retrieve_specification",
        "search_knowledge", "search_spec", "search_steps",
        "search_annotation_spec", "get_all_specs", "search_spec_sections",
        "split_spec_sections", "get_embeddings",
        "build_knowledge_base", "rebuild_vector_store", "list_knowledge_sources",
        "add_source_chunks", "remove_source", "get_source_stats",
    ]
except ImportError:
    __all__ = [
        "search_knowledge", "search_spec", "search_steps",
        "search_annotation_spec", "get_all_specs", "search_spec_sections",
        "split_spec_sections", "get_embeddings",
        "build_knowledge_base", "rebuild_vector_store", "list_knowledge_sources",
        "add_source_chunks", "remove_source", "get_source_stats",
    ]
