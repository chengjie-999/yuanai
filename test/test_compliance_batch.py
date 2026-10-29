"""
C5-C11 合规整改批次测试（2026-10-29）

覆盖：C5 aigc 落库 / C6 输出侧审核自动工单 / C7 冻结原因+申诉 /
C8 target=claude 白名单 + 服务端固定提示 / C9 出境开关 / C10 robots 解析 /
C11 协议公开端点 + 同意留痕。
"""
import pytest


def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


class TestC5AigcColumn:
    def test_save_sets_aigc_for_assistant(self, client, auth_headers, db):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        create = client.post("/api/v1/chat/session/new", json={"title": "aigc 测试"}, headers=auth_headers)
        assert create.status_code == 200
        sid = create.json()["session_id"]
        try:
            client.post("/api/v1/chat/save", json={
                "session_id": sid,
                "messages": [{"role": "user", "content": "你好"},
                             {"role": "assistant", "content": "回复"}],
            }, headers=auth_headers)
            from db.session import AIChat
            sess = db.Session()
            try:
                rows = sess.query(AIChat).filter_by(session_id=sid).order_by(AIChat.id).all()
                assert len(rows) == 2
                assert rows[0].aigc == 0   # 用户消息不标识
                assert rows[1].aigc == 1   # AI 消息标识
            finally:
                sess.close()
        finally:
            sess = db.Session()
            try:
                from db.session import AIChat, ChatSession
                sess.query(AIChat).filter_by(session_id=sid).delete()
                sess.query(ChatSession).filter_by(session_id=sid).delete()
                sess.commit()
            finally:
                sess.close()


class TestC6OutputAudit:
    def test_output_audit_hit_creates_auto_report(self, db):
        from api.v1.chat.router import _output_audit
        sid = "sess-audit-c6"
        try:
            hit = _output_audit(99999902, sid, "这是一段包含制造炸弹的违规回复", "test")
            assert hit == "制造炸弹"
            rows = db.list_reports("pending")
            auto = [r for r in rows if r["session_id"] == sid]
            assert auto and auto[0]["source"] == "auto"
            assert "制造炸弹" in auto[0]["reason"]
        finally:
            from db.session import AIReport
            sess = db.Session()
            try:
                sess.query(AIReport).filter_by(session_id=sid).delete()
                sess.commit()
            finally:
                sess.close()

    def test_output_audit_clean_no_report(self, db):
        from api.v1.chat.router import _output_audit
        assert _output_audit(99999902, "sess-audit-c6-clean", "正常回复内容", "test") == ""


class TestC7FreezeAppeal:
    def test_freeze_with_reason_and_login_message(self, client, db):
        """冻结附原因 → 登录 403 详情含原因与申诉指引"""
        r = db.register_user("__freeze_test__", "test1234")
        assert "error" not in r, r
        uid = r["id"]
        try:
            # 冻结 7 天附原因
            sess = db.Session()
            from db.session import User
            from datetime import datetime, timedelta
            u = sess.query(User).filter_by(id=uid).first()
            u.frozen_until = datetime.utcnow() + timedelta(days=7)
            u.freeze_reason = "发布违规内容"
            sess.commit()
            sess.close()
            resp = client.post("/api/v1/auth/login", json={
                "username": "__freeze_test__", "password": "test1234"})
            assert resp.status_code == 403
            detail = resp.json()["detail"]
            assert "发布违规内容" in detail
            assert "申诉" in detail
        finally:
            sess = db.Session()
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
                sess.commit()
            sess.close()

    def test_appeal_flow(self, client, db):
        """申诉端点：冻结账号 → 工单 kind=appeal；未冻结 → 400；不存在 → 404"""
        # 清申诉配额（本机连跑测试会累积 Redis 计数；键形如 quota:appeal:{ip}:{date}）
        try:
            from db.redis_client import get_redis
            from datetime import datetime
            get_redis().delete(f"quota:appeal:testclient:{datetime.now().strftime('%Y%m%d')}")
        except Exception:
            pass
        r = db.register_user("__appeal_test__", "test1234")
        assert "error" not in r, r
        uid = r["id"]
        try:
            from datetime import datetime, timedelta
            sess = db.Session()
            from db.session import User
            u = sess.query(User).filter_by(id=uid).first()
            u.frozen_until = datetime.utcnow() + timedelta(days=3)
            sess.commit()
            sess.close()
            # 公开端点，无需登录
            resp = client.post("/api/v1/auth/appeal", json={
                "username": "__appeal_test__", "contact": "test@example.com",
                "reason": "我认为冻结有误"})
            assert resp.status_code == 200
            rows = db.list_reports("pending")
            hit = [x for x in rows if x["user_id"] == uid and x["kind"] == "appeal"]
            assert hit and "冻结申诉" in hit[0]["reason"]
            # 未冻结账号申诉 → 400
            sess = db.Session()
            u = sess.query(User).filter_by(id=uid).first()
            u.frozen_until = None
            sess.commit()
            sess.close()
            resp = client.post("/api/v1/auth/appeal", json={
                "username": "__appeal_test__", "contact": "x", "reason": "再试"})
            assert resp.status_code == 400
            # 不存在账号 → 404
            assert client.post("/api/v1/auth/appeal", json={
                "username": "no_such_user_xyz", "contact": "x", "reason": "x"}).status_code == 404
        finally:
            from db.session import AIReport
            sess = db.Session()
            sess.query(AIReport).filter_by(user_id=uid).delete()
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
            sess.commit()
            sess.close()


class TestC8ClaudeWhitelist:
    def test_stream_target_claude_requires_whitelist(self, client, auth_headers):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        resp = client.post("/api/v1/chat/stream", json={
            "prompt": "你好", "target_agent": "claude",
        }, headers=auth_headers)
        # 普通用户不在 CLAUDE_BRIDGE_ALLOWED_USERNAMES → 403
        assert resp.status_code == 403

    def test_server_canonical_prompt_nonempty(self):
        from config.settings import CHAT_SYSTEM_PROMPT
        assert CHAT_SYSTEM_PROMPT  # 服务端人设默认值已固化（不再依赖客户端）


class TestC9OverseasGate:
    def test_endpoint_compliant(self, monkeypatch):
        from agent.claude_loop import endpoint_compliant
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "")
        assert endpoint_compliant() is False            # 未设置 → SDK 默认官方端点，违规
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        assert endpoint_compliant() is False            # 官方端点 → 违规
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
        assert endpoint_compliant() is True             # 境内网关 → 合规
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        monkeypatch.setenv("OVERSEAS_BASE_URL_ALLOWED", "1")
        assert endpoint_compliant() is True             # 显式放行
        monkeypatch.delenv("OVERSEAS_BASE_URL_ALLOWED")

    def test_custom_model_overseas_base_url_rejected(self, monkeypatch):
        """lc.get_llm：自定义模型 base_url 非白名单 → ValueError（fail-closed）"""
        import yuanai_core.core.lc as lc
        monkeypatch.setattr(lc, "dsllm", [])
        monkeypatch.setattr(lc, "seed", [])
        monkeypatch.setattr(lc, "_get_stored_key", lambda p: "fake-key")
        from config.settings import MODELS
        monkeypatch.setitem(MODELS, "__overseas_test__", {"provider": "Custom"})
        with pytest.raises(ValueError, match="境内端点白名单"):
            lc.get_llm("__overseas_test__", base_url="https://api.openai.com/v1")
        # 白名单内端点放行（构造成功即可，不实际请求）
        llm = lc.get_llm("__overseas_test__", base_url="https://ark.cn-beijing.volces.com/api/v3")
        assert llm is not None
        monkeypatch.delitem(MODELS, "__overseas_test__")

    def test_web_search_skips_ddg_when_disabled(self, monkeypatch):
        import yuanai_core.pure.web_search as ws
        monkeypatch.setattr("config.settings.OVERSEAS_LOOKUP_ENABLED", False)
        def _raise(q, m): raise AssertionError("DDG 不应被调用")
        monkeypatch.setattr(ws, "_search_ddg", _raise)
        monkeypatch.setattr(ws, "_search_deepseek", lambda q, m: [])
        monkeypatch.setattr(ws, "_search_bing", lambda q, m: [])
        assert ws.web_search("测试关键词") == []  # 走完两级兜底且未碰 DDG


class TestC10Robots:
    def test_parse_robots(self):
        from yuanai_core.pure.crawl_compliance import _parse_robots
        text = (
            "User-agent: *\n"
            "Disallow: /private/\n"
            "Disallow: /admin\n"
            "\n"
            "User-agent: XiaoYuanBot\n"
            "Disallow: /bot-free-zone\n"
            "Crawl-delay: 2\n"
        )
        rules, delay = _parse_robots(text)
        # 本 UA 专属组优先于 *
        assert "/bot-free-zone" in rules
        assert delay == 2
        text2 = "User-agent: *\nDisallow: /\n"
        rules2, _ = _parse_robots(text2)
        assert rules2 == ["/"]  # 根前缀 = 全禁
        # 无匹配组 → 全放行
        assert _parse_robots("") == ([], None)

    def test_guarded_get_deny_raises(self, monkeypatch):
        from yuanai_core.pure.crawl_compliance import guarded_get
        monkeypatch.setattr("yuanai_core.pure.crawl_compliance.check_robots",
                            lambda url: ("deny", ""))
        with pytest.raises(PermissionError, match="robots"):
            guarded_get("https://example.com/blocked")


class TestC11Agreements:
    def test_agreement_endpoints_public(self, client):
        for name, kw in (("terms", "用户协议"), ("privacy", "隐私政策"), ("rules", "投诉举报")):
            resp = client.get(f"/api/v1/docs/agreement/{name}")  # 无 token
            assert resp.status_code == 200, name
            assert kw in resp.text
        assert client.get("/api/v1/docs/agreement/unknown").status_code == 404

    def test_agree_records_timestamp(self, client, auth_headers, db):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        resp = client.post("/api/v1/auth/agree", headers=auth_headers)
        assert resp.status_code == 200
        from db.session import User
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(username="__test_api_user__").first()
            assert u and u.agreed_at is not None
        finally:
            sess.close()
