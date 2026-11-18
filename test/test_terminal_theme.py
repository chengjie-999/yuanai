# -*- coding: utf-8 -*-
"""终端主题模块测试（T2 品牌对齐，2026-11-18）：
缓存读写/启动链（云端→缓存→env→默认暗）/set_theme_synced 回推。
不触发真实网络——fetch/push cloud 经 monkeypatch。"""

import agent.terminal_theme as tt


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "_THEME_FILE", str(tmp_path / "theme.json"))
    assert tt.read_theme_cache() == ""  # 缺失 → 空
    tt.write_theme_cache("light")
    assert tt.read_theme_cache() == "light"
    tt.write_theme_cache("dark")
    assert tt.read_theme_cache() == "dark"


def test_cache_invalid_or_corrupt(tmp_path, monkeypatch):
    p = tmp_path / "theme.json"
    monkeypatch.setattr(tt, "_THEME_FILE", str(p))
    p.write_text("not json", encoding="utf-8")
    assert tt.read_theme_cache() == ""
    p.write_text('{"theme": "pink"}', encoding="utf-8")
    assert tt.read_theme_cache() == ""


def test_resolve_cloud_wins_and_writes_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "_THEME_FILE", str(tmp_path / "theme.json"))
    monkeypatch.setattr(tt, "fetch_cloud_theme", lambda: "light")
    assert tt.resolve_startup_theme() == "light"
    assert tt.read_theme_cache() == "light"  # 云端值回写缓存


def test_resolve_cloud_down_falls_back_to_cache_then_env_then_dark(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "_THEME_FILE", str(tmp_path / "theme.json"))
    monkeypatch.setattr(tt, "fetch_cloud_theme", lambda: None)  # 云端不可达
    # 缓存命中
    tt.write_theme_cache("light")
    assert tt.resolve_startup_theme() == "light"
    # 缓存空 → TERMINAL_DARK=0 → light（v3 遗留兼容）
    tt.write_theme_cache("")
    monkeypatch.setenv("TERMINAL_DARK", "0")
    assert tt.resolve_startup_theme() == "light"
    monkeypatch.setenv("TERMINAL_DARK", "1")
    assert tt.resolve_startup_theme() == "dark"
    # 全空 → 默认暗色
    monkeypatch.delenv("TERMINAL_DARK")
    assert tt.resolve_startup_theme() == "dark"


def test_set_theme_synced_writes_cache_and_pushes_cloud(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "_THEME_FILE", str(tmp_path / "theme.json"))
    pushed = []
    monkeypatch.setattr(tt, "push_cloud_theme", lambda t, timeout=3: pushed.append(t) or True)
    assert tt.set_theme_synced("light") == "light"
    assert tt.read_theme_cache() == "light"
    assert pushed == ["light"]
    # 非法值兜底 dark
    assert tt.set_theme_synced("pink") == "dark"
    assert tt.read_theme_cache() == "dark"


def test_dispatch_theme_command_toggles_and_syncs(monkeypatch, tmp_path):
    """/theme 经 dispatch_command：翻转主题 + set_theme 渲染器调用 +
    缓存落盘 + 云端回推（set_theme_synced 假实现注入）"""
    import asyncio
    import agent.terminal as t
    import agent.terminal_theme as tt

    calls = []

    class FakeRender:
        blocks_mode = True
        theme_applied = ""

        def set_theme(self, theme):
            self.theme_applied = theme

        def current_theme(self):
            return "dark"

        def info(self, text):
            calls.append(("info", text))

    render = FakeRender()

    class FakeCtx:
        def __init__(self, render):
            self.render = render
            self.mode_ref = ["chat"]

    monkeypatch.setattr(tt, "_THEME_FILE", str(tmp_path / "theme.json"))
    monkeypatch.setattr(tt, "push_cloud_theme", lambda theme, timeout=3: calls.append(("push", theme)) or True)
    asyncio.run(t.dispatch_command("/theme", FakeCtx(render)))
    assert render.theme_applied == "light"        # dark → 翻转 light
    assert tt.read_theme_cache() == "light"
    assert ("push", "light") in calls
    assert any("主题已切换为浅色" in c[1] for c in calls if c[0] == "info")

    # 指定参数：/theme dark
    asyncio.run(t.dispatch_command("/theme dark", FakeCtx(render)))
    assert render.theme_applied == "dark"
    assert tt.read_theme_cache() == "dark"
    assert ("push", "dark") in calls
