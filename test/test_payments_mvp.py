"""盈利 MVP 充值闭环测试（2026-11-06）

覆盖：档位校验/订单创建 pending/转账信息提交/归属校验/后台确认入账
（user_paid_totals 仅 confirmed 计入）/驳回/注册赠送 ¥5/收款码上传公开。
"""
import io
import json
import secrets

import pytest

from db.session import get_db


def _db_or_skip():
    try:
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


@pytest.fixture()
def users(db):
    from api.v1.auth.utils import create_token
    from db.session import User, PaymentRecord
    uids = {}
    for name, role in (("__pay_user__", "user"), ("__pay_admin__", "admin")):
        # 先清残留（上轮 teardown 失败等）再创建，保证干净起点
        with db.session() as sess:
            stale = sess.query(User).filter_by(username=name).first()
            if stale:
                for p in sess.query(PaymentRecord).filter_by(user_id=stale.id).all():
                    sess.delete(p)
                sess.delete(stale)
                sess.commit()
        r = db.register_user(name, "test1234", role=role)
        assert "error" not in r, r
        with db.session() as sess:
            u = sess.query(User).filter_by(id=r["id"]).first()
        assert u is not None
        uids[name] = (u.id, create_token(u.id, role))
    yield uids
    from db.session import PaymentRecord, User
    with db.session() as sess:
        for uid, _ in uids.values():
            for p in sess.query(PaymentRecord).filter_by(user_id=uid).all():
                sess.delete(p)
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
        sess.commit()


@pytest.fixture()
def qr_dir(monkeypatch, tmp_path):
    import api.v1.payments as pm
    monkeypatch.setattr(pm, "_QR_PATH", str(tmp_path / "payment_qr.png"))
    return tmp_path


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- 订单链路 ----------------

def test_payment_order_and_confirm_flow(client, db, users):
    uid, tok = users["__pay_user__"]
    admin_tok = users["__pay_admin__"][1]
    h, ah = _h(tok), _h(admin_tok)

    # 非法档位 → 400
    r = client.post("/api/v1/auth/payments", json={"amount": 66, "tail": "8888"}, headers=h)
    assert r.status_code == 400
    # 提交订单（提交成功才创建订单并发送管理员）
    r = client.post("/api/v1/auth/payments", json={"amount": 50, "tail": "8888"}, headers=h)
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["status"] == "pending"
    # 直接出现在管理员确认队列
    assert any(x["id"] == pid for x in db.list_pending_payments()["pending"])
    # 待确认不计入收款总额
    assert db.user_paid_totals([uid]).get(uid, 0) == 0
    # 缺尾号 → 422
    assert client.post("/api/v1/auth/payments",
                       json={"amount": 50}, headers=h).status_code == 422
    # 后台确认 → 计入收款
    r = client.post(f"/api/v1/admin/payments/{pid}/confirm", headers=ah)
    assert r.status_code == 200
    assert db.user_paid_totals([uid]).get(uid, 0) == 50.0


def test_payment_created_at_beijing_time(client, db, users):
    """充值时间用北京时间（云服务器时区 UTC——func.now() 曾差 8 小时）"""
    tok = users["__pay_user__"][1]
    client.post("/api/v1/auth/payments", json={"amount": 50, "tail": "8888"}, headers=_h(tok))
    rec = db.list_payments(users["__pay_user__"][0], limit=1)[0]
    from datetime import datetime
    from yuanai_core.pure.beijing_time import beijing_now
    created = datetime.strptime(rec["created_at"], "%Y-%m-%d %H:%M:%S")
    now = beijing_now()
    # 与北京时间差 < 5 分钟（UTC 写入会差 8 小时）
    assert abs((now - created).total_seconds()) < 300


def test_payment_reject_flow(client, db, users):
    uid, tok = users["__pay_user__"]
    admin_tok = users["__pay_admin__"][1]
    h, ah = _h(tok), _h(admin_tok)
    r = client.post("/api/v1/auth/payments", json={"amount": 10, "tail": "8888"}, headers=h)
    pid = r.json()["id"]
    r = client.post(f"/api/v1/admin/payments/{pid}/reject?note=未收到款", headers=ah)
    assert r.status_code == 200
    assert db.user_paid_totals([uid]).get(uid, 0) == 0  # 驳回不计入
    records = client.get("/api/v1/auth/payments", headers=h).json()["records"]
    rec = next(x for x in records if x["id"] == pid)
    assert rec["status"] == "rejected"


def test_payment_cancel_flow(client, db, users):
    """取消订单（最终流程）：pending 可取消（告知管理员）；终态不可；取消不计收款"""
    uid, tok = users["__pay_user__"]
    ah = _h(users["__pay_admin__"][1])
    h = _h(tok)
    r = client.post("/api/v1/auth/payments", json={"amount": 50, "tail": "8888"}, headers=h)
    pid = r.json()["id"]
    assert any(x["id"] == pid for x in db.list_pending_payments()["pending"])
    # 取消 → 从待确认消失 + 进已取消历史（告知管理员）
    assert client.post(f"/api/v1/auth/payments/{pid}/cancel", headers=h).status_code == 200
    assert db.user_paid_totals([uid]).get(uid, 0) == 0
    assert not any(x["id"] == pid for x in db.list_pending_payments()["pending"])
    assert any(x["id"] == pid for x in db.list_pending_payments()["cancelled"])
    # 已取消再取消 → 409
    assert client.post(f"/api/v1/auth/payments/{pid}/cancel", headers=h).status_code == 409
    # 已确认订单不可取消
    r3 = client.post("/api/v1/auth/payments", json={"amount": 10, "tail": "8888"}, headers=h)
    pid3 = r3.json()["id"]
    client.post(f"/api/v1/admin/payments/{pid3}/confirm", headers=ah)
    assert client.post(f"/api/v1/auth/payments/{pid3}/cancel", headers=h).status_code == 409
    # 取消他人订单 → 404
    other = users["__pay_admin__"][1]
    assert client.post(f"/api/v1/auth/payments/{pid3}/cancel", headers=_h(other)).status_code == 404


def test_payment_detail(client, users):
    """订单详情：归属校验 + 完整信息"""
    tok = users["__pay_user__"][1]
    r = client.post("/api/v1/auth/payments", json={"amount": 50, "tail": "8888", "note": "测试"}, headers=_h(tok))
    pid = r.json()["id"]
    d = client.get(f"/api/v1/auth/payments/{pid}", headers=_h(tok)).json()
    assert d["id"] == pid and d["amount"] == 50.0
    assert "尾号:8888" in d["note"] and "备注:测试" in d["note"]
    # 他人查看 → 404
    other = users["__pay_admin__"][1]
    assert client.get(f"/api/v1/auth/payments/{pid}", headers=_h(other)).status_code == 404


def test_payment_ownership(client, users):
    tok = users["__pay_user__"][1]
    r = client.post("/api/v1/auth/payments", json={"amount": 50, "tail": "8888"}, headers=_h(tok))
    pid = r.json()["id"]
    # 别人取消 → 404
    other = users["__pay_admin__"][1]
    r2 = client.post(f"/api/v1/auth/payments/{pid}/cancel", headers=_h(other))
    assert r2.status_code == 404
    # 未登录 → 401
    assert client.post("/api/v1/auth/payments", json={"amount": 50, "tail": "8888"}).status_code == 401


def test_confirm_with_custom_amount(client, db, users):
    """实际到账金额：管理员核对转账与订单不一致时按实入账（多转多充）"""
    uid, tok = users["__pay_user__"]
    ah = _h(users["__pay_admin__"][1])
    r = client.post("/api/v1/auth/payments", json={"amount": 50, "tail": "8888"}, headers=_h(tok))
    pid = r.json()["id"]
    # 实收 100（多转）→ 按 100 入账
    r = client.post(f"/api/v1/admin/payments/{pid}/confirm", json={"amount": 100}, headers=ah)
    assert r.status_code == 200
    assert db.user_paid_totals([uid]).get(uid, 0) == 100.0
    # 留空 body → 按订单金额
    r2 = client.post("/api/v1/auth/payments", json={"amount": 10, "tail": "8888"}, headers=_h(tok))
    pid2 = r2.json()["id"]
    assert client.post(f"/api/v1/admin/payments/{pid2}/confirm", headers=ah).status_code == 200
    assert db.user_paid_totals([uid]).get(uid, 0) == 110.0
    # 非法金额 → 422
    r3 = client.post("/api/v1/auth/payments", json={"amount": 10, "tail": "8888"}, headers=_h(tok))
    pid3 = r3.json()["id"]
    assert client.post(f"/api/v1/admin/payments/{pid3}/confirm", json={"amount": -5}, headers=ah).status_code == 422


def test_payment_state_machine(client, users, db):
    """状态机（审查加固）：confirmed 不可再改（防误操作吞余额）；
    rejected 可补确认；重复 reject 409。"""
    uid, tok = users["__pay_user__"]
    ah = _h(users["__pay_admin__"][1])
    r = client.post("/api/v1/auth/payments", json={"amount": 10, "tail": "8888"}, headers=_h(tok))
    pid = r.json()["id"]
    # 确认 → 到账
    assert client.post(f"/api/v1/admin/payments/{pid}/confirm", headers=ah).status_code == 200
    assert db.user_paid_totals([uid]).get(uid, 0) == 10.0
    # 再确认/再驳回 → 409（金额不变）
    assert client.post(f"/api/v1/admin/payments/{pid}/confirm", headers=ah).status_code == 409
    assert client.post(f"/api/v1/admin/payments/{pid}/reject", headers=ah).status_code == 409
    assert db.user_paid_totals([uid]).get(uid, 0) == 10.0
    # 新单：驳回 → 可补确认
    r2 = client.post("/api/v1/auth/payments", json={"amount": 10, "tail": "8888"}, headers=_h(tok))
    pid2 = r2.json()["id"]
    assert client.post(f"/api/v1/admin/payments/{pid2}/reject", headers=ah).status_code == 200
    assert client.post(f"/api/v1/admin/payments/{pid2}/reject", headers=ah).status_code == 409  # 幂等拒绝
    assert client.post(f"/api/v1/admin/payments/{pid2}/confirm", headers=ah).status_code == 200  # 补确认
    assert db.user_paid_totals([uid]).get(uid, 0) == 20.0


# ---------------- 注册赠送 ----------------

def test_register_gift(client, db, monkeypatch):
    # 今日本机注册防刷配额已满（测试账号多）——放行
    monkeypatch.setattr("api.v1.db_helpers.consume_daily_quota", lambda *a, **k: True)
    from db.session import User
    name = f"__gift_{secrets.token_hex(3)}__"
    r = client.post("/api/v1/auth/register", json={
        "username": name, "password": "test1234", "agreement_accepted": True,
    })
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    try:
        totals = db.user_paid_totals([uid])
        assert totals.get(uid, 0) == 5.0  # GIFT_AMOUNT 默认 5
    finally:
        from db.session import PaymentRecord
        with db.session() as sess:
            for p in sess.query(PaymentRecord).filter_by(user_id=uid).all():
                sess.delete(p)
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
            sess.commit()


# ---------------- 收款码 ----------------

def test_payment_qr_upload_and_public(client, users, qr_dir):
    from PIL import Image
    img = Image.new("RGB", (64, 64), (37, 99, 235))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    ah = _h(users["__pay_admin__"][1])
    # 未登录上传 → 401/403
    assert client.post("/api/v1/admin/payment-qr",
                       files={"qr": ("a.png", buf.getvalue(), "image/png")}).status_code in (401, 403)
    # 管理员上传 → 公开可读
    r = client.post("/api/v1/admin/payment-qr",
                    files={"qr": ("a.png", buf.getvalue(), "image/png")}, headers=ah)
    assert r.status_code == 200
    pub = client.get("/api/v1/payment-qr")
    assert pub.status_code == 200
    assert pub.headers["content-type"].startswith("image/png")


def test_payment_qr_404_when_unset(client, qr_dir):
    assert client.get("/api/v1/payment-qr").status_code == 404


if __name__ == "__main__":
    print("测试入口：pytest test/test_payments_mvp.py -v")
