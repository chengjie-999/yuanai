# -*- coding: utf-8 -*-
"""桌宠联动写方测试（dsh-pet-indesktop 协议）— 去重/轮转/失败静默/setup 合并"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from agent import pet_events as pe


@pytest.fixture(autouse=True)
def _tmp_path(monkeypatch, tmp_path):
    """事件文件指向临时目录（不碰真实桌宠配置）"""
    monkeypatch.setenv("PET_EVENTS_PATH", str(tmp_path / "agent-events" / "xiaoyuan.jsonl"))
    with pe._lock:
        pe._last = None
    yield tmp_path


def _lines(tmp_path):
    p = tmp_path / "agent-events" / "xiaoyuan.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_emit_basic_and_dedupe(tmp_path):
    pe.emit(state="thinking")
    pe.emit(state="thinking")  # 连续同状态去重
    pe.emit(state="thinking")
    lines = _lines(tmp_path)
    assert len(lines) == 1
    assert lines[0]["state"] == "thinking" and lines[0]["agent"] == "xiaoyuan"
    pe.emit(state="working", tool="bash")
    lines = _lines(tmp_path)
    assert len(lines) == 2 and lines[1]["tool"] == "bash"
    pe.emit(state="working", tool="python -m")  # 工具不同 → 新行
    assert len(_lines(tmp_path)) == 3


def test_emit_event_form_and_state_priority(tmp_path):
    pe.emit(event="PreToolUse", tool="bash")  # 事件名形态（Claude hooks 兼容）
    lines = _lines(tmp_path)
    assert lines[-1]["event"] == "PreToolUse" and "state" not in lines[-1]


def test_rotation_keeps_one_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "ROTATE_BYTES", 200)
    for i in range(5):
        pe.emit(state="thinking" if i % 2 == 0 else "working")
    main = tmp_path / "agent-events" / "xiaoyuan.jsonl"
    bak = tmp_path / "agent-events" / "xiaoyuan.jsonl.1"
    assert main.exists() and bak.exists()
    # 主文件继续可追加
    pe.emit(state="idle")
    assert _lines(tmp_path)[-1]["state"] == "idle"


def test_silent_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_EVENTS_PATH", "Z:/不存在的盘符/x.jsonl")
    pe.emit(state="thinking")  # 路径不可建 → 静默

    import builtins
    real_open = builtins.open

    def _fail(path, mode, *a, **kw):
        if "a" in mode and str(path).endswith("xiaoyuan.jsonl"):
            raise OSError("mock write fail")
        return real_open(path, mode, *a, **kw)

    monkeypatch.setattr(builtins, "open", _fail)
    pe.emit(state="working")  # 写失败也静默


def test_setup_merges_config(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "dsh-pet-standalone"
    cfg_dir.mkdir()
    cfg = {"version": 4, "agent_link": {"custom_agents": [{"key": "gemini", "name": "Gemini", "path": "/x/y.jsonl"}]},
           "other": {"keep": 1}}
    (cfg_dir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pe, "_config_dir", lambda: str(cfg_dir))
    monkeypatch.delenv("PET_EVENTS_PATH", raising=False)
    pe.setup()
    saved = json.loads((cfg_dir / "config.json").read_text(encoding="utf-8"))
    agents = saved["agent_link"]["custom_agents"]
    assert len(agents) == 2  # 既有条目保留
    x = [a for a in agents if a["key"] == "xiaoyuan"][0]
    assert x["name"] == "小元AI" and x["path"].endswith("xiaoyuan.jsonl")
    assert saved["other"]["keep"] == 1  # 其他配置不动
    assert (cfg_dir / "config.json.bak").exists()  # 改前备份
    # 幂等：重复 setup 不产生重复条目
    pe.setup()
    saved2 = json.loads((cfg_dir / "config.json").read_text(encoding="utf-8"))
    assert len(saved2["agent_link"]["custom_agents"]) == 2


if __name__ == "__main__":
    print("测试入口：pytest test/test_pet_events.py -v")
