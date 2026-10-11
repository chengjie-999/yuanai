# -*- coding: utf-8 -*-
"""统一工作台文件服务测试 — P1 隐藏内部存储/正斜杠 + P2 scope 化（后续阶段扩展）

端点部分需要 MySQL（不可用则跳过）。运行：pytest test/test_workbench_files.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from api.v1.admin.resources import _is_hidden_entry  # noqa: E402


def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


# ---------------- P1 纯函数：列表隐藏 ----------------

def test_is_hidden_entry_data_root():
    """data 根级隐藏 '.' 开头（.yuan 记忆内部存储 / .pt_token.txt 令牌）；子层不隐藏"""
    assert _is_hidden_entry("", ".yuan") is True
    assert _is_hidden_entry("", ".pt_token.txt") is True
    assert _is_hidden_entry("", "datasets") is False
    # 子层不隐藏（用户目录里正常的隐藏文件归用户自己管）
    assert _is_hidden_entry("cases", ".hidden") is False


# ---------------- P1 端点级：隐藏 + 正斜杠 + .yuan 封禁 ----------------

def _admin_headers(db, name="__files_admin__"):
    from api.v1.auth.utils import create_token
    from db.session import User
    db.register_user(name, "test123", role="admin")
    sess = db.Session()
    try:
        uid = sess.query(User).filter_by(username=name).first().id
    finally:
        sess.close()
    return {"Authorization": f"Bearer {create_token(uid, 'admin')}"}, uid


def test_admin_files_hides_dotfiles_and_forward_slash(client, db):
    h, uid = _admin_headers(db)
    try:
        # data 根列表：无 '.' 开头条目，且所有 path 无反斜杠
        r = client.get("/api/v1/admin/files", headers=h)
        assert r.status_code == 200
        items = r.json()["items"]
        names = [i["name"] for i in items]
        assert all(not n.startswith(".") for n in names)
        assert ".yuan" not in names
        assert all("\\" not in i["path"] for i in items)

        # 嵌套目录正斜杠：cases 子项 path 应为 cases/xxx
        r = client.get("/api/v1/admin/files?path=cases", headers=h)
        if r.status_code == 200 and r.json()["items"]:
            for i in r.json()["items"]:
                assert i["path"].startswith("cases/") and "\\" not in i["path"]

        # .yuan 手构造 URL 封禁 404（列表隐藏挡不住直连）
        assert client.get("/api/v1/admin/file/read?path=.yuan%2F1%2Fxxx.md",
                          headers=h).status_code == 404
        # 越权仍 400
        assert client.get("/api/v1/admin/file/read?path=..%2F..%2Fetc",
                          headers=h).status_code == 400
    finally:
        from db.session import User
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()
