# -*- coding: utf-8 -*-
"""北京时间权威来源测试 — 云服务器 UTC 时区曾致对话时间差 8 小时（2026-10-23）"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from yuanai_core.pure.beijing_time import beijing_now, BEIJING_TZ  # noqa: E402


def test_beijing_tz_offset():
    assert BEIJING_TZ.utcoffset(None) == timedelta(hours=8)


def test_beijing_now_naive():
    n = beijing_now()
    assert n.tzinfo is None  # naive 墙钟：与既有 strftime/日期运算兼容


def test_beijing_now_matches_utc_plus_8():
    n = beijing_now()
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = abs((n - (utc_now + timedelta(hours=8))).total_seconds())
    assert delta < 5, f"北京时间与 UTC+8 偏差 {delta}s"


def test_datetime_tools_use_beijing(monkeypatch):
    from yuanai_core.tools import datetime_tools as dt

    fixed = datetime(2026, 10, 24, 20, 0, 0)  # 固定时刻，工具必须原样使用
    monkeypatch.setattr(dt, "beijing_now", lambda: fixed)

    assert dt.get_current_time.func() == "2026-10-24 20:00:00"
    assert "2026-10-24" in dt.get_weekday.func()
    assert "星期六" in dt.get_weekday.func()  # 2026-10-24 是星期六
    assert "10 天" in dt.calculate_date_diff.func("2026-10-14")


def test_datetime_tools_date_inputs_unchanged(monkeypatch):
    from yuanai_core.tools import datetime_tools as dt

    # 显式传日期不依赖「今天」：add_days/date_diff 行为不变
    assert dt.add_days.func("2026-10-24", 7) == "2026-10-31"
    assert dt.add_days.func("2026-01-01", -1) == "2025-12-31"
