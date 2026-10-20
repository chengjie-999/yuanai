"""
向量知识库 — Milvus + OpenAI 兼容 Embedding API（审核知识库）
开发模式: Milvus Lite (嵌入式，免 Docker)

与 yuanai_core/rag.py 通用知识库共用 yuanai_core.rag_base 基建
（文本分块/规范文档兼容接口/原始文本兜底/retrieve_specification 工厂）；
本模块只保留审核库特有逻辑：固定 Lite 文件、按默认模型服务商选 Embedding 通道、audit_knowledge 集合。
"""
import os
import time
from typing import Optional, List
from openai import OpenAI
from pymilvus import MilvusClient
from config.settings import DEFAULT_MODEL, MODELS
from utils.data_path import root_path
from utils.sensitive_data import get_api_key
from yuanai_core.rag_base import (
    SPEC_FILE_PATH, STEPS_FILE_PATH, chunk_text, get_all_specs,
    split_spec_sections, search_spec_sections, get_all_raw_text,
    make_retrieve_specification,
)

# ====================== 配置 ======================
MILVUS_DB_PATH = os.path.join(root_path(), "data", "milvus_knowledge.db")
COLLECTION_NAME = "audit_knowledge"
TOP_K = 3

# Embedding 配置：优先用默认模型对应的 API，运行时自动检测实际维度
EMBEDDING_DIM = 1024  # 默认值，首次调用后自动更新
_actual_dim: Optional[int] = None  # 运行时检测的实际维度

_client: Optional[OpenAI] = None
_db: Optional[MilvusClient] = None


# ====================== Embedding ======================
def _get_openai_client() -> OpenAI:
    """获取 OpenAI 兼容客户端（复用项目已有的 API 配置）"""
    global _client
    if _client is not None:
        return _client

    provider = MODELS.get(DEFAULT_MODEL, {}).get("provider", "Doubao")
    if provider == "DeepSeek":
        api_key = get_api_key("dsllm")
        base_url = "https://api.deepseek.com/beta"
    else:
        api_key = get_api_key("seed")
        base_url = "https://ark.cn-beijing.volces.com/api/v3"

    _client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
    return _client


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """批量获取文本向量"""
    if not texts:
        return []
    global _actual_dim
    client = _get_openai_client()
    try:
        resp = client.embeddings.create(
            model=DEFAULT_MODEL,
            input=texts,
        )
        embeddings = [d.embedding for d in resp.data]
        if embeddings and _actual_dim is None:
            _actual_dim = len(embeddings[0])
            print(f"✅ Embedding 实际维度: {_actual_dim}")
        return embeddings
    except Exception as e:
        print(f"⚠️ Embedding API 调用失败: {e}")
        dim = _actual_dim or EMBEDDING_DIM
        return [[0.0] * dim for _ in texts]


# ====================== Milvus ======================
def _get_db() -> MilvusClient:
    """获取 Milvus 客户端（Lite 模式）"""
    global _db
    if _db is not None:
        return _db
    os.makedirs(os.path.dirname(MILVUS_DB_PATH), exist_ok=True)
    _db = MilvusClient(MILVUS_DB_PATH)
    return _db


def build_knowledge_base(force_rebuild: bool = False) -> bool:
    """构建知识库：索引 annotation_spec.txt + audit_steps.txt"""
    db = _get_db()

    # 检查集合是否已存在
    if db.has_collection(COLLECTION_NAME) and not force_rebuild:
        print("✅ 知识库已存在")
        return True

    # 读取知识文档
    sources = {}
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            sources["annotation_spec"] = f.read()
    if os.path.exists(STEPS_FILE_PATH):
        with open(STEPS_FILE_PATH, "r", encoding="utf-8") as f:
            sources["audit_steps"] = f.read()

    if not sources:
        print("⚠️ 无知识文档可索引")
        return False

    # 切分（分块逻辑来自 yuanai_core.rag_base）
    all_chunks = []
    for source_name, text in sources.items():
        all_chunks.extend(chunk_text(text, source_name))

    if not all_chunks:
        print("⚠️ 文档切分后为空")
        return False

    # 获取向量
    texts = [c["text"] for c in all_chunks]
    print(f"🔨 正在为 {len(texts)} 个文本块生成向量...")
    start = time.time()
    embeddings = get_embeddings(texts)
    print(f"   向量生成完成，耗时 {time.time() - start:.1f}s")

    # 删除旧集合后重建
    if db.has_collection(COLLECTION_NAME):
        db.drop_collection(COLLECTION_NAME)

    # 准备插入数据
    data = []
    for i, chunk in enumerate(all_chunks):
        data.append({
            "id": i,
            "vector": embeddings[i],
            "text": chunk["text"],
            "title": chunk["title"],
            "source": chunk["source"],
        })

    db.create_collection(COLLECTION_NAME, dimension=_actual_dim or EMBEDDING_DIM)
    db.insert(COLLECTION_NAME, data)
    print(f"✅ 知识库构建完成，共 {len(data)} 条")
    return True


# ====================== 检索 ======================
def search_knowledge(query: str, top_k: int = TOP_K, source: Optional[str] = None) -> str:
    """向量检索知识库，返回相关段落"""
    if not query.strip():
        return ""

    db = _get_db()
    if not db.has_collection(COLLECTION_NAME):
        # 首次调用时自动构建
        if not build_knowledge_base():
            return get_all_raw_text()

    embeddings = get_embeddings([query])
    if not embeddings or all(v == 0 for v in embeddings[0]):
        # Embedding 不可用时返回原始文本的子集
        return get_all_raw_text()[:2000]

    filter_expr = f'source == "{source.replace(chr(34), chr(92)+chr(34))}"' if source else None
    results = db.search(
        COLLECTION_NAME,
        data=[embeddings[0]],
        limit=top_k,
        output_fields=["text", "title", "source"],
        filter=filter_expr,
    )

    if not results or not results[0]:
        return get_all_raw_text()[:2000]

    chunks = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        src = entity.get("source", "")
        title = entity.get("title", "")
        text = entity.get("text", "")
        chunks.append(f"[{src}] {title}\n{text}")

    return "\n---\n".join(chunks)


def search_spec(query: str) -> str:
    """检索标注规范（仅 annotation_spec 来源）"""
    return search_knowledge(query, source="annotation_spec")


def search_steps(query: str) -> str:
    """检索操作步骤（仅 audit_steps 来源）"""
    return search_knowledge(query, source="audit_steps")


# ====================== 兼容旧接口（规范接口来自 yuanai_core.rag_base） ======================
def search_annotation_spec(query: str) -> str:
    """按关键词检索规范（兼容旧接口，现在走向量检索）"""
    return search_spec(query)


def rebuild_vector_store():
    """强制重建知识库"""
    build_knowledge_base(force_rebuild=True)


# ====================== LangChain Tool ======================
_ALL = [
    "search_knowledge", "search_spec", "search_steps",
    "search_annotation_spec", "get_all_specs", "search_spec_sections",
    "split_spec_sections", "get_embeddings",
    "build_knowledge_base", "rebuild_vector_store",
]
retrieve_specification = make_retrieve_specification(get_all_specs, search_spec)
if retrieve_specification is not None:
    _ALL.insert(0, "retrieve_specification")
__all__ = _ALL
