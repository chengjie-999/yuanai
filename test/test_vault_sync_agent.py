# -*- coding: utf-8 -*-
"""vault 同步循环测试 — mock HTTP 层 + 临时 vault 目录（纯离线，不触 MySQL）

运行：pytest test/test_vault_sync_agent.py -v
"""
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from agent.vault_sync import VaultSyncLoop  # noqa: E402


@pytest.fixture()
def loop(tmp_path, monkeypatch):
    """自建 loop（server_base 假地址，HTTP 全 mock）；vault 目录 = tmp/vault"""
    vault = tmp_path / "vault"
    vault.mkdir()
    loop = VaultSyncLoop(
        vault_dir=str(vault), agent_id="1", agent_secret="s",
        server_base="http://fake", state_path=str(tmp_path / "state.json"))
    yield loop


def _mk(loop, rel, content, age=10):
    """在 vault 写文件并把 mtime 拨到 age 秒前（满足防抖 now-mtime>3s）"""
    full = os.path.join(loop.vault_dir, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    old = time.time() - age
    os.utime(full, (old, old))


def _stable(loop):
    """预置两轮相同快照（模拟防抖已稳定），下一轮 run_once 即产生候选"""
    snap = loop._scan()
    loop._snap_prev = snap
    loop._snap_prev2 = snap


# ---------------- 冷启动基线 ----------------

def test_cold_start_baseline(loop, monkeypatch):
    calls = []

    def fake_ok(method, path, payload=None, timeout=30):
        calls.append((method, path))
        if path == "/pull/index":
            return True, {"notes": [{"id": 1, "map_id": 0, "title": "我的笔记",
                                     "content_hash": "h1", "source": "ai"}]}
        if path.startswith("/pull/content"):
            return True, {"notes": [{"id": 1, "map_id": 0, "title": "我的笔记",
                                     "content": "# 云端正文", "content_hash": "h1"}]}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    r = loop.run_once()
    assert r["cold_start"] is True

    # 文件落盘（frontmatter 锚点 + 正文）
    out = os.path.join(loop.vault_dir, "知识星球", "我的笔记.md")
    assert os.path.isfile(out)
    text = open(out, encoding="utf-8").read()
    assert text.startswith("---")
    assert "planet_note_id: 1" in text
    assert "# 云端正文" in text
    # 状态已建基线
    assert loop._state["baseline"] is True
    assert loop._state["notes"]["知识星球/我的笔记.md"]["note_id"] == 1


def test_cold_start_no_cloud(loop, monkeypatch):
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    r = loop.run_once()
    assert r["cold_start"] is True
    assert loop._state["baseline"] is True


# ---------------- 新建文件上传 ----------------

def test_new_file_upload(loop, monkeypatch):
    # 冷启动为空
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/新想法.md", "---\nmap_id: 0\n---\n\n新想法正文")
    pushed = []

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": []}
        if path == "/push/upsert":
            pushed.append(payload)
            return True, {"id": 42, "created": True,
                          "content_hash": payload["content"] + "_hash"}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    _stable(loop)
    r = loop.run_once()
    assert r["uploaded"] == 1
    assert pushed[0]["title"] == "新想法"
    assert pushed[0]["content"] == "新想法正文"
    assert loop._state["notes"]["知识星球/新想法.md"]["note_id"] == 42


# ---------------- 三向：修改 → upload ----------------

def test_modified_file_upload(loop, monkeypatch):
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/a.md", "旧内容")
    loop._state["notes"]["知识星球/a.md"] = {"note_id": 7, "base_hash": "oldhash", "status": "ok", "retry": 0}
    loop._save_state()

    pushed = []

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            # 云端未变（base_hash 一致）
            return True, {"notes": [{"id": 7, "map_id": 0, "title": "a",
                                     "content_hash": "oldhash", "source": "user"}]}
        if path == "/push/upsert":
            pushed.append(payload)
            return True, {"id": 7, "created": False, "content_hash": "newhash"}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    _stable(loop)
    r = loop.run_once()
    assert r["uploaded"] == 1
    assert pushed[0]["content"] == "旧内容"
    assert loop._state["notes"]["知识星球/a.md"]["base_hash"] == "newhash"


# ---------------- 三向：云端变 → download ----------------

def test_cloud_change_download(loop, monkeypatch):
    from yuanai_core.pure.vault_note import note_body_hash

    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/b.md", "本地旧版")
    # base = 文件的真实哈希（vault 未变）；云端返回新哈希 → 纯下载
    loop._state["notes"]["知识星球/b.md"] = {"note_id": 8,
                                             "base_hash": note_body_hash("本地旧版", 0),
                                             "status": "ok", "retry": 0}
    loop._save_state()

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": [{"id": 8, "map_id": 0, "title": "b",
                                     "content_hash": "cloudchanged", "source": "ai"}]}
        if path.startswith("/pull/content"):
            return True, {"notes": [{"id": 8, "map_id": 0, "title": "b",
                                     "content": "# 云端新版本"}]}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    _stable(loop)
    r = loop.run_once()
    assert r["downloaded"] == 1
    text = open(os.path.join(loop.vault_dir, "知识星球", "b.md"), encoding="utf-8").read()
    assert "# 云端新版本" in text
    assert loop._state["notes"]["知识星球/b.md"]["base_hash"] != "sharedhash"


# ---------------- 三向：双变 → conflict（本地赢 + conflict 副本） ----------------

def test_conflict_writes_copy_and_local_wins(loop, monkeypatch):
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/c.md", "本地改动版")
    loop._state["notes"]["知识星球/c.md"] = {"note_id": 9, "base_hash": "baseh", "status": "ok", "retry": 0}
    loop._save_state()

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": [{"id": 9, "map_id": 0, "title": "c",
                                     "content_hash": "cloudchanged", "source": "ai"}]}
        if path.startswith("/pull/content"):
            return True, {"notes": [{"id": 9, "map_id": 0, "title": "c",
                                     "content": "# 云端版内容"}]}
        if path == "/push/upsert":
            return True, {"id": 9, "created": False, "content_hash": "localhash"}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    _stable(loop)
    r = loop.run_once()
    assert r["conflicts"] == 1
    # conflict 副本含云端内容
    conflicts = [f for f in os.listdir(os.path.join(loop.vault_dir, "知识星球"))
                 if ".conflict-" in f and f.startswith("c")]
    assert len(conflicts) == 1
    ctext = open(os.path.join(loop.vault_dir, "知识星球", conflicts[0]), encoding="utf-8").read()
    assert "# 云端版内容" in ctext
    # 本地版已被上传（本地赢）
    assert loop._state["notes"]["知识星球/c.md"]["base_hash"] == "localhash"


# ---------------- 本地删除 → trash + push delete ----------------

def test_local_delete_trash_and_push(loop, monkeypatch):
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/d.md", "内容")
    loop._state["notes"]["知识星球/d.md"] = {"note_id": 10, "base_hash": "h", "status": "ok", "retry": 0}
    loop._save_state()
    os.remove(os.path.join(loop.vault_dir, "知识星球", "d.md"))

    deleted = []
    monkeypatch.setattr(loop, "_http_ok",
                        lambda m, p, payload=None, timeout=30:
                        (deleted.append(payload) or True, {"notes": []})
                        if p == "/push/delete" else (True, {"notes": []}))
    _stable(loop)
    r = loop.run_once()
    assert r["deleted"] == 1
    assert deleted[0]["nid"] == 10
    assert "知识星球/d.md" not in loop._state["notes"]
    assert any("d.md" in t["path"] for t in loop._state["trash"])


# ---------------- 请求退避 ----------------

def test_request_backoff_on_failure(loop, monkeypatch):
    now = time.time()
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (False, {"error": "boom"}))
    loop._state["baseline"] = True
    loop._save_state()
    r = loop.run_once(now=now)
    assert loop._request_backoff_s > now  # 已设置退避时间
    # 退避期间再跑一轮 → 直接跳过（不请求）
    r2 = loop.run_once(now=now + 5)
    assert r2["uploaded"] == 0 and r2["downloaded"] == 0 and r2["deleted"] == 0


if __name__ == "__main__":
    print("测试入口：pytest test/test_vault_sync_agent.py -v")


# ===================== S3：落盘格式 =====================

def test_new_file_anchor_backfill(loop, monkeypatch):
    """新文件上传成功后：回填 frontmatter 锚点（文件自描述），正文不动"""
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/无锚点笔记.md", "# 标题\n纯正文，无 frontmatter")

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": []}
        if path == "/push/upsert":
            return True, {"id": 55, "created": True, "content_hash": "hash55"}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    _stable(loop)
    loop.run_once()

    text = open(os.path.join(loop.vault_dir, "知识星球", "无锚点笔记.md"), encoding="utf-8").read()
    assert "planet_note_id: 55" in text
    assert "# 标题\n纯正文，无 frontmatter" in text  # 正文原样保留


def test_baseline_downloads_assets_and_rewrites(loop, monkeypatch):
    """冷启动：asset: 链接改写为本地相对路径 + 图片落盘"""
    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": [{"id": 1, "map_id": 5, "title": "图文笔记",
                                     "planet": "Python学习", "content_hash": "h"}]}
        if path.startswith("/pull/content"):
            return True, {"notes": [{"id": 1, "map_id": 5, "title": "图文笔记",
                                     "content": "看图：![图](asset:5/a.png)"}]}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    monkeypatch.setattr(loop, "_http_raw", lambda path, timeout=60: b"PNGDATA")

    loop.run_once()

    text = open(os.path.join(loop.vault_dir, "知识星球", "图文笔记.md"), encoding="utf-8").read()
    assert "![图](assets/5/a.png)" in text
    assert "asset:5/a.png" not in text
    assert os.path.isfile(os.path.join(loop.vault_dir, "知识星球", "assets", "5", "a.png"))
    # tags 写入
    assert "tags: Python学习" in text


def test_cloud_title_change_renames(loop, monkeypatch):
    """云端标题变化 → vault 文件改名 + 状态迁移"""
    from yuanai_core.pure.vault_note import note_body_hash

    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/旧标题.md", "正文")
    loop._state["notes"]["知识星球/旧标题.md"] = {
        "note_id": 8, "base_hash": note_body_hash("正文", 0), "status": "ok", "retry": 0}
    loop._save_state()

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": [{"id": 8, "map_id": 0, "title": "新标题",
                                     "planet": "收件箱", "content_hash": "cloudnew"}]}
        if path.startswith("/pull/content"):
            return True, {"notes": [{"id": 8, "map_id": 0, "title": "新标题",
                                     "content": "云端新正文"}]}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    _stable(loop)
    r = loop.run_once()
    assert r["downloaded"] == 1 and r["renamed"] == 1
    assert not os.path.exists(os.path.join(loop.vault_dir, "知识星球", "旧标题.md"))
    assert os.path.isfile(os.path.join(loop.vault_dir, "知识星球", "新标题.md"))
    assert "知识星球/新标题.md" in loop._state["notes"]


def test_images_not_uploaded_reported(loop, monkeypatch):
    """上行正文含 asset: 链接（本地图片未上行）→ 状态报告不静默"""
    monkeypatch.setattr(loop, "_http_ok", lambda m, p, payload=None, timeout=30: (True, {"notes": []}))
    loop.run_once()

    _mk(loop, "知识星球/带图.md", "看图 ![x](assets/5/b.png) 还有 ![y](assets/5/c.png)")

    def fake_ok(method, path, payload=None, timeout=30):
        if path == "/pull/index":
            return True, {"notes": []}
        if path == "/push/upsert":
            return True, {"id": 60, "created": True, "content_hash": "h60"}
        return True, {}

    monkeypatch.setattr(loop, "_http_ok", fake_ok)
    _stable(loop)
    r = loop.run_once()
    assert r["uploaded"] == 1
    assert r["images_not_uploaded"] == 2
