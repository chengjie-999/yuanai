"""RAG 隔离与结构化检索测试 — 需要 Milvus 运行中（不可用则 skip）

核心回归：user_id=None 时绝不返回他人私有 chunk；sources 过滤只命中指定 source；
fallback=False 无结果时返回空数组（不回落 raw text）。
"""
import pytest


def _rag_or_skip():
    try:
        import yuanai_core.rag as rag

        db = rag._get_db()
        if db is None:
            pytest.skip("Milvus 不可用")
        has = rag._safe_milvus("has_collection", db.has_collection, rag.COLLECTION_NAME)
        if not has:
            pytest.skip("knowledge_base 集合不存在（先跑一次 build_knowledge_base）")
        return rag
    except ImportError as e:
        pytest.skip(f"依赖缺失: {e}")


@pytest.fixture(scope="module")
def rag():
    return _rag_or_skip()


UID_A, UID_B = 999001, 999002
SRC_A = f"planet:{UID_A}:1:1"
SRC_B = f"planet:{UID_B}:1:1"
MARKER_A = "隔离测试标记AAA私有内容"
MARKER_B = "隔离测试标记BBB私有内容"


@pytest.fixture(scope="module", autouse=True)
def _seed(rag):
    """写入 A/B 两用户的私有 chunk，测试结束后清理"""
    chunks_a = [{
        "text": f"{MARKER_A}：这是用户A的私人笔记，讲的是深度学习优化器 Adam 的调参经验",
        "title": "Adam调参", "path": "笔记 > 调参", "level": 2,
        "source": SRC_A, "user_id": UID_A, "images": "[]",
    }]
    chunks_b = [{
        "text": f"{MARKER_B}：这是用户B的私人笔记，讲的是Adam优化器与SGD的对比",
        "title": "优化器对比", "path": "笔记 > 对比", "level": 2,
        "source": SRC_B, "user_id": UID_B, "images": "[]",
    }]
    rag.remove_source(SRC_A, user_id=UID_A)
    rag.remove_source(SRC_B, user_id=UID_B)
    rag.add_source_chunks(chunks_a)
    rag.add_source_chunks(chunks_b)
    yield
    rag.remove_source(SRC_A, user_id=UID_A)
    rag.remove_source(SRC_B, user_id=UID_B)


def test_hits_no_user_no_leak(rag):
    """user_id=None（共享上下文）→ 只返回 user_id==0 的内容，绝不返回 A/B 私有"""
    hits = rag.search_knowledge_hits("Adam 优化器 调参", top_k=10, user_id=None, fallback=False)
    for h in hits:
        assert MARKER_A not in h["text"], "泄漏了用户A的私有内容"
        assert MARKER_B not in h["text"], "泄漏了用户B的私有内容"
    assert isinstance(hits, list)


def test_hits_user_a_gets_own_only(rag):
    hits = rag.search_knowledge_hits("Adam 优化器 调参", top_k=10, user_id=UID_A, fallback=False)
    texts = " ".join(h["text"] for h in hits)
    assert MARKER_A in texts, "用户A检索不到自己的私有内容"
    assert MARKER_B not in texts, "用户A检索到了用户B的私有内容"
    for h in hits:
        assert h["source"] == SRC_A


def test_hits_sources_filter(rag):
    hits = rag.search_knowledge_hits("Adam 优化器", top_k=5, sources=[SRC_B],
                                     user_id=UID_B, fallback=False)
    assert hits and all(h["source"] == SRC_B for h in hits)
    # 指定不存在的 source → 空
    hits2 = rag.search_knowledge_hits("Adam 优化器", top_k=5, sources=[f"planet:0:0:0"],
                                      user_id=UID_B, fallback=False)
    assert hits2 == []


def test_hits_fallback_false_empty(rag):
    """fallback=False 无命中 → 空数组而非 raw text"""
    hits = rag.search_knowledge_hits("完全不存在的查询词xyzabc", top_k=3,
                                     sources=[SRC_A], user_id=UID_A, fallback=False)
    assert hits == []


def test_hits_structure(rag):
    hits = rag.search_knowledge_hits("Adam 优化器", top_k=5, sources=[SRC_A], user_id=UID_A)
    for h in hits:
        for key in ("source", "title", "path", "text", "images", "score", "level"):
            assert key in h


def test_all_clean(rag):
    """__all__ 不再包含幽灵项，且包含新函数"""
    assert "retrieve_knowledge" not in rag.__all__
    assert "search_knowledge_hits" in rag.__all__
