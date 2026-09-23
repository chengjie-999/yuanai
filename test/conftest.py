"""
测试共享 fixtures — 使用 FastAPI TestClient + 内存数据库

安装依赖后运行：pip install -r requirements.txt && pytest test/ -v
"""
import os
import sys
import tempfile

import pytest

# 确保项目根在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 测试默认走 milvus-lite 嵌入式本地文件（无需 Milvus 服务）；
# 环境变量显式设置了 MILVUS_HOST（如服务器）则尊重之
os.environ.setdefault("MILVUS_HOST", os.path.join(tempfile.gettempdir(), "milvus_test.db"))
# 测试豁免限流（连跑登录会触发 5次/60s 429）
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")


@pytest.fixture(scope="session", autouse=True)
def _rag_fast_embeddings():
    """测试环境 mock embedding：确定性 ±1 伪向量，零网络零模型下载。
    隔离/过滤逻辑测试不需要真实向量；本地无法访问 huggingface 下载模型。
    注意：milvus-lite 的 .db 实际是目录，残留旧库会让复跑结果不稳定——
    会话开始先清库。"""
    try:
        import shutil

        db_path = os.environ.get("MILVUS_HOST", "")
        if db_path.endswith(".db"):
            shutil.rmtree(db_path, ignore_errors=True)

        import yuanai_core.rag as rag

        def fake_embeddings(texts):
            dim = rag.EMBEDDING_DIM
            out = []
            for t in texts:
                h = hash(t)
                out.append([1.0 if ((h >> (i % 61)) & 1) else -1.0 for i in range(dim)])
            return out

        rag.get_embeddings = fake_embeddings
    except Exception:
        pass


@pytest.fixture(scope="session")
def client():
    """
    FastAPI TestClient（需要完整环境：pip install -r requirements.txt）
    如果依赖未安装则跳过。
    """
    try:
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)
    except ImportError as e:
        pytest.skip(f"API 依赖未安装: {e}")


@pytest.fixture(scope="session")
def auth_headers(client):
    """登录并返回带 token 的 headers"""
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    if resp.status_code == 200:
        token = resp.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    return {}
