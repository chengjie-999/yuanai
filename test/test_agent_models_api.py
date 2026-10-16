# -*- coding: utf-8 -*-
"""Agent 模型分配测试 — 覆盖链 / 热更新 / 端点 / 删除引用保护

模型淘汰可更换（2026-10-16）：后台「模型配置」页可把各 Agent 切到新模型
（models.json _agent_models + 热更新），被引用的模型拒绝删除。
运行：pytest test/test_agent_models_api.py -v
settings 覆盖链离线可跑；端点测试需要 MySQL。
"""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from utils.data_path import root_path  # noqa: E402

_MODELS_PATH = os.path.join(root_path(), "data", "models.json")


@pytest.fixture
def models_file_backup():
    """备份/恢复 data/models.json（测试读写真实文件，与本地开发共享）"""
    backup = None
    if os.path.exists(_MODELS_PATH):
        with open(_MODELS_PATH, "r", encoding="utf-8") as f:
            backup = f.read()
    yield
    if backup is None:
        if os.path.exists(_MODELS_PATH):
            os.remove(_MODELS_PATH)
    else:
        with open(_MODELS_PATH, "w", encoding="utf-8") as f:
            f.write(backup)


@pytest.fixture
def settings_restore():
    """恢复 settings 全局状态（reload 与端点会原地改 MODELS/AGENT_MODEL_MAP/VOICE 等）"""
    import config.settings as s
    models = dict(s.MODELS)
    amap = dict(s.AGENT_MODEL_MAP)
    mm, pm = s.MEMORY_MODEL, s.PLANET_ARTICLE_MODEL
    vc = dict(s.VOICE_CONFIG)
    vt = (s.VOICE_TTS_MODEL, s.VOICE_TTS_VOICE, s.VOICE_TTS_VOICE_BOT,
          s.VOICE_ASR_RESOURCE_ID, s.VOICE_TTS_RESOURCE_ID)
    yield
    s.MODELS.clear(); s.MODELS.update(models)
    s.AGENT_MODEL_MAP.clear(); s.AGENT_MODEL_MAP.update(amap)
    s.MEMORY_MODEL, s.PLANET_ARTICLE_MODEL = mm, pm
    s.VOICE_CONFIG.clear(); s.VOICE_CONFIG.update(vc)
    (s.VOICE_TTS_MODEL, s.VOICE_TTS_VOICE, s.VOICE_TTS_VOICE_BOT,
     s.VOICE_ASR_RESOURCE_ID, s.VOICE_TTS_RESOURCE_ID) = vt


def _write_agent_models(data: dict):
    os.makedirs(os.path.dirname(_MODELS_PATH), exist_ok=True)
    with open(_MODELS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ---------------- settings 覆盖链（离线） ----------------

def test_load_agent_models_custom_override(models_file_backup, settings_restore):
    from config import settings as s
    _write_agent_models({"_agent_models": {
        "orchestrator": "deepseek-v4-pro",
        "memory_fold": "doubao-seed-2-0-pro-260215",
    }})
    m = s._load_agent_models()
    assert m["orchestrator"] == "deepseek-v4-pro"          # 自定义覆盖
    assert m["analysis"] == "deepseek-v4-pro"              # 未覆盖项保留默认
    assert m["memory_fold"] == "doubao-seed-2-0-pro-260215"
    assert m["planet_article"] == "doubao-seed-2-1-lite-260915"  # 未覆盖项保留默认（2026-10 已换 2.1）
    assert len(m) == 7


def test_reload_hot_updates_memory_and_planet(models_file_backup, settings_restore, monkeypatch):
    from config import settings as s
    monkeypatch.delenv("MEMORY_MODEL", raising=False)
    monkeypatch.delenv("PLANET_ARTICLE_MODEL", raising=False)
    _write_agent_models({"_agent_models": {
        "memory_fold": "deepseek-v4-flash",
        "planet_article": "deepseek-v4-pro",
    }})
    s.reload_agent_models()
    assert s.AGENT_MODEL_MAP["memory_fold"] == "deepseek-v4-flash"
    assert s.MEMORY_MODEL == "deepseek-v4-flash"           # 派生字符串同步热更新
    assert s.PLANET_ARTICLE_MODEL == "deepseek-v4-pro"


def test_env_overrides_agent_models(models_file_backup, settings_restore, monkeypatch):
    from config import settings as s
    _write_agent_models({"_agent_models": {"memory_fold": "deepseek-v4-flash"}})
    monkeypatch.setenv("MEMORY_MODEL", "env-custom-model")
    s.reload_agent_models()
    assert s.MEMORY_MODEL == "env-custom-model"            # env 优先级最高（既有语义）


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
def admin_jwt(db):
    """自建 admin 测试用户 → JWT（端点 require_admin 用）"""
    from db.session import User
    from api.v1.auth.utils import create_token

    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__agent_model_admin__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()

    r = db.register_user("__agent_model_admin__", "test123", role="admin")
    assert "error" not in r, r
    yield create_token(r["id"], "admin")
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


def test_agent_models_endpoint_roundtrip(client, db, admin_jwt, models_file_backup, settings_restore):
    h = {"Authorization": f"Bearer {admin_jwt}"}

    # 未登录 401
    assert client.get("/api/v1/admin/agent-models").status_code == 401

    # GET：7 个分配键
    resp = client.get("/api/v1/admin/agent-models", headers=h)
    assert resp.status_code == 200
    am = resp.json()["agent_models"]
    assert len(am) == 7 and "orchestrator" in am and "memory_fold" in am

    # PUT：未知分配键 400
    resp = client.put("/api/v1/admin/agent-models", headers=h,
                      json={"agent_models": {"nope": "deepseek-v4-flash"}})
    assert resp.status_code == 400

    # PUT：未配置的模型 400
    resp = client.put("/api/v1/admin/agent-models", headers=h,
                      json={"agent_models": {"orchestrator": "ghost-model-123"}})
    assert resp.status_code == 400

    # PUT：合法 → 落文件 + settings 热更新 + GET 一致
    resp = client.put("/api/v1/admin/agent-models", headers=h,
                      json={"agent_models": {"orchestrator": "deepseek-v4-pro"}})
    assert resp.status_code == 200
    from config import settings as s
    assert s.AGENT_MODEL_MAP["orchestrator"] == "deepseek-v4-pro"
    am2 = client.get("/api/v1/admin/agent-models", headers=h).json()["agent_models"]
    assert am2["orchestrator"] == "deepseek-v4-pro"

    # 还原默认分配（不留脏状态）
    resp = client.put("/api/v1/admin/agent-models", headers=h,
                      json={"agent_models": {"orchestrator": "deepseek-flash"}})
    assert resp.status_code == 200


def test_delete_model_referenced_blocked(client, db, admin_jwt, models_file_backup, settings_restore):
    h = {"Authorization": f"Bearer {admin_jwt}"}

    # 建自定义模型并分配引用
    assert client.post("/api/v1/admin/models", headers=h,
                       json={"model_id": "test-ghost-model", "label": "测试模型",
                             "provider": "Custom"}).status_code == 200
    assert client.put("/api/v1/admin/agent-models", headers=h,
                      json={"agent_models": {"planet_article": "test-ghost-model"}}).status_code == 200

    # 被引用 → 400 拒绝删除，提示先切换（旧版 TestClient delete 无 json 参数，走 request）
    resp = client.request("DELETE", "/api/v1/admin/models", headers=h,
                          json={"model_id": "test-ghost-model"})
    assert resp.status_code == 400
    assert "planet_article" in resp.json()["detail"]

    # 切换分配后 → 删除成功
    assert client.put("/api/v1/admin/agent-models", headers=h,
                      json={"agent_models": {"planet_article": "doubao-seed-2-1-lite-260915"}}).status_code == 200
    resp = client.request("DELETE", "/api/v1/admin/models", headers=h,
                          json={"model_id": "test-ghost-model"})
    assert resp.status_code == 200


def test_model_upgrade_plan_and_apply(client, db, admin_jwt, models_file_backup, settings_restore):
    """自动检查更新：存量旧分配 → 升级清单 → 确认后自动添加新模型 + 切分配 + 热更新"""
    h = {"Authorization": f"Bearer {admin_jwt}"}

    # 模拟存量自定义分配还指着退役模型
    from api.v1.models_file import write_models_file
    write_models_file({"_agent_models": {
        "orchestrator": "deepseek-v4-flash",
        "memory_fold": "doubao-seed-2-0-lite-260215",
    }})
    from config.settings import reload_agent_models
    reload_agent_models()

    # 检查 → 2 项升级建议
    plan = client.get("/api/v1/admin/models/upgrade-plan", headers=h).json()
    assert len(plan["model_upgrades"]) == 2
    assert {u["old"] for u in plan["model_upgrades"]} == {
        "deepseek-v4-flash", "doubao-seed-2-0-lite-260215"}

    # 确认 → 自动更换
    d = client.post("/api/v1/admin/models/upgrade", headers=h).json()
    assert d["ok"] and len(d["model_upgrades"]) == 2

    from config import settings as s
    assert s.AGENT_MODEL_MAP["orchestrator"] == "deepseek-flash"
    assert s.AGENT_MODEL_MAP["memory_fold"] == "doubao-seed-2-1-lite-260915"
    assert "deepseek-flash" in s.MODELS
    assert "doubao-seed-2-1-lite-260915" in s.MODELS

    # 再检查 → 无待升级
    plan2 = client.get("/api/v1/admin/models/upgrade-plan", headers=h).json()
    assert plan2["model_upgrades"] == []


def test_voice_config_endpoint_roundtrip(client, db, admin_jwt, models_file_backup, settings_restore):
    h = {"Authorization": f"Bearer {admin_jwt}"}

    # 未登录 401
    assert client.get("/api/v1/admin/voice-config").status_code == 401

    # GET：5 个配置键
    resp = client.get("/api/v1/admin/voice-config", headers=h)
    assert resp.status_code == 200
    vc = resp.json()["voice_config"]
    assert len(vc) == 5 and vc["tts_model"] == "seed-tts-2.0"

    # PUT：未知键 400
    resp = client.put("/api/v1/admin/voice-config", headers=h,
                      json={"voice_config": {"nope": "x"}})
    assert resp.status_code == 400

    # PUT：合法 → 落文件 + 热更新 + GET 一致
    resp = client.put("/api/v1/admin/voice-config", headers=h,
                      json={"voice_config": {"tts_model": "seed-tts-9.0"}})
    assert resp.status_code == 200
    from config import settings as s
    assert s.VOICE_TTS_MODEL == "seed-tts-9.0"
    vc2 = client.get("/api/v1/admin/voice-config", headers=h).json()["voice_config"]
    assert vc2["tts_model"] == "seed-tts-9.0"

    # 还原
    resp = client.put("/api/v1/admin/voice-config", headers=h,
                      json={"voice_config": {"tts_model": "seed-tts-2.0"}})
    assert resp.status_code == 200


if __name__ == "__main__":
    print("测试入口：pytest test/test_agent_models_api.py -v")
