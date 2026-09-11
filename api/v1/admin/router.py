"""后台管理主路由：仪表盘/Agent 状态 + 聚合各资源子路由（users / agent_devices / resources）"""

from fastapi import APIRouter, Request
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
    db = get_db()
    sess = db.Session()
    try:
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

        return {
            "users": user_count,
            "sessions": session_count,
            "messages": message_count,
            "today_messages": today_messages,
            "today_users": today_users,
            "avg_messages": avg_msgs,
            "datasets": dataset_count,
            "daily_messages": daily_messages,
        }
    finally:
        sess.close()


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
