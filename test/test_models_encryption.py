# -*- coding: utf-8 -*-
"""S3.1 models.json _apikeys 透明加密测试 — 密文落盘/解密读取/旧明文迁移/轮换 CLI

纯离线（monkeypatch _MODELS_PATH 到 tmp，不碰真实 data/models.json）。
运行：pytest test/test_models_encryption.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


@pytest.fixture()
def mf(tmp_path, monkeypatch):
    import api.v1.models_file as mf_mod
    monkeypatch.setattr(mf_mod, "_MODELS_PATH", str(tmp_path / "models.json"))
    monkeypatch.setenv("ENCRYPTION_PASSWORD", "test-password-123")
    return mf_mod


def test_write_encrypts_and_read_decrypts(mf):
    mf.write_models_file({"_apikeys": {"deepseek": "sk-test-123", "doubao": "dk-secret-456"}})
    # 磁盘文本：不含明文，含密文结构
    disk = open(mf._MODELS_PATH, encoding="utf-8").read()
    assert "sk-test-123" not in disk
    assert "dk-secret-456" not in disk
    assert "encrypted_data" in disk and "salt" in disk
    # 读取：透明解密回明文
    data = mf.read_models_file()
    assert data["_apikeys"]["deepseek"] == "sk-test-123"
    assert data["_apikeys"]["doubao"] == "dk-secret-456"


def test_legacy_plaintext_reads_and_migrates(mf):
    """旧明文文件：读得到值；下一次写入自动转密文"""
    json.dump({"_apikeys": {"deepseek": "sk-legacy-789"}},
              open(mf._MODELS_PATH, "w", encoding="utf-8"))
    data = mf.read_models_file()
    assert data["_apikeys"]["deepseek"] == "sk-legacy-789"

    mf.write_models_file(data)  # 任意修改写回 → 自动加密
    disk = open(mf._MODELS_PATH, encoding="utf-8").read()
    assert "sk-legacy-789" not in disk


def test_no_password_plaintext_write_with_warning(mf, monkeypatch, caplog):
    monkeypatch.delenv("ENCRYPTION_PASSWORD", raising=False)
    mf.write_models_file({"_apikeys": {"deepseek": "sk-plain"}})
    disk = open(mf._MODELS_PATH, encoding="utf-8").read()
    assert "sk-plain" in disk
    assert any("明文" in r.message for r in caplog.records)


def test_wrong_password_raises(mf, monkeypatch):
    mf.write_models_file({"_apikeys": {"deepseek": "sk-test-123"}})
    monkeypatch.setenv("ENCRYPTION_PASSWORD", "wrong-password")
    with pytest.raises(Exception):
        mf.read_models_file()


def test_ciphertext_without_password_raises(mf, monkeypatch):
    mf.write_models_file({"_apikeys": {"deepseek": "sk-test-123"}})
    monkeypatch.delenv("ENCRYPTION_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="ENCRYPTION_PASSWORD"):
        mf.read_models_file()


def test_roundtrip_other_keys_untouched(mf):
    """非 _apikeys 键（模型配置等）原样往返，不受加解密影响"""
    original = {
        "doubao-seed-2-0-lite": {"label": "豆包 Lite", "provider": "doubao"},
        "_agent_voices": {"orchestrator": "zh_male_shaonianzixin_uranus_bigtts"},
        "_apikeys": {"deepseek": "sk-test-123"},
    }
    mf.write_models_file(original)
    data = mf.read_models_file()
    assert data["doubao-seed-2-0-lite"] == original["doubao-seed-2-0-lite"]
    assert data["_agent_voices"] == original["_agent_voices"]
    assert data["_apikeys"]["deepseek"] == "sk-test-123"


def test_migrate_cli_roundtrip(mf, monkeypatch, capsys):
    """--migrate 明文转密文；--decrypt-to-plain 密文转明文（轮换密码的标准流程）"""
    # 明文 → migrate → 密文
    json.dump({"_apikeys": {"deepseek": "sk-migrate-1"}},
              open(mf._MODELS_PATH, "w", encoding="utf-8"))
    mf._migrate("migrate")
    disk = open(mf._MODELS_PATH, encoding="utf-8").read()
    assert "sk-migrate-1" not in disk

    # 密文 → decrypt-to-plain → 明文（换密码前必须做的一步）
    mf._migrate("decrypt-to-plain")
    disk = open(mf._MODELS_PATH, encoding="utf-8").read()
    assert "sk-migrate-1" in disk
    assert "encrypted_data" not in disk

    # 幂等：明文再 decrypt-to-plain 不报错
    mf._migrate("decrypt-to-plain")


if __name__ == "__main__":
    print("测试入口：pytest test/test_models_encryption.py -v")
