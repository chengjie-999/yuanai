"""
限流器单元测试 — 使用内存 fallback（不依赖 Redis）
"""
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from api.v1.ratelimit import RateLimiter, get_client_ip


class TestRateLimiter:
    """RateLimiter 基础功能（内存 fallback 模式）"""

    def test_allows_requests_within_limit(self):
        limiter = RateLimiter("test", max_requests=3, window=60)
        # 前 3 次不应抛出异常
        limiter.check("127.0.0.1")
        limiter.check("127.0.0.1")
        limiter.check("127.0.0.1")

    def test_blocks_when_over_limit(self):
        limiter = RateLimiter("test", max_requests=2, window=60)
        limiter.check("10.0.0.1")
        limiter.check("10.0.0.1")
        with pytest.raises(Exception) as exc:
            limiter.check("10.0.0.1")
        assert exc.value.status_code == 429

    def test_different_ips_independent(self):
        limiter = RateLimiter("test", max_requests=2, window=60)
        # IP A 用满
        limiter.check("192.168.1.1")
        limiter.check("192.168.1.1")
        # IP B 不应受影响
        limiter.check("192.168.1.2")
        limiter.check("192.168.1.2")

    def test_window_expiry(self):
        """时间窗口过期后计数应重置"""
        limiter = RateLimiter("test", max_requests=2, window=1)  # 1 秒窗口
        limiter.check("10.0.0.2")
        limiter.check("10.0.0.2")
        # 等待窗口过期
        time.sleep(1.1)
        # 应该可以再次请求
        limiter.check("10.0.0.2")

    def test_fallback_cleanup(self):
        """大量 IP 时清理过期记录"""
        limiter = RateLimiter("test", max_requests=1, window=0)  # 0 秒窗口
        for i in range(200):
            limiter.check(f"10.0.{i // 256}.{i % 256}")
        # 不应内存泄漏（cleanup 在 >10000 条时触发，这里验证不崩溃）


class TestGetClientIP:
    """IP 提取"""

    def test_x_forwarded_for(self):
        from fastapi import Request
        from unittest.mock import MagicMock
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert get_client_ip(mock_req) == "1.2.3.4"

    def test_client_host(self):
        from fastapi import Request
        from unittest.mock import MagicMock
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {}
        mock_req.client.host = "9.9.9.9"
        assert get_client_ip(mock_req) == "9.9.9.9"


class TestPresetLimiters:
    """预置限流器配置"""

    def test_api_limiter(self):
        from api.v1.ratelimit import api_limiter
        assert api_limiter.max_requests == 60
        assert api_limiter.window == 60

    def test_auth_limiter(self):
        from api.v1.ratelimit import auth_limiter
        assert auth_limiter.max_requests == 5
        assert auth_limiter.window == 60

    def test_upload_limiter(self):
        from api.v1.ratelimit import upload_limiter
        assert upload_limiter.max_requests == 10
        assert upload_limiter.window == 60
