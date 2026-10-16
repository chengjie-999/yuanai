# -*- coding: utf-8 -*-
"""S1.2 iframe XSS 链修复测试 — 沙箱响应头 / html_id 白名单 / .owner 归属 / sse token

运行：pytest test/test_iframe_security.py -v
端点测试需要 MySQL 运行中（不可用则跳过），纯函数与 registry 测试离线可跑。
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from utils.data_path import root_path  # noqa: E402


# ---------------- 纯函数（离线） ----------------

def test_safe_html_id_whitelist():
    from api.v1.data.router import _safe_html_id
    assert _safe_html_id("0123456789ab") is True
    for bad in ["0123456789", "0123456789abc", "0123456789AB", "0123456789a-",
                "..%2F..%2Fx", "../etc/passwd", "0123456789ab/", "", None]:
        assert _safe_html_id(bad or "") is False, f"应拒绝: {bad!r}"


def test_safe_single_name_rejects_traversal():
    from api.v1.data.router import _safe_single_name
    assert _safe_single_name("result") is True
    assert _safe_single_name("图表_01") is True
    for bad in ["../x", "a/b", "a\\b", "..", "..%2F..", "", None]:
        assert _safe_single_name(bad or "") is False, f"应拒绝: {bad!r}"


def test_sandbox_html_response_headers():
    from api.v1.data.router import _sandbox_html_response, SANDBOX_HEADERS
    resp = _sandbox_html_response("<script>alert(1)</script>")
    assert resp.body == b"<script>alert(1)</script>"
    csp = resp.headers.get("content-security-policy", "")
    assert "sandbox allow-scripts" in csp
    assert "frame-ancestors 'self'" in csp
    assert "nosniff" in resp.headers.get("x-content-type-options", "")
    assert SANDBOX_HEADERS["Content-Security-Policy"] == csp


# ---------------- registry .owner 写入（离线，真实子进程） ----------------

def _make_html_script(tmp_path):
    """最小脚本：生成一个 html 文件并打印 __HTML__:path（as_posix 防反斜杠转义）"""
    html = tmp_path / "chart.html"
    html.write_text("<html>chart</html>", encoding="utf-8")
    script = tmp_path / "test_html_script.py"
    script.write_text(
        f'__script_name__ = "test_html_owner"\n'
        f'__script_desc__ = "owner 测试脚本"\n'
        f'__script_params__ = [{{"name": "v", "type": "int"}}]\n'
        f'print("__HTML__:{html.as_posix()}")\n',
        encoding="utf-8",
    )
    return str(script)


def test_registry_writes_owner_file(tmp_path, monkeypatch):
    """__HTML__ 缓存落盘时写 .owner（内容=current_user_id）

    两次 run 用不同参数：同脚本同参数第二次会命中 A 看板缓存短路
    （设计内——看板是全局缓存，直接展示不重跑）。
    """
    import agent.scripts.registry as reg
    monkeypatch.setattr(reg, "PROJECT_ROOT", str(tmp_path))

    script_path = _make_html_script(tmp_path)
    handle = reg._ScriptHandle("test_html_owner", "owner 测试脚本", script_path)
    reg._parse_params_decl('[{"name": "v", "type": "int"}]', handle)
    out = handle.run(v="1")

    assert "__HTML__URL:/api/v1/data/script-html/" in out
    cache_dir = os.path.join(str(tmp_path), "data", "analysis", "html_cache")
    owners = [f for f in os.listdir(cache_dir) if f.endswith(".owner")]
    assert len(owners) == 1
    # 未设置 user 上下文 → 0
    assert open(os.path.join(cache_dir, owners[0]), encoding="utf-8").read().strip() == "0"

    # 设置 user 上下文 → 写入对应 uid
    from yuanai_core.rag import current_user_id
    token_ctx = current_user_id.set(42)
    try:
        out2 = handle.run(v="2")
        assert "__HTML__URL:/api/v1/data/script-html/" in out2
        owner_files = [f for f in os.listdir(cache_dir) if f.endswith(".owner")]
        contents = {open(os.path.join(cache_dir, f), encoding="utf-8").read().strip()
                    for f in owner_files}
        assert "42" in contents
    finally:
        current_user_id.reset(token_ctx)


# ---------------- 端点测试（需要 MySQL；不可用则跳过） ----------------

def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


@pytest.fixture(scope="module")
def test_admin(db):
    """自建 admin 测试用户（不依赖环境里存在 admin/admin123），模块结束清理"""
    from db.session import User

    # 清理残留
    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__sse_admin_test__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()

    r = db.register_user("__sse_admin_test__", "test123", role="admin")
    assert "error" not in r, r
    yield r
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


@pytest.fixture(scope="module")
def test_user(db):
    """普通用户（属主矩阵用：admin 会绕过 owner 校验）"""
    from db.session import User

    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__sse_user_test__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()

    r = db.register_user("__sse_user_test__", "test123")
    assert "error" not in r, r
    yield r
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


@pytest.fixture(scope="module")
def mint_sse(client, test_admin):
    """用测试 admin 的 JWT 签 sse token（单次使用，每次调用新签）"""
    from api.v1.auth.utils import create_token

    jwt = create_token(test_admin["id"], "admin")

    def _mint():
        resp = client.get("/api/v1/auth/sse-token",
                          headers={"Authorization": f"Bearer {jwt}"})
        assert resp.status_code == 200, resp.text
        return resp.json()["token"]
    return _mint


def test_sse_token_endpoint_auth(client):
    # 未登录 401
    assert client.get("/api/v1/auth/sse-token").status_code == 401
    # 坏 token 401
    assert client.get("/api/v1/auth/sse-token",
                      headers={"Authorization": "Bearer bad"}).status_code == 401


def test_script_html_bad_id_rejected(client, mint_sse):
    # 非法 html_id：白名单拒绝（httpx 会预解析 ../，穿越样式走下面直接函数调用）
    for bad in ("ABC", "short", "0123456789abc"):
        resp = client.get(f"/api/v1/data/script-html/{bad}", params={"token": mint_sse()})
        assert resp.status_code == 404, bad


def test_script_html_traversal_id_rejected():
    """穿越样式 html_id 在端点入口即 404（直接调用函数，绕过客户端 URL 归一化）"""
    import asyncio
    from types import SimpleNamespace
    from fastapi import HTTPException
    from api.v1.data.router import serve_script_html

    for bad in ("../etc/passwd", "..%2F..%2Fx", "../../x"):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(serve_script_html(
                bad, SimpleNamespace(state=SimpleNamespace(user_id=0, role=""))))
        assert ei.value.status_code == 404, bad


def test_script_html_owner_matrix(client, test_user):
    """有文件无 .owner → 404；.owner 属主不一致 → 404；一致 → 200 + 沙箱头"""
    from api.v1.auth.utils import create_token

    cache_dir = os.path.join(root_path(), "data", "analysis", "html_cache")
    os.makedirs(cache_dir, exist_ok=True)
    html_id = "a1b2c3d4e5f6"
    html_path = os.path.join(cache_dir, f"{html_id}.html")
    owner_path = os.path.join(cache_dir, f"{html_id}.owner")

    # 普通用户 JWT → 换 sse token（admin 会绕过 owner 校验，矩阵必须用普通用户）
    jwt = create_token(test_user["id"], "user")

    def mint_user_sse():
        resp = client.get("/api/v1/auth/sse-token",
                          headers={"Authorization": f"Bearer {jwt}"})
        assert resp.status_code == 200, resp.text
        return resp.json()["token"]

    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<html><body>chart</body></html>")

        # 1. 无 .owner → 404（旧缓存/未同步不暴露）
        resp = client.get(f"/api/v1/data/script-html/{html_id}", params={"token": mint_user_sse()})
        assert resp.status_code == 404

        # 2. 属主不一致 → 404
        with open(owner_path, "w", encoding="utf-8") as f:
            f.write(str(test_user["id"] + 999999))
        resp = client.get(f"/api/v1/data/script-html/{html_id}", params={"token": mint_user_sse()})
        assert resp.status_code == 404

        # 3. 属主一致 → 200 + 沙箱头 + nosniff
        with open(owner_path, "w", encoding="utf-8") as f:
            f.write(str(test_user["id"]))
        resp = client.get(f"/api/v1/data/script-html/{html_id}", params={"token": mint_user_sse()})
        assert resp.status_code == 200
        assert "sandbox allow-scripts" in resp.headers.get("content-security-policy", "")
        assert "nosniff" in resp.headers.get("x-content-type-options", "")
    finally:
        for p in (html_path, owner_path):
            if os.path.exists(p):
                os.remove(p)


def test_analysis_html_name_traversal_rejected():
    """name 含路径成分（%2F 解码后）→ 端点入口即 404（直接调用，绕过 URL 归一化）"""
    import asyncio
    from types import SimpleNamespace
    from fastapi import HTTPException
    from api.v1.data.router import serve_analysis_html, serve_analysis_image

    fake = SimpleNamespace(state=SimpleNamespace(user_id=0, role=""))
    for fn in (serve_analysis_html, serve_analysis_image):
        for bad in ("../x", "a/b", "a\\b", ".."):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(fn(1, bad, fake))
            assert ei.value.status_code == 404, f"{fn.__name__}: {bad}"


def test_planet_origin_sandbox_headers(db):
    """导图原文件（用户上传 html）响应必须带沙箱头 + nosniff（S1.2 存储型 XSS 拦截）"""
    from types import SimpleNamespace
    from api.v1.planet import store
    from api.v1.planet.router import get_map_origin

    uid = 990003
    p = db.create_planet(uid, "__test_origin_hdr__")
    try:
        html = os.path.join(root_path(), "data", "aiprompt", "01_Python.html")
        if not os.path.exists(html):
            pytest.skip("缺少真实样例文件")
        job = db.create_job(uid, "import", planet_id=p["id"])
        store.run_import(job, uid, p["id"],
                         [("01_Python.html", "01_Python.html", open(html, "rb").read())])
        m = db.list_maps(p["id"], uid)[0]
        assert m["source_format"] == "html"

        resp = get_map_origin(
            SimpleNamespace(state=SimpleNamespace(user_id=uid, role="")), m["id"])
        assert resp.media_type == "text/html"
        assert "sandbox allow-scripts" in resp.headers.get("content-security-policy", "")
        assert "nosniff" in resp.headers.get("x-content-type-options", "")
    finally:
        store.delete_planet_cascade(uid, p["id"])


def test_frozen_user_blocked_on_sse_branch(client, db):
    """S1.2 修复回归：sse token 分支冻结检查不再静默失效（403 而非漏过）"""
    from db.session import User
    from api.v1.auth.utils import create_sse_token

    r = db.register_user("__sse_frozen_test__", "test123")
    assert "error" not in r, r
    uid = r["id"]

    # 冻结该用户
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=uid).first()
        u.frozen_until = datetime.utcnow() + timedelta(hours=1)
        sess.commit()
    finally:
        sess.close()

    try:
        # 直接签 sse token（冻结用户连 sse-token 端点也会被中间件 403，故绕过签发环节）
        sse = create_sse_token(uid, "user")
        resp = client.get("/api/v1/data/script-html/a1b2c3d4e5f6", params={"token": sse})
        assert resp.status_code == 403, f"冻结检查失效: {resp.status_code}"
    finally:
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()


if __name__ == "__main__":
    test_safe_html_id_whitelist()
    test_safe_single_name_rejects_traversal()
    test_sandbox_html_response_headers()
    print("纯函数测试通过")
