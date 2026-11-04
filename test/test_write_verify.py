"""V1-1 写入-回读校验层测试（2026-11-05）

覆盖：save_data_csv 目录前缀归一化（本地/云端同一份口径）、路径穿越与未知
成分拒绝、写后回读校验失败抛异常、read_data_file 双重拼接修复与 None 防御。
"""
import os

import pytest

import utils.data_path
from utils.safe import resolve_within, normalize_save_filename, verified_write


# ---------------- resolve_within / normalize_save_filename（共享口径） ----------------

def test_resolve_within_relative_and_quotes():
    base = "/app/data/file/csv"
    assert resolve_within("报表.csv", base) == "报表.csv"
    assert resolve_within(' "x.csv" ', base) == "x.csv"
    assert resolve_within("a\\b.csv", base) == "a/b.csv"  # 反斜杠归一
    assert resolve_within("./x.csv", base) == "x.csv"


def test_resolve_within_traversal_rejected():
    base = "/app/data/file/csv"
    with pytest.raises(ValueError):
        resolve_within("../evil.csv", base)
    with pytest.raises(ValueError):
        resolve_within("a/../../evil.csv", base)


def test_resolve_within_absolute_inside_base():
    base = "/app/data/file/csv"
    assert resolve_within("/app/data/file/csv/x.csv", base) == "x.csv"


def test_resolve_within_absolute_outside_rejected():
    base = "/app/data/file/csv"
    with pytest.raises(ValueError):
        resolve_within("/etc/passwd", base)
    with pytest.raises(ValueError):
        resolve_within("C:/Windows/system.ini", base)


def test_normalize_save_filename_dir_prefixes():
    base = "/app/data/file/csv"
    assert normalize_save_filename("报表.csv", base) == "报表.csv"
    assert normalize_save_filename("csv/报表.csv", base) == "报表.csv"
    assert normalize_save_filename("file/csv/报表.csv", base) == "报表.csv"
    assert normalize_save_filename("data/file/csv/报表.csv", base) == "报表.csv"
    assert normalize_save_filename("/app/data/file/csv/报表.csv", base) == "报表.csv"


def test_normalize_save_filename_rejects_unknown_and_traversal():
    base = "/app/data/file/csv"
    # 未知路径成分与穿越：云边报同一错误（同一份实现）
    for bad in ("../x.csv", "a/b.csv", "/etc/passwd", "..", ""):
        with pytest.raises(ValueError):
            normalize_save_filename(bad, base)


# ---------------- verified_write ----------------

def test_verified_write_roundtrip_ok(tmp_path):
    p = str(tmp_path / "x.csv")
    verified_write(p, "a,b\n1,2")
    with open(p, "r", encoding="utf-8-sig") as f:
        assert f.read() == "a,b\n1,2"


def test_verified_write_mismatch_raises(tmp_path, monkeypatch):
    p = str(tmp_path / "x.csv")

    def broken_open(path, mode, encoding="utf-8-sig"):
        raise IOError("磁盘写入失败（模拟）")

    monkeypatch.setattr("builtins.open", broken_open)
    with pytest.raises(IOError):
        verified_write(p, "content")


# ---------------- save_data_csv（云端视角：root_path 指向容器目录） ----------------

def test_save_data_csv_with_dir_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.tools.file_tools import save_data_csv

    out = save_data_csv.invoke({"name": "data/file/csv/报表.csv", "data": "a,b\n1,2", "headers": ""})
    assert "已保存" in out
    assert os.path.exists(os.path.join(str(tmp_path), "data", "file", "csv", "报表.csv"))


def test_save_data_csv_success_returns_canonical_relative_path(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.tools.file_tools import save_data_csv

    out = save_data_csv.invoke({"name": "报表.csv", "data": "a\n1", "headers": ""})
    assert "data/file/csv/报表.csv" in out
    # 不泄漏绝对路径（模型回读时用相对路径也能命中）
    assert str(tmp_path) not in out


def test_save_data_csv_rejects_both_sides_same(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.tools.file_tools import save_data_csv

    r1 = save_data_csv.invoke({"name": "../x.csv", "data": "a", "headers": ""})
    r2 = save_data_csv.invoke({"name": "a/b.csv", "data": "a", "headers": ""})
    assert "非法" in r1 and "非法" in r2
    # 云边同一错误：错误信息形态一致（同一份实现，本地断言锁死）
    assert r1.split(":")[0] == r2.split(":")[0] == "文件名非法"


# ---------------- read_data_file（双重拼接修复 + None 防御） ----------------

def _write(tmp_path, rel, content):
    p = os.path.join(str(tmp_path), rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


def test_read_back_after_save_all_path_forms(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    _write(tmp_path, "data/file/csv/x.csv", "hello")
    from yuanai_core.tools.file_tools import read_data_file

    # 模型常见写法都要读到（此前 data/file/csv/x.csv 双重拼接读不到）
    assert "hello" in read_data_file.invoke({"path": "file/csv/x.csv"})
    assert "hello" in read_data_file.invoke({"path": "data/file/csv/x.csv"})
    abs_p = os.path.join(str(tmp_path), "data", "file", "csv", "x.csv")
    assert "hello" in read_data_file.invoke({"path": abs_p})


def test_read_data_file_traversal_friendly(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.tools.file_tools import read_data_file

    out = read_data_file.invoke({"path": "../.env"})
    assert "不存在" in out


def test_read_data_file_none_and_empty_friendly(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.tools.file_tools import read_data_file

    # path=None 曾触发 pydantic ValidationError（云端「NoneType」报错来源）→ 友好引导
    out = read_data_file.invoke({"path": None})
    assert "请提供文件路径" in out
    assert "请提供文件路径" in read_data_file.invoke({"path": ""})


def test_list_data_files_data_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    _write(tmp_path, "data/file/csv/x.csv", "hello")
    from yuanai_core.tools.file_tools import list_data_files

    assert "x.csv" in list_data_files.invoke({"subdir": "data/file/csv"})
    assert "x.csv" in list_data_files.invoke({"subdir": "file/csv"})


if __name__ == "__main__":
    print("测试入口：pytest test/test_write_verify.py -v")
