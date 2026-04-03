import os

# 👇 修复了新版 LangChain 导入
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.tools import tool

# ====================== 配置 ======================
SPEC_FILE_PATH = "annotation_spec.txt"
VECTOR_STORE_PATH = "./faiss_spec_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
TOP_K = 2

# ====================== 初始化 ======================
embedding = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def build_spec_vector_store(force_rebuild=False):
    if os.path.exists(VECTOR_STORE_PATH) and not force_rebuild:
        print("✅ 向量库已存在")
        return FAISS.load_local(VECTOR_STORE_PATH, embedding, allow_dangerous_deserialization=True)

    print("🔨 首次构建规范向量库...")
    with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_text(text)

    db = FAISS.from_texts(chunks, embedding)
    db.save_local(VECTOR_STORE_PATH)
    print("✅ 构建完成")
    return db


# 全局加载一次
vector_db = build_spec_vector_store()


# ====================== 检索 ======================
def search_annotation_spec(query: str) -> str:
    docs = vector_db.similarity_search(query, k=TOP_K)
    return "\n---\n".join([doc.page_content for doc in docs])


# ====================== Agent 工具 ======================
@tool
def retrieve_specification(query: str) -> str:
    """
    检索数据标注规范，需要判断内容是否合规时调用。
    输入：待审核的内容
    输出：相关规范
    """
    return search_annotation_spec(query)


__all__ = ["retrieve_specification", "search_annotation_spec"]
