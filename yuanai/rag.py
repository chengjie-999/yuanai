import os
import re

# 👇 修复了新版 LangChain 导入
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.tools import tool

# 👇 导入路径工具
from utils.data_path import root_path

# ====================== 配置 ======================
SPEC_FILE_PATH = os.path.join(root_path(), "data", "aiprompt", "annotation_spec.txt")
VECTOR_STORE_PATH = os.path.join(root_path(), "data", "faiss_spec_db")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
TOP_K = 2

# ====================== 是否启用 RAG ======================
# 由于网络问题，默认不启用 RAG 向量库
# 如需启用 RAG，请手动设置 USE_RAG = True（需要能访问 HuggingFace）
USE_RAG = False

# ====================== 初始化 ======================
# embedding 模型（网络不可用时会失败，延迟初始化）
_embedding = None
vector_db = None


def get_embedding():
    """获取 embedding 模型（延迟加载，网络问题也能工作）"""
    global _embedding
    if _embedding is None:
        if USE_RAG:
            try:
                _embedding = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
            except Exception as e:
                print(f"⚠️ 无法加载 embedding 模型: {e}")
                print("RAG 向量库功能已禁用，使用纯文本匹配模式")
                return None
        else:
            return None
    return _embedding


def build_spec_vector_store(force_rebuild=False):
    """构建规范向量库"""
    global vector_db
    
    # 检查是否启用 RAG
    if not USE_RAG:
        print("⚠️ RAG 向量库已禁用，跳过构建")
        print("   如需启用，请设置 yuanai.rag.USE_RAG = True")
        return None
    
    # 确保文件存在
    if not os.path.exists(SPEC_FILE_PATH):
        print(f"⚠️ 规范文件不存在: {SPEC_FILE_PATH}")
        print("请手动创建 annotation_spec.txt 文件并填入规范内容")
        return None

    embedding = get_embedding()
    if embedding is None:
        return None

    if os.path.exists(VECTOR_STORE_PATH) and not force_rebuild:
        print("✅ 向量库已存在")
        return FAISS.load_local(VECTOR_STORE_PATH, embedding, allow_dangerous_deserialization=True)

    print("🔨 首次构建规范向量库...")
    with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.strip():
        print("⚠️ 规范文件为空，请填入规范内容后重建向量库")
        return None

    # 确保目录存在
    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_text(text)

    db = FAISS.from_texts(chunks, embedding)
    db.save_local(VECTOR_STORE_PATH)
    print("✅ 构建完成")
    return db


# 全局加载（延迟初始化）
def get_vector_db():
    global vector_db
    if vector_db is None and USE_RAG:
        vector_db = build_spec_vector_store()
    return vector_db


# ====================== 检索 ======================
def search_annotation_spec(query: str) -> str:
    """检索规范（关键词匹配，无向量库时返回全部）"""
    if not USE_RAG:
        # RAG 禁用时，返回全部规范内容
        return get_all_specs()
    
    db = get_vector_db()
    if db is None:
        return "规范文件未找到，请检查 annotation_spec.txt"
    docs = db.similarity_search(query, k=TOP_K)
    return "\n---\n".join([doc.page_content for doc in docs])


def get_all_specs() -> str:
    """获取所有标注规范（无检索，直接返回全部内容）"""
    if os.path.exists(SPEC_FILE_PATH):
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def split_spec_sections() -> list:
    """将标注规范按一级标题切分为段落列表，返回 [(标题, 内容), ...]"""
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
    """
    按关键词检索相关规范段落。
    只返回匹配的标题段落，不返回全文。
    """
    sections = split_spec_sections()
    if not sections:
        return ""
    if not keyword:
        return "\n\n".join(c for _, c in sections)

    keyword_lower = keyword.lower()
    matched = []
    for title, content in sections:
        if keyword_lower in content.lower():
            matched.append(content)
    if matched:
        return "\n\n".join(matched)
    return sections[0][1] if sections else ""


def rebuild_vector_store():
    """强制重建向量库（用于规范文档更新后）"""
    global vector_db
    vector_db = build_spec_vector_store(force_rebuild=True)
    return vector_db


def update_spec_from_feishu(doc_url: str, cookies: dict = None):
    """
    从飞书云文档更新标注规范（预留函数，暂时不可用）
    提示：飞书云文档包含视频和图片，手动编辑 annotation_spec.txt 更合适
    """
    from spiderlx.core.requests.core import get_response_data

    try:
        content = get_response_data(doc_url, retype='text', cookies=cookies)
        os.makedirs(os.path.dirname(SPEC_FILE_PATH), exist_ok=True)
        with open(SPEC_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        rebuild_vector_store()
        return True
    except Exception as e:
        print(f"飞书同步失败: {e}")
        return False


# ====================== Agent 工具 ======================
@tool
def retrieve_specification(query: str = "") -> str:
    """
    检索数据标注规范，需要判断内容是否合规时调用。
    输入：待审核的内容
    输出：相关规范（如果 RAG 禁用，则返回全部规范）
    """
    if not USE_RAG:
        return get_all_specs()
    return search_annotation_spec(query)


__all__ = [
    "retrieve_specification", "search_annotation_spec",
    "get_all_specs", "rebuild_vector_store", "update_spec_from_feishu",
    "search_spec_sections", "split_spec_sections"
]
