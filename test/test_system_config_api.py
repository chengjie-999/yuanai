# -*- coding: utf-8 -*-
"""后台设定中心测试 — 写入 reload 生效 / 校验 / env_override / 模型注册表刷新 / 音色热更新

运行：pytest test/test_system_config_api.py -v
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
    import config.settings as s
    snap = {
        "system": dict(s.SYSTEM_CONFIG),
        "memory": {k: getattr(s, k) for k in (
            "MEMORY_ENABLED", "MEMORY_WORKING_WINDOW", "MEMORY_TRIGGER_CHARS",
            "MEMORY_FOLD_MIN_MESSAGES", "MEMORY_FOLD_MIN_CHARS", "MEMORY_FOLD_INPUT_MAX_CHARS",
            "MEMORY_MAX_ITEMS", "MEMORY_MAX_CHARS", "MEMORY_FOLD_TIMEOUT_S",
            "MEMORY_FOLD_DAILY_MAX", "MEMORY_ORGANIZE_DELETE_DAILY_MAX")},
        "effort": s.REASONING_EFFORT,
        "quota": (s.REGISTER_OPEN, s.DAILY_MESSAGE_QUOTA, s.VOICE_ENABLED),
        "pricing": dict(s.MODEL_PRICING),
        "prompts": (s.SELF_REPORT_TEMPLATE, s.CHAT_SYSTEM_PROMPT, s.CAPABILITY_NOTE),
    }
    yield
    s.SYSTEM_CONFIG.clear(); s.SYSTEM_CONFIG.update(snap["system"])
    for k, v in snap["memory"].items():
        setattr(s, k, v)
    s.REASONING_EFFORT = snap["effort"]
    s.REGISTER_OPEN, s.DAILY_MESSAGE_QUOTA, s.VOICE_ENABLED = snap["quota"]
    s.MODEL_PRICING.clear(); s.MODEL_PRICING.update(snap["pricing"])
    (s.SELF_REPORT_TEMPLATE, s.CHAT_SYSTEM_PROMPT, s.CAPABILITY_NOTE) = snap["prompts"]


def _write_syscfg(cfg: dict):
    os.makedirs(os.path.dirname(_MODELS_PATH), exist_ok=True)
    data = {}
    if os.path.exists(_MODELS_PATH):
        with open(_MODELS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["_system_config"] = cfg
    with open(_MODELS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ---------------- settings 覆盖链（离线） ----------------

def test_reload_system_config_memory_hot_update(models_file_backup, settings_restore):
    from config import settings as s
    _write_syscfg({"memory_working_window": 99, "memory_max_chars": 4321})
    s.reload_system_config()
    assert s.MEMORY_WORKING_WINDOW == 99
    assert s.MEMORY_MAX_CHARS == 4321


def test_reload_system_config_prompts(models_file_backup, settings_restore):
    from config import settings as s
    _write_syscfg({"chat_system_prompt": "你是测试助手", "capability_note": "备注"})
    s.reload_system_config()
    assert s.CHAT_SYSTEM_PROMPT == "你是测试助手"
    assert s.self_report_text("deepseek-flash")  # 默认模板可用
    assert "deepseek-flash" in s.self_report_text("deepseek-flash")


def test_env_priority_over_system_config(models_file_backup, settings_restore, monkeypatch):
    from config import settings as s
    _write_syscfg({"daily_message_quota": 123})
    monkeypatch.setenv("DAILY_MESSAGE_QUOTA", "456")
    s.reload_system_config()
    assert s.DAILY_MESSAGE_QUOTA == 456          # env 优先
    assert s.env_overrides_system_config("daily_message_quota") is True
    assert s.env_overrides_system_config("memory_max_chars") is False


def test_reload_models_registry_refreshes_lc_lists(models_file_backup, settings_restore):
    from config import settings as s
    import yuanai_core.core.lc as lc
    data = {"deepseek-test-model": {"label": "测试", "provider": "DeepSeek"}}
    os.makedirs(os.path.dirname(_MODELS_PATH), exist_ok=True)
    with open(_MODELS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    s.reload_models_registry()
    assert "deepseek-test-model" in s.MODELS and "deepseek-test-model" in s.MODEL_NAMES
    assert "deepseek-test-model" in lc.dsllm  # 新模型走 DeepSeek 通道（无需重启）


def test_reload_agent_voices_hot(models_file_backup, settings_restore):
    from config import settings as s
    _write_syscfg({})  # 确保文件存在
    data = json.load(open(_MODELS_PATH, encoding="utf-8"))
    data["_agent_voices"] = {"orchestrator": "zh_test_voice_uranus_bigtts"}
    with open(_MODELS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    s.reload_agent_voices()
    assert s.AGENT_VOICE_MAP["orchestrator"] == "zh_test_voice_uranus_bigtts"


# ---------------- 端点（需要 MySQL） ----------------

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
    from db.session import User
    from api.v1.auth.utils import create_token
    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__syscfg_admin__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()
    r = db.register_user("__syscfg_admin__", "test123", role="admin")
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


def test_system_config_endpoint_roundtrip(client, db, admin_jwt, models_file_backup, settings_restore):
    h = {"Authorization": f"Bearer {admin_jwt}"}

    # 未登录 401
    assert client.get("/api/v1/admin/system-config").status_code == 401

    # GET：可编辑项 + schema + 运行实况
    resp = client.get("/api/v1/admin/system-config", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert "memory_working_window" in body["editable"]
    assert body["effective"]["tool_count"] > 0

    # PUT：未知键 400
    assert client.put("/api/v1/admin/system-config", headers=h,
                      json={"system_config": {"nope": 1}}).status_code == 400
    # PUT：越界值 400
    assert client.put("/api/v1/admin/system-config", headers=h,
                      json={"system_config": {"memory_working_window": -1}}).status_code == 400
    # PUT：类型错 400
    assert client.put("/api/v1/admin/system-config", headers=h,
                      json={"system_config": {"memory_enabled": "yes"}}).status_code == 400

    # PUT：合法 → 热更新生效
    resp = client.put("/api/v1/admin/system-config", headers=h,
                      json={"system_config": {"memory_working_window": 77}})
    assert resp.status_code == 200
    from config import settings as s
    assert s.MEMORY_WORKING_WINDOW == 77

    # 还原
    client.put("/api/v1/admin/system-config", headers=h,
               json={"system_config": {"memory_working_window": 20}})


def test_chat_system_prompt_endpoint(client, db, admin_jwt):
    h = {"Authorization": f"Bearer {admin_jwt}"}
    resp = client.get("/api/v1/chat/system-prompt", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert "system_prompt" in body and "self_report_template" in body


def test_user_side_agent_models_reloads(client, db, admin_jwt, models_file_backup, settings_restore):
    """用户侧 PUT /auth/agent-models 写盘后热更新（2026-10-17 修复）"""
    from api.v1.models_file import write_models_file
    from config.settings import reload_agent_models
    write_models_file({})
    reload_agent_models()
    h = {"Authorization": f"Bearer {admin_jwt}"}
    resp = client.put("/api/v1/auth/agent-models", headers=h,
                      json={"role": "orchestrator", "model_id": "deepseek-v4-pro"})
    assert resp.status_code == 200
    from config import settings as s
    assert s.AGENT_MODEL_MAP["orchestrator"] == "deepseek-v4-pro"  # 内存已刷新
    # 还原
    client.put("/api/v1/auth/agent-models", headers=h,
               json={"role": "orchestrator", "model_id": "deepseek-flash"})


if __name__ == "__main__":
    print("测试入口：pytest test/test_system_config_api.py -v")
