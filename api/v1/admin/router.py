"""后台管理主路由：仪表盘/Agent 状态 + 聚合各资源子路由（users / agent_devices / resources）"""

from fastapi import APIRouter, HTTPException, Request
from db.session import get_db

from api.v1.admin.users import router as users_router
from api.v1.admin.agent_devices import router as agent_devices_router
from api.v1.admin.resources import router as resources_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(users_router)
router.include_router(agent_devices_router)
router.include_router(resources_router)


# ===================== 仪表盘 =====================


@router.get("/dashboard")
async def admin_dashboard(request: Request):
    # 2026-10-19 安全收口：此前任意登录用户可取全站统计
    from api.v1.middleware import require_admin
    require_admin(request)
    db = get_db()
    with db.session() as sess:
        from db.session import User, ChatSession, AIChat
        from sqlalchemy import func

        user_count = sess.query(func.count(User.id)).scalar() or 0
        session_count = sess.query(func.count(ChatSession.id)).scalar() or 0
        message_count = sess.query(func.count(AIChat.id)).scalar() or 0

        # 最近30天消息数
        from datetime import datetime as dt, timedelta
        thirty_days_ago = dt.utcnow() - timedelta(days=30)
        daily = (
            sess.query(
                func.date(AIChat.create_time).label("date"),
                func.count(AIChat.id).label("count"),
            )
            .filter(AIChat.create_time >= thirty_days_ago)
            .group_by(func.date(AIChat.create_time))
            .order_by(func.date(AIChat.create_time))
            .all()
        )
        daily_messages = [{"date": str(d), "count": c} for d, c in daily]

        # 今日统计
        today = dt.utcnow().strftime("%Y-%m-%d")
        today_messages = sess.query(func.count(AIChat.id)).filter(
            func.date(AIChat.create_time) == today
        ).scalar() or 0
        today_users = sess.query(func.count(func.distinct(AIChat.session_id))).filter(
            func.date(AIChat.create_time) == today
        ).scalar() or 0
        avg_msgs = round(message_count / max(session_count, 1), 1)

        # 数据集数
        import os
        from utils.data_path import root_path
        ds_dir = os.path.join(root_path(), "data", "datasets")
        dataset_count = len(os.listdir(ds_dir)) if os.path.isdir(ds_dir) else 0

        # 网站访问统计（前端埋点 visit_log 表）
        from db.session import VisitLog
        visits = {}
        if True:
            today_pv = sess.query(func.count(VisitLog.id)).filter(
                func.date(VisitLog.create_time) == today).scalar() or 0
            today_uv = sess.query(func.count(func.distinct(VisitLog.ip))).filter(
                func.date(VisitLog.create_time) == today).scalar() or 0
            seven_days_ago = dt.utcnow() - timedelta(days=6)
            visits_daily = (
                sess.query(
                    func.date(VisitLog.create_time).label("date"),
                    func.count(VisitLog.id).label("pv"),
                    func.count(func.distinct(VisitLog.ip)).label("uv"),
                )
                .filter(VisitLog.create_time >= seven_days_ago)
                .group_by(func.date(VisitLog.create_time))
                .order_by(func.date(VisitLog.create_time))
                .all()
            )
            visits = {
                "today_pv": today_pv,
                "today_uv": today_uv,
                "daily": [{"date": str(d), "pv": p, "uv": u} for d, p, u in visits_daily],
            }

        return {
            "users": user_count,
            "sessions": session_count,
            "messages": message_count,
            "today_messages": today_messages,
            "today_users": today_users,
            "avg_messages": avg_msgs,
            "datasets": dataset_count,
            "daily_messages": daily_messages,
            "visits": visits,
        }
# ===================== Agent 状态摘要 =====================


@router.get("/agent-summary")
async def admin_agent_summary(request: Request):
    from api.v1.agent.router import _agents, _agent_info

    result = []
    for agent_id, ws in _agents.items():
        info = _agent_info.get(agent_id, {})
        online = ws.client_state.name == "CONNECTED" if hasattr(ws, 'client_state') else False
        result.append({
            "agent_id": agent_id,
            "agent_name": info.get("agent_name", agent_id),
            "capabilities": info.get("capabilities", []),
            "online": online,
            "last_heartbeat": info.get("last_heartbeat", ""),
        })
    return result


# ===================== Agent 状态（代理到 agent router 内部数据）=====================


@router.get("/agent-status")
async def admin_agent_status_v2(request: Request):
    """返回 Agent 列表（含活动记录）。admin 看全部，普通用户只看自己的。"""
    from api.v1.agent.router import _get_agent_status
    return _get_agent_status(request, include_activities=True)


# ===================== Token 用量统计（支付与金融分析账本） =====================


@router.get("/token-usage")
async def token_usage_stats(request: Request, days: int = 7, group_by: str = "day"):
    """Token 用量聚合（admin）：group_by = day / model / user。

    前端后台仪表盘与后续计费/金融分析共用；数据由 lc.py 用量回调落库。
    """
    from api.v1.middleware import require_admin
    require_admin(request)
    if group_by not in ("day", "model", "user"):
        raise HTTPException(status_code=400, detail="group_by 必须为 day/model/user")
    rows = get_db().query_token_usage(days=max(1, min(days, 90)), group_by=group_by)
    # 成本按模型定价折算（元）；day 聚合口径为「每天各模型的成本之和」
    from yuanai_core.usage import model_cost
    for r in rows:
        if group_by == "model":
            r["cost"] = model_cost(r["key"], r["prompt_tokens"], r["completion_tokens"])
    totals = {
        "total_tokens": sum(r["total_tokens"] for r in rows),
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "calls": sum(r["calls"] for r in rows),
    }
    # 成本总额始终以 model 口径计算（准确）
    model_rows = get_db().query_token_usage(days=max(1, min(days, 90)), group_by="model")
    totals["cost"] = round(sum(
        model_cost(mr["key"], mr["prompt_tokens"], mr["completion_tokens"])
        for mr in model_rows), 2)
    return {"rows": rows, "totals": totals}


# ===================== 用户行为分析（用户维度指标体系） =====================


@router.get("/user-analytics")
async def user_analytics(request: Request, days: int = 30):
    """用户维度数据分析（admin）：流量/页面价值/用户活跃/活跃分层。

    指标体系见 CLAUDE.md 用户分析小节；前端后台「用户维度 → 用户分析」页。
    """
    from api.v1.middleware import require_admin
    require_admin(request)
    return get_db().query_visit_analytics(days=max(7, min(days, 90)))


# ===================== 多维度经营分析（对话/功能/留存/成本） =====================


@router.get("/analytics/{scope}")
async def analytics_scope(request: Request, scope: str, days: int = 30):
    """经营分析统一端点：scope = chat / features / retention / cost"""
    from api.v1.middleware import require_admin
    require_admin(request)
    db = get_db()
    scopes = {
        "chat": db.query_chat_analytics,
        "features": db.query_feature_analytics,
        "retention": db.query_retention_analytics,
        "cost": db.query_cost_analytics,
    }
    fn = scopes.get(scope)
    if not fn:
        raise HTTPException(status_code=400, detail="scope 必须为 chat/features/retention/cost")
    return fn(days=max(7, min(days, 90)))
