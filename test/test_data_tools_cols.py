# -*- coding: utf-8 -*-
"""数据集列清单兼容性回归 — columns 双重编码/字符串列表曾炸 list_datasets

事故（2026-10-14）：用户数据集 columns_info 被双重编码（JSON 里再塞 JSON
字符串），单次 loads 得到字符串，工具按 list[dict] 取下标抛
TypeError「string indices must be integers」，模型一调 list_datasets 整个流断。
运行：pytest test/test_data_tools_cols.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


def test_json_loads_lenient_double_encoded():
    from db.session import _json_loads_lenient
    # 双重编码：json 里再塞 JSON 字符串
    inner = json.dumps([{"name": "客户ID", "dtype": "int64"}], ensure_ascii=False)
    double = json.dumps(inner, ensure_ascii=False)
    assert _json_loads_lenient(double) == [{"name": "客户ID", "dtype": "int64"}]
    # 单层正常
    assert _json_loads_lenient(json.dumps([1, 2])) == [1, 2]
    # 非 JSON 字符串 → 原样返回（调用方有 isinstance list 兜底）
    assert _json_loads_lenient("不是JSON") == "不是JSON"


def test_col_names_tolerant():
    from yuanai_core.tools.data_tools import _col_names
    assert _col_names([{"name": "A"}, {"name": "B"}]) == ["A", "B"]
    assert _col_names(["A", "B", ""]) == ["A", "B"]
    assert _col_names([]) == []
    assert _col_names(None) == []


def test_list_datasets_mixed_columns(monkeypatch):
    """columns 三种形态（dict 列表 / 字符串列表 / 空）混合也不抛异常"""
    from yuanai_core.tools.data_tools import list_datasets

    class FakeDB:
        def get_datasets(self, user_id=None):
            return [
                {"id": 1, "name": "正常", "file_type": "csv", "row_count": 10,
                 "file_size": 1024, "columns": [{"name": "A"}, {"name": "B"}]},
                {"id": 2, "name": "字符串列", "file_type": "csv", "row_count": 10,
                 "file_size": 1024, "columns": ["X", "Y"]},
                {"id": 3, "name": "空列", "file_type": "csv", "row_count": 0,
                 "file_size": 0, "columns": []},
            ]

    monkeypatch.setattr("db.session.get_db", lambda: FakeDB())
    out = list_datasets.invoke({})
    assert "A, B" in out and "X, Y" in out and "#3" in out


def test_preview_dataset_str_columns(monkeypatch):
    from yuanai_core.tools.data_tools import preview_dataset

    class FakeDB:
        def get_dataset(self, ds_id):
            return {"id": 9, "name": "咖啡", "file_type": "csv", "row_count": 2,
                    "columns": ["客户ID", "count"],
                    "preview_rows": [{"客户ID": "101", "count": "14"}]}

    monkeypatch.setattr("db.session.get_db", lambda: FakeDB())
    out = preview_dataset.invoke({"dataset_id": 9})
    assert "| 客户ID | count |" in out and "| 101 | 14 |" in out


if __name__ == "__main__":
    print("测试入口：pytest test/test_data_tools_cols.py -v")
