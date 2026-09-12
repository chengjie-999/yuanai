"""知识星球 API 测试 — CRUD + 越权 404 矩阵 + 导入任务

需要 MySQL 运行中（不可用则整文件 skip）。运行：pytest test/test_planet_api.py -v
"""
import io
import os

import pytest

from utils.data_path import root_path

AIPROMPT_DIR = os.path.join(root_path(), "data", "aiprompt")


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
def uids():
    """两个互不相关的测试用户 id（不真实建用户，仅做数据隔离）"""
    return 990001, 990002


@pytest.fixture(scope="module")
def planet(db, uids):
    uid, _ = uids
    p = db.create_planet(uid, "__test_planet__")
    yield p
    db.delete_planet(p["id"], uid)


def test_planet_crud_ownership(db, uids):
    uid, other = uids
    p = db.create_planet(uid, "__test_planet2__")
    try:
        assert db.get_planet(p["id"], uid)["name"] == "__test_planet2__"
        # 越权读不到
        assert db.get_planet(p["id"], other) is None
        # 更新
        assert db.update_planet(p["id"], uid, name="改名后")
        assert db.get_planet(p["id"], uid)["name"] == "改名后"
    finally:
        db.delete_planet(p["id"], uid)


def test_note_crud(db, uids, planet):
    uid, other = uids
    nid = db.add_note(uid, planet["id"], None, "测试笔记", "# 正文\n内容", source="user")
    try:
        n = db.get_note(nid, uid)
        assert n["content"].startswith("# 正文")
        assert n["word_count"] > 0
        # 越权 404 语义（None）
        assert db.get_note(nid, other) is None
        # 编辑
        assert db.update_note(nid, uid, content="改后的内容")
        assert db.get_note(nid, uid)["content"] == "改后的内容"
        # 列表不含正文
        rows = db.list_notes(uid, planet_id=planet["id"])
        assert "content" not in rows[0]
    finally:
        db.delete_note(nid, uid)


def test_import_pipeline_best_fidelity(db, uids, planet):
    """同名 html+md 只导一张（html 保真度高），emmx 单独导入为 text-only"""
    from api.v1.planet import store

    uid, _ = uids
    html = os.path.join(AIPROMPT_DIR, "01_Python.html")
    md = os.path.join(AIPROMPT_DIR, "01_Python", "01_Python.md")
    if not (os.path.exists(html) and os.path.exists(md)):
        pytest.skip("缺少真实样例文件")

    job = db.create_job(uid, "import", planet_id=planet["id"])
    items = [
        ("01_Python.html", f"x/01_Python.html", open(html, "rb").read()),
        ("01_Python.md", f"x/01_Python.md", open(md, "rb").read()),
    ]
    store.run_import(job, uid, planet["id"], items)

    j = db.get_job(job, uid)
    assert j["status"] == "done"
    maps = [m for m in db.list_maps(planet["id"], uid) if m["title"] == "01_Python"]
    assert len(maps) == 1
    m = maps[0]
    assert m["source_format"] == "html"
    assert m["quality"] == "full"
    assert m["node_count"] >= 700
    assert any("忽略" in w for w in m["warnings"])

    # 文件落盘
    mdir = store.map_dir(uid, planet["id"], m["id"])
    assert os.path.isfile(os.path.join(mdir, "tree.json"))
    assert os.path.isfile(os.path.join(mdir, "outline.md"))
    assert os.path.isdir(os.path.join(mdir, "assets"))
    # 级联清理（连同笔记/任务行）
    store.delete_map_cascade(uid, m["id"])
    assert not os.path.isdir(mdir)


def test_import_emmx_text_only(db, uids, planet):
    from api.v1.planet import store

    uid, _ = uids
    emmx = os.path.join(AIPROMPT_DIR, "01_Python.emmx")
    if not os.path.exists(emmx):
        pytest.skip("缺少真实样例文件")

    job = db.create_job(uid, "import", planet_id=planet["id"])
    store.run_import(job, uid, planet["id"], [("01_Python.emmx", "01_Python.emmx", open(emmx, "rb").read())])

    j = db.get_job(job, uid)
    assert j["status"] == "done"
    m = [m for m in db.list_maps(planet["id"], uid) if m["quality"] == "text-only"][0]
    assert m["quality"] == "text-only"
    assert m["node_count"] >= 300
    assert any("层级" in w for w in m["warnings"])
    store.delete_map_cascade(uid, m["id"])


def test_job_watchdog_timeout(db, uids, planet):
    """running 超时的任务被看门狗判 failed"""
    from api.v1.planet import store

    uid, _ = uids
    job = db.create_job(uid, "convert", planet_id=planet["id"], map_id=None)
    db.update_job(job, uid, status="running")
    # 直接把 update_time 拨回 25 分钟前
    sess = db.Session()
    try:
        from db.session import PlanetJob
        r = sess.query(PlanetJob).filter_by(id=job).first()
        from datetime import datetime, timedelta
        r.update_time = datetime.utcnow() - timedelta(minutes=25)
        sess.commit()
    finally:
        sess.close()
    j = store.owned_job(job, uid)
    store.apply_job_watchdog(db, job, uid, j)
    assert j["status"] == "failed"
    assert "超时" in j["error"]
