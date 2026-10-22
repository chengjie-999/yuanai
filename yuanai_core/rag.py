"""
向量知识库 — Milvus + OpenAI 兼容 Embedding API
开发模式: Milvus Lite (嵌入式，免 Docker)
生产模式: Milvus Standalone/Cluster (改连接地址即可，API 不变)

支持数据源:
  - data/aiprompt/*.txt         纯文本规范文档
  - data/aiprompt/**/*.md       思维导图 Markdown 导出（支持嵌套文件夹）
"""
from __future__ import annotations
import concurrent.futures
import os
import time
import json
import hashlib
import threading
from contextvars import ContextVar
from openai import OpenAI
from pymilvus import MilvusClient
from utils.data_path import root_path
from utils.sensitive_data import get_api_key
from yuanai_core.rag_base import (
    SPEC_FILE_PATH, STEPS_FILE_PATH, chunk_text, get_all_specs,
    split_spec_sections, search_spec_sections, get_all_raw_text,
    make_retrieve_specification,
)

# ====================== 配置 ======================
AIPROMPT_DIR = os.path.join(root_path(), "data", "aiprompt")
# SPEC_FILE_PATH/STEPS_FILE_PATH 由 yuanai_core.rag_base 统一提供
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
# MILVUS_HOST 以 .db 结尾时走 milvus-lite 嵌入式本地文件模式（单机测试/免部署）
COLLECTION_NAME = "knowledge_base"
TOP_K = 10
# Milvus query/删除 单次上限：知识星球累计 chunk 可超 1.6 万，旧值会导致 ID 冲突与删不净
MILVUS_QUERY_LIMIT = 65536

# TODO: 本地 fallback 模型 dim=384，API 模型 dim=1024，需运行时动态适配
# 当前用 1024，API 成功后没有问题；本地模型 fallback 时需先删旧 collection 重建
EMBEDDING_DIM = 1024

_client: OpenAI | None = None
_db: MilvusClient | None = None
_db_lock = threading.RLock()  # 保护集合创建/写入并发（可重入）
current_user_id: ContextVar[int] = ContextVar("kb_user_id", default=0)  # 当前检索用户上下文
current_request_id: ContextVar[str] = ContextVar("kb_request_id", default="")  # 当前对话请求 ID（工具内发心跳/事件用）
current_session_id: ContextVar[str] = ContextVar("kb_session_id", default="")  # 当前对话会话 ID（记忆自整理删除边界判定用）


# ====================== Embedding ======================
def _get_openai_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    # Embedding 模型始终用火山引擎 Ark（与对话模型无关）
    api_key = get_api_key("seed")
    base_url = "https://ark.cn-beijing.volces.com/api/v3"

    _client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
    return _client


_local_model = None

def _get_local_embedding_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _local_model


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _get_openai_client()
    model = os.getenv("EMBEDDING_MODEL", "")
    if not model:
        print("⚠️ 未配置 EMBEDDING_MODEL 环境变量，使用本地模型")
        m = _get_local_embedding_model()
        return m.encode(texts, normalize_embeddings=True).tolist()

    try:
        all_embeddings = []
        batch_size = 256
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = client.embeddings.create(model=model, input=batch, timeout=30.0)
            all_embeddings.extend([d.embedding for d in resp.data])
        return all_embeddings
    except Exception as e:
        print(f"⚠️ API embedding 失败: {e}，fallback 到本地模型")
        try:
            m = _get_local_embedding_model()
            return m.encode(texts, normalize_embeddings=True).tolist()
        except Exception as e2:
            print(f"⚠️ 本地模型也失败: {e2}")
            dim = EMBEDDING_DIM
            return [[0.0] * dim for _ in texts]


# ====================== Milvus ======================
MILVUS_OP_TIMEOUT = 15  # 单次 Milvus 操作超时（秒）
MILVUS_FAIL_COOLDOWN_S = 60  # 连接失败后的快速失败冷却期（秒）


def _get_db() -> MilvusClient | None:
    """Milvus 客户端（进程级缓存）。连接失败进入冷却期快速返回 None——
    曾每轮工具调用都重试连接、挂死对话（部署 Agent 无 Milvus，卡 120s）。"""
    global _db, _db_fail_until
    if _db is not None:
        return _db
    if time.time() < _db_fail_until:
        return None
    if MILVUS_HOST.endswith(".db"):
        uri = MILVUS_HOST  # milvus-lite 嵌入式本地文件
    else:
        uri = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
    try:
        _db = MilvusClient(uri=uri, timeout=5)
        return _db
    except Exception:
        _db_fail_until = time.time() + MILVUS_FAIL_COOLDOWN_S
        return None


_db_fail_until = 0.0

# 模块级守护线程池：_safe_milvus 曾每次新建 with ThreadPoolExecutor——超时后
# with 退出仍等挂死线程收尾，15s 保护形同虚设。守护池不阻塞调用方与进程退出。
_safe_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="milvus-safe")


def _safe_milvus(op_name: str, fn, *args, **kwargs):
    """带超时保护执行 Milvus 操作，失败返回 None 而非挂死"""
    try:
        future = _safe_pool.submit(fn, *args, **kwargs)
        return future.result(timeout=MILVUS_OP_TIMEOUT)
    except concurrent.futures.TimeoutError:
        print(f"⚠️ Milvus {op_name} 超时（>{MILVUS_OP_TIMEOUT}s）")
        return None
    except Exception as e:
        print(f"⚠️ Milvus {op_name} 异常: {e}")
        return None


# ====================== Markdown 思维导图解析 ======================
def _parse_mindmap_md(filepath: str) -> list[dict]:
    """解析 Markdown 文件：heading (#) + 列表项 (-) 共同构成树形结构（纯函数版薄壳）"""
    from yuanai_core.pure.mindmap_parser import parse_mindmap_markdown

    with open(filepath, "r", encoding="utf-8") as f:
        return parse_mindmap_markdown(f.read())


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


# ====================== 知识库构建 ======================
def build_knowledge_base(force_rebuild: bool = False) -> bool:
    db = _get_db()
    if db is None:
        print("⚠️ Milvus 不可用，无法构建知识库")
        return False

    if db.has_collection(COLLECTION_NAME) and not force_rebuild:
        print("✅ 知识库已存在")
        return True

    print("🔍 扫描知识文档...")

    all_chunks: list[dict] = []

    # 1. 纯文本文档（分块逻辑来自 yuanai_core.rag_base）
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            all_chunks.extend(chunk_text(f.read(), "annotation_spec", path_prefix="annotation_spec", level=2))
        print(f"  📝 annotation_spec.txt")

    if os.path.exists(STEPS_FILE_PATH):
        with open(STEPS_FILE_PATH, "r", encoding="utf-8") as f:
            all_chunks.extend(chunk_text(f.read(), "audit_steps", path_prefix="audit_steps", level=2))
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
            limit=MILVUS_QUERY_LIMIT,
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
    filter_parts = [f'source == "{source.replace(chr(34), chr(92)+chr(34))}"']
    if user_id is not None:
        filter_parts.append(f'user_id == {user_id}')
    try:
        results = db.query(
            COLLECTION_NAME,
            filter=" and ".join(filter_parts),
            output_fields=["id"],
            limit=MILVUS_QUERY_LIMIT,
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
            limit=MILVUS_QUERY_LIMIT,
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
def _resolve_user_id(user_id: int | None) -> int:
    """隔离语义：显式 uid → 用；None → 取当前请求上下文；仍无 → 0（仅共享）"""
    if user_id is not None:
        return user_id
    try:
        ctx = current_user_id.get()
    except Exception:
        ctx = 0
    return ctx if ctx else 0


def _asset_url(source: str, name: str) -> str:
    """图片 URL：planet:uid:pid:mid 来源走鉴权资产路由，其余走 legacy 公开路由"""
    parts = source.split(":")
    if len(parts) >= 4 and parts[0] == "planet":
        return f"/api/v1/planet/asset/{parts[2]}/{parts[3]}/{name}"
    return f"/api/v1/knowledge/img/{source}/{name}"


def search_knowledge_hits(query: str, top_k: int = TOP_K, sources: list[str] | None = None,
                          user_id: int | None = None, fallback: bool = True) -> list[dict]:
    """向量检索，返回结构化命中 [{source,title,path,text,images:[url],score,level}]。

    sources: 显式 source 列表（走 source in [...]，避免 like 行为差异）；缺省检索全部可见。
    user_id: None → 取 current_user_id 上下文，仍无则仅共享（user_id==0）——修复跨用户泄漏。
    fallback: False 时不回退 raw text（知识星球检索绝不能拿标注规范文档凑数）。
    """
    if not query.strip():
        return []

    db = _get_db()
    if db is None:
        return []

    has_coll = _safe_milvus("has_collection", db.has_collection, COLLECTION_NAME)
    if has_coll is None or not has_coll:
        return []

    embeddings = get_embeddings([query])
    if not embeddings or all(v == 0 for v in embeddings[0]):
        return []

    uid = _resolve_user_id(user_id)
    filters = []
    if sources:
        quoted = ", ".join(f'"{s.replace(chr(34), chr(92) + chr(34))}"' for s in sources)
        filters.append(f"source in [{quoted}]")
    if uid:
        filters.append(f"(user_id == 0 or user_id == {uid})")
    else:
        filters.append("(user_id == 0)")

    filter_expr = " and ".join(filters)
    output_fields = ["text", "title", "source", "path", "images", "user_id", "level"]

    results = _safe_milvus(
        "search",
        db.search,
        COLLECTION_NAME,
        data=[embeddings[0]],
        limit=top_k,
        output_fields=output_fields,
        filter=filter_expr,
    )
    # 旧集合缺字段时回退
    if results is None:
        results = _safe_milvus(
            "search(fallback)",
            db.search,
            COLLECTION_NAME,
            data=[embeddings[0]],
            limit=top_k,
            output_fields=["text", "title", "source"],
            filter=filter_expr,
        )

    if not results or not results[0]:
        return []

    hits = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        src = entity.get("source", "")
        imgs = []
        raw_imgs = entity.get("images", "[]")
        if raw_imgs and raw_imgs != "[]":
            try:
                imgs = [_asset_url(src, i) for i in json.loads(raw_imgs)]
            except (json.JSONDecodeError, Exception):
                pass
        hits.append({
            "source": src,
            "title": entity.get("title", ""),
            "path": entity.get("path", ""),
            "text": entity.get("text", ""),
            "images": imgs,
            "score": round(float(hit.get("distance", 0.0)), 4),
            "level": entity.get("level", 0),
        })
    if hits:
        return hits
    return [] if not fallback else []


def search_knowledge(query: str, top_k: int = TOP_K, source: str | None = None,
                     user_id: int | None = None) -> str:
    """向量检索知识库（字符串契约，供 Agent 工具使用；结构化检索请用 search_knowledge_hits）。

    user_id=None   → 取请求上下文用户；仍无 → 仅检索共享知识（user_id=0）
    user_id=123    → 检索共享 + 该用户的私有知识
    """
    if not query.strip():
        return ""

    db = _get_db()
    if db is None:
        return "知识库服务未启动（Milvus 不可用），请联系管理员"

    has_coll = _safe_milvus("has_collection", db.has_collection, COLLECTION_NAME)
    if has_coll is None:
        return "知识库服务响应超时，请稍后重试"
    if not has_coll:
        if not build_knowledge_base():
            return get_all_raw_text()

    hits = search_knowledge_hits(query, top_k=top_k, sources=[source] if source else None,
                                 user_id=user_id)
    if not hits:
        return get_all_raw_text()[:2000]

    chunks = []
    for h in hits:
        header = f"[{h['source']}] {h['path'] or h['title']}"
        chunks.append(header + "\n" + h["text"])
        for img_url in h["images"]:
            chunks.append(f"  ![图片]({img_url})")
    return "\n---\n".join(chunks)


def search_spec(query: str) -> str:
    return search_knowledge(query, source="annotation_spec")


def search_steps(query: str) -> str:
    return search_knowledge(query, source="audit_steps")


def list_knowledge_sources() -> list[str]:
    """列出所有已索引的知识库来源"""
    db = _get_db()
    if db is None:
        return []
    has_coll = _safe_milvus("has_collection", db.has_collection, COLLECTION_NAME)
    if not has_coll:
        return []
    sources = set()
    results = _safe_milvus(
        "query", db.query,
        COLLECTION_NAME,
        filter='id >= 0',
        output_fields=["source"],
        limit=10000,
    )
    if not results:
        return []
    for r in results:
        sources.add(r.get("source", ""))
    return sorted(sources)


# ====================== 兼容旧接口（规范接口来自 yuanai_core.rag_base） ======================
def search_annotation_spec(query: str) -> str:
    return search_spec(query)


def rebuild_vector_store():
    build_knowledge_base(force_rebuild=True)


# ====================== LangChain Tool ======================
_ALL = [
    "search_knowledge", "search_knowledge_hits", "search_spec", "search_steps",
    "search_annotation_spec", "get_all_specs", "search_spec_sections",
    "split_spec_sections", "get_embeddings",
    "build_knowledge_base", "rebuild_vector_store", "list_knowledge_sources",
    "add_source_chunks", "remove_source", "get_source_stats",
]
retrieve_specification = make_retrieve_specification(get_all_specs, search_spec)
if retrieve_specification is not None:
    _ALL.insert(0, "retrieve_specification")
__all__ = _ALL
