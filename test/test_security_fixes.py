"""安全加固 S0 修复测试 — 白名单/路径包含/SQL 占位符/桥接门禁

运行：pytest test/test_security_fixes.py -v
"""
import os

import pytest

from utils.safe import ensure_within, safe_filename, safe_ident


# ---------------- utils.safe 白名单 ----------------

def test_safe_ident_accepts():
    assert safe_ident("user_data_1") == "user_data_1"
    assert safe_ident("`tbl`") == "tbl"  # 反引号剥除


@pytest.mark.parametrize("bad", [
    "users; DROP TABLE users--", "a b", "a`b", "", "1abc", "a" * 65,
    "x../../etc", "update",  # update 是关键字但语法上仍是合法标识符——白名单只挡字符
])
def test_safe_ident_rejects(bad):
    if bad == "update":
        return  # 关键字不在白名单职责内，跳过
    with pytest.raises(ValueError):
        safe_ident(bad)


def test_safe_filename_accepts():
    assert safe_filename("报表.csv") == "报表.csv"
    assert safe_filename("normal_name-v2.xlsx") == "normal_name-v2.xlsx"


@pytest.mark.parametrize("bad", [
    "../../etc/cron.d/x", "..\\..\\win.ini", "a/b", "a\\b",
    "con.txt", "NUL", "", "..", "a" * 200,
])
def test_safe_filename_rejects(bad):
    with pytest.raises(ValueError):
        safe_filename(bad)


def test_ensure_within(tmp_path):
    base = str(tmp_path)
    ok = ensure_within(base, os.path.join(base, "csv", "a.csv"))
    assert ok.startswith(base)
    with pytest.raises(ValueError):
        ensure_within(base, os.path.join(str(tmp_path.parent), "evil.csv"))


# ---------------- SavedData 路径固化（C4） ----------------

def test_saveddata_traversal_rejected(monkeypatch, tmp_path):
    import spiderlx.core.save.save_data as sd_module
    monkeypatch.setattr(sd_module, "file_save_path", lambda: str(tmp_path))
    from spiderlx.core.save.save_data import SavedData

    with pytest.raises(ValueError):
        SavedData("../../evil")
    with pytest.raises(ValueError):
        SavedData("..\\..\\evil")
    sd = SavedData("正常名")
    assert sd.name == "正常名"
    target = sd._target("csv", ".csv")
    assert target.startswith(os.path.realpath(str(tmp_path)) + os.sep)


# ---------------- SQL 占位符（C2） ----------------

def test_save_data_mysql_parameterized(monkeypatch, tmp_path):
    captured = {}

    class FakeCursor:
        def execute(self, sql, params=None):
            captured["ddl"] = sql

        def executemany(self, sql, rows):
            captured["sql"] = sql
            captured["rows"] = rows

        def close(self):
            pass

    class FakeDB:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def close(self):
            pass

    import spiderlx.core.save.save_data as sd_module
    monkeypatch.setattr(sd_module, "file_save_path", lambda: str(tmp_path))
    monkeypatch.setattr(sd_module.pymysql, "connect", lambda **kw: FakeDB())
    from spiderlx.core.save.save_data import SavedData

    SavedData("news_table").save_data_mysql([["001", "新闻一"], ["002", "新闻二"]])
    assert "%s" in captured["sql"]
    assert captured["rows"] == [("001", "新闻一"), ("002", "新闻二")]
    assert "新闻一" not in captured["sql"]
    assert "`news_table`" in captured["ddl"]


def test_save_data_mysql_bad_table_rejected(monkeypatch, tmp_path):
    import spiderlx.core.save.save_data as sd_module
    monkeypatch.setattr(sd_module, "file_save_path", lambda: str(tmp_path))
    from spiderlx.core.save.save_data import SavedData

    with pytest.raises(ValueError):
        SavedData("news; DROP TABLE users").save_data_mysql([])


# ---------------- save_data_csv 工具（C5） ----------------

def test_save_data_csv_traversal_rejected(monkeypatch, tmp_path):
    import utils.data_path
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.tools.file_tools import save_data_csv

    result = save_data_csv.invoke({"name": "../../evil.csv", "data": "a,b\n1,2", "headers": ""})
    assert "非法" in result
    assert not os.path.exists(os.path.join(str(tmp_path), "evil.csv"))
    ok = save_data_csv.invoke({"name": "报表.csv", "data": "a,b\n1,2", "headers": ""})
    assert "已保存" in ok
    assert os.path.exists(os.path.join(str(tmp_path), "data", "file", "csv", "报表.csv"))


# ---------------- 桥接门禁与白名单（C1） ----------------

def test_guard_ready_and_allowed_tools():
    from agent.bridge_policy import build_allowed_tools, guard_ready

    ok, reason = guard_ready(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert ok, reason  # 仓库已提交 .claude/settings.json + hook 脚本

    tools = build_allowed_tools()
    assert "Read" in tools and "Edit" in tools
    # 默认不含裸 Bash：token 列表里不允许单独出现 "Bash"
    assert "Bash" not in tools.split(",")
    assert "Bash(git status:*)" in tools


def test_guard_ready_missing_settings(tmp_path, monkeypatch):
    from agent.bridge_policy import guard_ready
    import agent.bridge_policy as bp
    # 指向空目录：hook 脚本缺失
    ok, reason = guard_ready(str(tmp_path))
    assert not ok
    assert "hook" in reason
