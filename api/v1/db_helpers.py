"""聊天/语音/后台共用小工具（单点实现，消除各 router 里的复制粘贴）

历史教训：chat/voice 路由曾各自复制这些 helper 且漏 import，导致运行时 NameError。
新代码一律从这里导入，禁止再复制。
"""

from fastapi import HTTPException

SAFE_ERROR = "请求处理失败，请稍后重试"


def get_db():
    """延迟导入 DB 单例，避免模块级循环依赖"""
    from db.session import get_db as _get_db
    return _get_db()


def verify_session_owner(db, session_id: str, user_id: int):
    """验证会话所有权，不是所有人则抛出 403"""
    sess = db.Session()
    try:
        from db.session import ChatSession
        chat = sess.query(ChatSession).filter_by(session_id=session_id).first()
        if chat and chat.user_id and chat.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问该会话")
    finally:
        sess.close()


def check_daily_quota(key: str, limit: int) -> bool:
    """每日配额计数（Redis INCR + 24h 过期，键含日期）。未超限返回 True；
    Redis 不可用时降级宽松放行（限流失败不阻断服务）。"""
    try:
        from datetime import datetime
        from db.redis_client import get_redis
        rds = get_redis()
        day_key = f"quota:{key}:{datetime.now().strftime('%Y%m%d')}"
        count = rds.incr(day_key)
        if count == 1:
            rds.expire(day_key, 24 * 3600)
        return count <= limit
    except Exception:
        return True
