import logging
from urllib.parse import quote_plus
from sqlalchemy import create_engine, Column, Integer, Text, TIMESTAMP, String, text, UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os
import json
import uuid
from datetime import datetime
from utils.data_path import root_path
from config.settings import DEFAULT_MODEL

logger = logging.getLogger(__name__)

# ---------------------- SQLAlchemy 基础配置 ----------------------
Base = declarative_base()


# ---------------------- 数据库模型定义（对应原表结构） ----------------------
class ChatSession(Base):
    """会话表"""
    __tablename__ = 'chat_session'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    title = Column(String(200), default='新对话')
    model = Column(String(50), default='doubao-seed-2-0-pro-260215')
    is_main = Column(Integer, default=0)  # 1 = 豆包式置顶主对话（每用户一条）
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class AIChat(Base):
    """AI 聊天记录表模型"""
    __tablename__ = 'ai_chat'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    images = Column(Text, nullable=True)
    create_time = Column(TIMESTAMP, server_default=func.now())


class AIChatFeedback(Base):
    """AI 消息反馈表（消息无 id，以数组下标定位，会话内唯一；liked/disliked 三态互斥）"""
    __tablename__ = 'ai_chat_feedback'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    message_index = Column(Integer, nullable=False)
    liked = Column(Integer, default=0)       # 0=未赞 1=已赞
    disliked = Column(Integer, default=0)    # 0=未踩 1=已踩（与 liked 不可同时为 1）
    user_id = Column(Integer, nullable=True, index=True)
    create_time = Column(TIMESTAMP, server_default=func.now())
    __table_args__ = (UniqueConstraint('session_id', 'message_index', name='uq_feedback_session_index'),)


class TokenUsage(Base):
    """Token 用量统计（支付与金融分析账本；lc.py 回调批量落库）"""
    __tablename__ = 'token_usage'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    model = Column(String(64), default='')
    purpose = Column(String(32), default='chat')
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    source = Column(String(16), default='cloud')
    create_time = Column(TIMESTAMP, server_default=func.now())


class SessionMemoryState(Base):
    """会话记忆折叠游标：folded_count = 已折叠进长期记忆的前缀消息条数

    ai_chat 每次 save 全量重建（id 每轮全变），故游标必须是独立持久化的
    前缀计数；编辑重发使消息数组变短时由调用方回夹（clamp）。
    """
    __tablename__ = 'session_memory_state'
    session_id = Column(String(36), primary_key=True)
    user_id = Column(Integer, nullable=True, index=True)
    folded_count = Column(Integer, default=0, nullable=False)
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class TaskImage(Base):
    """任务图片记录表"""
    __tablename__ = 'task_image'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    task_name = Column(Text, nullable=False)
    task_url = Column(Text, nullable=False)
    image_dir = Column(Text, nullable=False)
    image_count = Column(Integer, default=0)
    meta = Column(Text)
    create_time = Column(TIMESTAMP, server_default=func.now())


class VisitLog(Base):
    """网站访问日志（前端埋点上报，后台仪表盘统计 PV/UV）"""
    __tablename__ = 'visit_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(200), nullable=False, default='/')
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(300), nullable=True)
    user_id = Column(Integer, nullable=True, index=True)  # 登录用户行为分析（游客=0）
    create_time = Column(TIMESTAMP, server_default=func.now())


class AnalysisHistory(Base):
    """分析大屏结果历史（Redis 1h TTL 过期后从此恢复，数据不再蒸发）"""
    __tablename__ = 'analysis_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    dataset_id = Column(Integer, nullable=True)
    result_json = Column(Text, nullable=False)
    create_time = Column(TIMESTAMP, server_default=func.now())


class User(Base):
    """用户表"""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    display_name = Column(String(50), default='')
    role = Column(String(20), default='user')
    memory = Column(Text, default='')
    theme = Column(String(10), default='')
    frozen_until = Column(TIMESTAMP, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(TIMESTAMP, nullable=True)
    token_version = Column(Integer, default=0, nullable=False)  # S3.4：令牌吊销计数（+1 全量失效）
    create_time = Column(TIMESTAMP, server_default=func.now())


class AgentDevice(Base):
    """本地 Agent 设备表（机器识别：后台签发安装码 → 本机注册 → 一对一绑定云端用户）

    - id 即 WS 路径的 agent_id（与用户 id 解耦）
    - install_code 由后台预签发（agent_secret 为空 = 未注册），本机注册时消费
    - agent_secret 注册时生成，本机持久化，连接 WS 时校验
    """
    __tablename__ = 'agent_devices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    install_code = Column(String(32), unique=True, nullable=False)
    agent_secret = Column(String(64), default='')  # 空 = 安装码尚未被注册消费
    machine_name = Column(String(64), default='')
    user_id = Column(Integer, nullable=True, index=True)  # 一对一绑定的云端用户
    enabled = Column(Integer, default=1)  # 0 = 冻结
    last_seen = Column(TIMESTAMP, nullable=True)
    create_time = Column(TIMESTAMP, server_default=func.now())


class Website(Base):
    """网站配置表"""
    __tablename__ = 'websites'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    url = Column(Text, nullable=False)
    remark = Column(Text, default='')
    sort_order = Column(Integer, default=0)
    create_time = Column(TIMESTAMP, server_default=func.now())


class CrawlRecord(Base):
    """爬取记录表"""
    __tablename__ = 'crawl_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, nullable=False)
    retype = Column(String(20), default='text')
    file_path = Column(Text, default='')   # 原始文件保存路径
    preview = Column(String(2000), default='')  # 预览文本
    result_length = Column(Integer, default=0)
    parsed_title = Column(String(500), default='')
    parsed_text = Column(Text, default='')
    parsed_links = Column(Text, default='')
    user_id = Column(Integer, nullable=True, index=True)
    create_time = Column(TIMESTAMP, server_default=func.now())


class Dataset(Base):
    """数据集表"""
    __tablename__ = 'datasets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(10), default='csv')
    file_size = Column(Integer, default=0)
    row_count = Column(Integer, default=0)
    columns_info = Column(Text, default='')
    preview_rows = Column(Text, default='')
    source = Column(String(20), default='upload')
    user_id = Column(Integer, nullable=True, index=True)
    analysis_json = Column(Text, default='')
    analyzed_at = Column(TIMESTAMP, nullable=True)
    create_time = Column(TIMESTAMP, server_default=func.now())


class Planet(Base):
    """知识星球表（一级：主题域）"""
    __tablename__ = 'planets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default='')
    sort_order = Column(Integer, default=0)
    map_count = Column(Integer, default=0)   # 冗余计数，列表页免 join
    note_count = Column(Integer, default=0)
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class PlanetMap(Base):
    """思维导图表（二级：导图）"""
    __tablename__ = 'planet_maps'
    id = Column(Integer, primary_key=True, autoincrement=True)
    planet_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # 冗余，单条件隔离查询
    title = Column(String(200), default='')
    source_format = Column(String(16), default='md')      # emmx/html/md/mm/xmind/opml/txt
    origin_filename = Column(String(300), default='')
    dir_path = Column(String(500), default='')            # 相对 data/planet 的目录
    node_count = Column(Integer, default=0)
    max_depth = Column(Integer, default=0)
    quality = Column(String(16), default='full')          # full/text-only/flat
    warnings = Column(Text, default='')                   # JSON 数组
    note_id = Column(Integer, nullable=True)              # 最新 AI 笔记
    status = Column(String(16), default='imported')       # imported/converting/ready/failed
    error = Column(String(500), default='')
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class PlanetNote(Base):
    """线性笔记表（三级：markdown 文章）"""
    __tablename__ = 'planet_notes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    planet_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    map_id = Column(Integer, nullable=True, index=True)   # 可为空 = 自由笔记
    title = Column(String(200), default='')
    # 中文文章 2 万字可超 MySQL TEXT 64KB 上限，必须 MEDIUMTEXT
    content = Column(Text().with_variant(MEDIUMTEXT, 'mysql'))
    summary = Column(String(500), default='')
    source = Column(String(8), default='ai')              # ai/user
    model = Column(String(50), default='')
    word_count = Column(Integer, default=0)
    # vault 同步变更检测：规范化正文的 sha256（空 = 存量数据未回填，读时现算）
    content_hash = Column(String(64), default='')
    status = Column(String(12), default='ready')
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class PlanetJob(Base):
    """知识星球任务表（导入/转换/重建进度，前端轮询）"""
    __tablename__ = 'planet_jobs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    planet_id = Column(Integer, nullable=True, index=True)
    map_id = Column(Integer, nullable=True, index=True)
    job_type = Column(String(16), default='import')       # import/convert/reindex
    status = Column(String(12), default='pending')        # pending/running/done/failed
    progress = Column(Integer, default=0)                 # 0-100
    total_steps = Column(Integer, default=0)
    done_steps = Column(Integer, default=0)
    message = Column(String(500), default='')
    result_json = Column(Text, default='')
    error = Column(String(1000), default='')
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


# ---------------------- 数据库操作类（功能完全对齐原代码） ----------------------
class AgentDatabase:
    def __init__(self, mysql_config: dict = None):
        from utils.sensitive_data import get_mysql_config
        cfg = mysql_config or get_mysql_config()
        logger.info("连接 MySQL: %s:%s/%s", cfg.get('host', 'localhost'), cfg.get('port', 3306), cfg.get('database', 'ai_agent'))
        # 手动构造连接字符串（URL 编码密码，处理 @ 等特殊字符）
        user = cfg.get("user", "root")
        password = quote_plus(cfg.get("password", ""))
        host = cfg.get("host", "localhost")
        port = cfg.get("port", 3306)
        database = cfg.get("database", "ai_agent")
        conn_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        self.engine = create_engine(conn_url, pool_size=5, max_overflow=10)
        Base.metadata.create_all(self.engine)  # 全新数据库首次建表
        self._run_alembic_migrations()         # Alembic 增量迁移（替代原始 ALTER TABLE）
        Base.metadata.create_all(self.engine)  # 迁移后兜底：幂等补建缺失的新表（如无迁移文件的模型）
        self.Session = sessionmaker(bind=self.engine)

    from contextlib import contextmanager

    @contextmanager
    def session(self):
        """上下文管理器，自动关闭会话"""
        sess = self.Session()
        try:
            yield sess
        finally:
            sess.close()

    def _run_alembic_migrations(self):
        """通过 Alembic 执行增量迁移（替代原始 ALTER TABLE）"""
        try:
            from alembic.config import Config
            from alembic import command
            import os

            alembic_ini = os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')
            if not os.path.exists(alembic_ini):
                logger.warning("alembic.ini 不存在，跳过 Alembic 迁移")
                return

            alembic_cfg = Config(alembic_ini)
            # 使用在线连接（共用 engine）
            alembic_cfg.set_main_option("sqlalchemy.url", str(self.engine.url))
            # 将 engine 注入 env.py，避免重复创建连接
            alembic_cfg.attributes["connection"] = self.engine.connect()

            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic 迁移已应用至最新版本")
        except ImportError:
            logger.warning("alembic 未安装，跳过迁移（仅使用 create_all 创建表）")
        except Exception as e:
            logger.error("Alembic 迁移失败，数据库可能缺少新列: %s", e)

    def _init_tables(self):
        """自动创建表：SQLite 全表创建，MySQL 只建聊天相关表"""
        pass

    # --------------------------------------------------------------------------
    # 会话操作
    # --------------------------------------------------------------------------
    def create_session(self, title: str = "新对话", model: str = DEFAULT_MODEL, user_id: int = None) -> dict:
        """创建新会话"""
        session = self.Session()
        try:
            sid = str(uuid.uuid4())
            cs = ChatSession(session_id=sid, title=title, model=model, user_id=user_id)
            session.add(cs)
            session.commit()
            return {"session_id": sid, "title": title, "model": model}
        finally:
            session.close()

    def get_sessions(self, limit: int = 50, user_id: int = None) -> list:
        """获取会话列表（按最后活跃时间倒序：旧对话发新消息后自动置顶）"""
        session = self.Session()
        try:
            q = session.query(ChatSession)
            if user_id is not None:
                q = q.filter(ChatSession.user_id == user_id)
            q = q.order_by(ChatSession.is_main.desc(), ChatSession.update_time.desc()).limit(limit).all()
            return [{"session_id": s.session_id, "title": s.title, "model": s.model,
                     "create_time": str(s.create_time), "update_time": str(s.update_time),
                     "is_main": bool(s.is_main)} for s in q]
        finally:
            session.close()

    def ensure_main_session(self, user_id: int, model: str = "") -> dict:
        """取/建当前用户的置顶主对话（豆包式；每用户一条）"""
        sess = self.Session()
        try:
            row = sess.query(ChatSession).filter_by(user_id=user_id, is_main=1).first()
            if row:
                return {"session_id": row.session_id, "title": row.title,
                        "create_time": str(row.create_time), "is_main": True}
            sid = str(uuid.uuid4())
            sess.add(ChatSession(session_id=sid, user_id=user_id, title="主对话",
                                 model=model or DEFAULT_MODEL, is_main=1))
            sess.commit()
            return {"session_id": sid, "title": "主对话",
                    "create_time": str(datetime.now()), "is_main": True}
        finally:
            sess.close()

    def delete_session(self, session_id: str):
        """删除会话及其所有消息"""
        sess = self.Session()
        try:
            sess.query(AIChat).filter_by(session_id=session_id).delete()
            sess.query(AIChatFeedback).filter_by(session_id=session_id).delete()
            sess.query(SessionMemoryState).filter_by(session_id=session_id).delete()
            sess.query(ChatSession).filter_by(session_id=session_id).delete()
            sess.commit()
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # 聊天记录操作
    # --------------------------------------------------------------------------
    def add_chat(self, session_id: str, role: str, content: str):
        """添加一条聊天记录"""
        session = self.Session()
        try:
            chat = AIChat(session_id=session_id, role=role, content=content)
            session.add(chat)
            session.flush()
            count = session.query(AIChat).filter_by(session_id=session_id).count()
            if role == "user" and count == 1:
                title = content[:80] + ("..." if len(content) > 80 else "")
                session.query(ChatSession).filter_by(session_id=session_id).update(
                    {"title": title, "update_time": func.now()}
                )
            else:
                session.query(ChatSession).filter_by(session_id=session_id).update(
                    {"update_time": func.now()}
                )
            session.commit()
        finally:
            session.close()

    def get_chats(self, session_id: str) -> list:
        """获取指定会话的消息"""
        session = self.Session()
        try:
            chats = session.query(AIChat).filter_by(session_id=session_id).order_by(AIChat.id).all()
            result = [{"role": c.role, "content": c.content, "create_time": str(c.create_time)} for c in chats]
            for i, c in enumerate(chats):
                if c.images:
                    try:
                        result[i]["images"] = json.loads(c.images)
                    except Exception:
                        result[i]["images"] = []
            return result
        finally:
            session.close()

    def clear_chats(self):
        """清空所有聊天记录"""
        session = self.Session()
        try:
            session.query(AIChat).delete()
            session.query(ChatSession).delete()
            session.query(SessionMemoryState).delete()
            session.commit()
        finally:
            session.close()

    # --------------------------------------------------------------------------
    # 分析大屏结果历史
    # --------------------------------------------------------------------------
    def add_analysis_history(self, session_id: str, result_json: str, dataset_id: int = None):
        """保存分析大屏结果（每次分析追加一条；Redis TTL 过期后从此恢复）"""
        sess = self.Session()
        try:
            sess.add(AnalysisHistory(session_id=session_id, dataset_id=dataset_id, result_json=result_json))
            sess.commit()
        finally:
            sess.close()

    def get_analysis_history(self, session_id: str, limit: int = 20) -> list:
        """获取会话的分析大屏历史（最新在前）"""
        sess = self.Session()
        try:
            rows = sess.query(AnalysisHistory).filter_by(session_id=session_id) \
                .order_by(AnalysisHistory.id.desc()).limit(limit).all()
            return [{"id": r.id, "session_id": r.session_id, "dataset_id": r.dataset_id,
                     "result": json.loads(r.result_json) if r.result_json else {},
                     "create_time": str(r.create_time)[:19]} for r in rows]
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # 任务图片记录
    # --------------------------------------------------------------------------
    def save_task_images(self, session_id: str, task_name: str, task_url: str,
                         image_dir: str, image_count: int, meta: list) -> dict:
        """保存任务图片记录到数据库"""
        sess = self.Session()
        try:
            record = TaskImage(
                session_id=session_id,
                task_name=task_name,
                task_url=task_url,
                image_dir=image_dir,
                image_count=image_count,
                meta=json.dumps(meta, ensure_ascii=False),
            )
            sess.add(record)
            sess.commit()
            return {"id": record.id, "session_id": session_id}
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # 用户操作
    # --------------------------------------------------------------------------
    def register_user(self, username: str, password: str, display_name: str = "", role: str = "user") -> dict:
        """注册新用户"""
        import bcrypt as _bcrypt
        sess = self.Session()
        try:
            existing = sess.query(User).filter_by(username=username).first()
            if existing:
                return {"error": "用户名已存在"}
            pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            user = User(
                username=username,
                password_hash=pw_hash,
                display_name=display_name or username,
                role=role,
            )
            sess.add(user)
            sess.commit()
            return {"id": user.id, "username": user.username, "role": user.role}
        finally:
            sess.close()

    def authenticate_user(self, username: str, password: str):
        """验证用户登录，成功返回 user 对象，失败返回 None。
        调用方需自行检查 locked_until 是否已过期。"""
        import bcrypt as _bcrypt
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(username=username).first()
            if user and _bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                return user
            return None
        finally:
            sess.close()

    def get_user_by_username(self, username: str):
        """根据用户名获取用户（用于登录前锁定检查等）"""
        sess = self.Session()
        try:
            return sess.query(User).filter_by(username=username).first()
        finally:
            sess.close()

    def record_failed_login(self, username: str):
        """记录一次登录失败，连续 5 次后锁定 15 分钟"""
        from datetime import datetime, timedelta
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(username=username).first()
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                sess.commit()
        finally:
            sess.close()

    def reset_login_attempts(self, user_id: int):
        """登录成功后重置失败计数和锁定状态"""
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(id=user_id).first()
            if user:
                user.failed_login_attempts = 0
                user.locked_until = None
                sess.commit()
        finally:
            sess.close()

    def get_user_by_id(self, user_id: int):
        """根据 ID 获取用户"""
        sess = self.Session()
        try:
            return sess.query(User).filter_by(id=user_id).first()
        finally:
            sess.close()

    def get_user_memory(self, user_id: int) -> str:
        """获取用户记忆（data/.yuan/ 文件存储；首次读时把旧字段懒迁移为文件）"""
        from yuanai_core import memory_store

        facts = memory_store.load_facts(user_id)
        if facts:
            return "\n".join(facts)
        # 懒迁移：目录为空且旧 users.memory 字段有值 → 导出为文件并清空旧字段
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(id=user_id).first()
            legacy = user.memory if user and user.memory else ""
            if legacy.strip():
                lines = [ln.strip() for ln in legacy.split("\n") if ln.strip()]
                memory_store.add_facts(user_id, lines, source="legacy")
                user.memory = ""
                sess.commit()
                return "\n".join(lines)
            return ""
        finally:
            sess.close()

    def update_user_memory(self, user_id: int, memory: str) -> bool:
        """替换用户记忆（全量覆盖为文件；旧字段已废弃不写）"""
        from yuanai_core import memory_store

        if not self.get_user_by_id(user_id):
            return False
        lines = [ln.strip() for ln in str(memory or "").split("\n") if ln.strip()]
        memory_store.rewrite(user_id, lines, source="edit")
        return True

    # --------------------------------------------------------------------------
    # 记忆机制（会话折叠游标 / 反馈三态 / 记忆合并）
    # --------------------------------------------------------------------------
    def get_session_memory_state(self, session_id: str):
        """读折叠游标；无行返回 None（视作 folded=0）"""
        sess = self.Session()
        try:
            row = sess.query(SessionMemoryState).filter_by(session_id=session_id).first()
            if not row:
                return None
            return {"session_id": row.session_id, "user_id": row.user_id,
                    "folded_count": row.folded_count or 0}
        finally:
            sess.close()

    def upsert_session_memory_state(self, session_id: str, user_id: int, folded_count: int) -> None:
        """幂等 upsert 折叠游标；已存在时取 max（游标只增不减，防并发回退）"""
        sess = self.Session()
        try:
            row = sess.query(SessionMemoryState).filter_by(session_id=session_id).first()
            if row:
                row.folded_count = max(row.folded_count or 0, folded_count)
                row.user_id = user_id or row.user_id
            else:
                sess.add(SessionMemoryState(session_id=session_id, user_id=user_id,
                                            folded_count=folded_count))
            sess.commit()
        finally:
            sess.close()

    def get_session_feedback(self, session_id: str) -> dict:
        """{message_index: {"liked": bool, "disliked": bool}}；两态皆 0 的行不返回"""
        sess = self.Session()
        try:
            rows = sess.query(AIChatFeedback).filter_by(session_id=session_id).all()
            out = {}
            for r in rows:
                if r.liked or r.disliked:
                    out[r.message_index] = {"liked": bool(r.liked), "disliked": bool(r.disliked)}
            return out
        finally:
            sess.close()

    def merge_user_memory(self, user_id: int, new_lines: list, max_items: int, max_chars: int) -> dict:
        """把折叠出的新事实合并进长期记忆（data/.yuan/ 文件存储，per-user 锁）

        只追加 + 双向去重（升级语义）+ 超限丢最旧，逻辑在 yuanai_core.memory.merge_facts。
        返回 {"added": int, "total": int}。
        """
        from yuanai_core import memory_store

        if not self.get_user_by_id(user_id):
            return {"added": 0, "total": 0}
        return memory_store.add_facts(user_id, new_lines,
                                      max_items=max_items, max_chars=max_chars,
                                      source="fold")

    def delete_user_memory_line(self, user_id: int, line: str) -> dict:
        """按行文本删除一条记忆（精确匹配 → 唯一子串匹配；多条命中不误删）

        返回 {"deleted": n, "total": m, "memory": str, "asked_more": bool}
        """
        from yuanai_core import memory_store

        if not self.get_user_by_id(user_id):
            return {"deleted": 0, "total": 0, "memory": "", "asked_more": False}
        return memory_store.delete_fact(user_id, line)

    def get_session_stats(self, session_id: str) -> dict:
        """会话消息条数 + 总字数（一次聚合查询，不加载正文）"""
        from sqlalchemy import func as _func
        sess = self.Session()
        try:
            cnt, total = sess.query(
                _func.count(AIChat.id), _func.coalesce(_func.sum(_func.length(AIChat.content)), 0)
            ).filter(AIChat.session_id == session_id).first()
            return {"msg_count": int(cnt or 0), "total_chars": int(total or 0)}
        finally:
            sess.close()

    def get_user_theme(self, user_id: int) -> str:
        """获取用户主题偏好"""
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(id=user_id).first()
            return (user.theme or '') if user else ''
        finally:
            sess.close()

    def update_user_theme(self, user_id: int, theme: str) -> bool:
        """更新用户主题偏好"""
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(id=user_id).first()
            if not user:
                return False
            user.theme = theme
            sess.commit()
            return True
        finally:
            sess.close()

    def update_display_name(self, user_id: int, display_name: str) -> bool:
        """更新用户显示名称"""
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(id=user_id).first()
            if not user:
                return False
            user.display_name = display_name.strip()
            sess.commit()
            return True
        finally:
            sess.close()

    def change_password(self, user_id: int, old_password: str, new_password: str) -> tuple:
        """修改密码，返回 (成功, 错误消息)"""
        import bcrypt as _bcrypt
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(id=user_id).first()
            if not user:
                return False, "用户不存在"
            if not _bcrypt.checkpw(old_password.encode(), user.password_hash.encode()):
                return False, "原密码错误"
            if len(new_password) < 8:
                return False, "新密码至少 8 个字符"
            user.password_hash = _bcrypt.hashpw(new_password.encode(), _bcrypt.gensalt()).decode()
            sess.commit()
            return True, ""
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # 统计
    # --------------------------------------------------------------------------
    def get_stats(self) -> dict:
        """获取系统统计数据"""
        from sqlalchemy import func as sa_func
        sess = self.Session()
        try:
            # 用户统计
            user_count = sess.query(sa_func.count(User.id)).scalar() or 0

            # 会话统计
            session_count = sess.query(sa_func.count(ChatSession.id)).scalar() or 0
            msg_count = sess.query(sa_func.count(AIChat.id)).scalar() or 0
            avg_msgs = round(msg_count / session_count, 1) if session_count else 0

            # 每日消息量（近30天）
            from datetime import datetime, timedelta
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            daily_rows = sess.query(
                sa_func.date(AIChat.create_time).label('day'),
                sa_func.count(AIChat.id).label('cnt'),
            ).filter(AIChat.create_time >= thirty_days_ago).group_by(sa_func.date(AIChat.create_time)).order_by('day').all()
            daily_messages = [{"date": str(r.day), "count": r.cnt} for r in daily_rows]

            # 任务图片统计
            task_image_count = sess.query(sa_func.count(TaskImage.id)).scalar() or 0

            # 扫描 data/ 下的 Excel/CSV 文件
            import os
            from utils.data_path import root_path
            data_dir = os.path.join(root_path(), 'data')
            excel_files = []
            for root_dir, dirs, files in os.walk(data_dir):
                for f in files:
                    if f.endswith(('.xlsx', '.xls', '.csv')):
                        fpath = os.path.join(root_dir, f)
                        rel = os.path.relpath(fpath, data_dir)
                        excel_files.append({
                            "name": rel,
                            "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                        })

            # 图片缓存大小
            qimg_dir = os.path.join(root_path(), 'data', 'qimg')
            cache_size = 0
            if os.path.exists(qimg_dir):
                for f in os.listdir(qimg_dir):
                    fpath = os.path.join(qimg_dir, f)
                    if os.path.isdir(fpath):
                        for sub in os.listdir(fpath):
                            fp = os.path.join(fpath, sub)
                            if os.path.isfile(fp):
                                cache_size += os.path.getsize(fp)

            return {
                "users": user_count,
                "sessions": session_count,
                "messages": msg_count,
                "avg_messages_per_session": avg_msgs,
                "daily_messages": daily_messages,
                "task_images": task_image_count,
                "cache_size_mb": round(cache_size / 1024 / 1024, 2),
                "excel_files": excel_files,
            }
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # 网站管理
    # --------------------------------------------------------------------------
    def get_websites(self) -> list:
        """获取网站列表"""
        sess = self.Session()
        try:
            rows = sess.query(Website).order_by(Website.sort_order, Website.id).all()
            return [{"id": r.id, "name": r.name, "url": r.url, "remark": r.remark or "", "sort_order": r.sort_order} for r in rows]
        finally:
            sess.close()

    def add_website(self, name: str, url: str, remark: str = "", sort_order: int = 0) -> dict:
        """添加网站"""
        sess = self.Session()
        try:
            existing = sess.query(Website).filter_by(name=name).first()
            if existing:
                return {"error": "网站名称已存在"}
            w = Website(name=name, url=url, remark=remark, sort_order=sort_order)
            sess.add(w)
            sess.commit()
            return {"id": w.id, "name": w.name}
        finally:
            sess.close()

    def update_website(self, wid: int, name: str = None, url: str = None, remark: str = None, sort_order: int = None) -> bool:
        """修改网站"""
        sess = self.Session()
        try:
            w = sess.query(Website).filter_by(id=wid).first()
            if not w:
                return False
            if name is not None:
                w.name = name
            if url is not None:
                w.url = url
            if remark is not None:
                w.remark = remark
            if sort_order is not None:
                w.sort_order = sort_order
            sess.commit()
            return True
        finally:
            sess.close()

    def delete_website(self, wid: int) -> bool:
        """删除网站"""
        sess = self.Session()
        try:
            w = sess.query(Website).filter_by(id=wid).first()
            if not w:
                return False
            sess.delete(w)
            sess.commit()
            return True
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # 爬取记录管理
    # --------------------------------------------------------------------------
    def save_crawl_record(self, url: str, retype: str, file_path: str, preview: str, result_length: int, user_id: int = None) -> dict:
        """保存一条爬取记录，自动查重"""
        sess = self.Session()
        try:
            existing = sess.query(CrawlRecord).filter_by(url=url, user_id=user_id).first()
            if existing:
                # 删除旧文件
                import os
                if existing.file_path and os.path.exists(existing.file_path):
                    try:
                        os.remove(existing.file_path)
                    except Exception:
                        pass
                existing.file_path = file_path
                existing.preview = preview[:2000]
                existing.result_length = result_length
                existing.retype = retype
                sess.commit()
                return {"id": existing.id, "url": url, "duplicate": True}
            r = CrawlRecord(url=url, retype=retype, file_path=file_path, preview=preview[:2000], result_length=result_length, user_id=user_id)
            sess.add(r)
            sess.commit()
            return {"id": r.id, "url": url, "duplicate": False}
        finally:
            sess.close()

    def get_crawl_records(self, user_id: int = None, page: int = 1, limit: int = 20) -> tuple:
        """获取爬取记录列表，返回 (records, total)"""
        sess = self.Session()
        try:
            q = sess.query(CrawlRecord)
            if user_id is not None:
                q = q.filter(CrawlRecord.user_id == user_id)
            total = q.count()
            rows = q.order_by(CrawlRecord.id.desc()).offset((page - 1) * limit).limit(limit).all()
            records = [{
                "id": r.id, "url": r.url, "retype": r.retype,
                "file_path": r.file_path, "preview": r.preview,
                "result_length": r.result_length,
                "parsed_title": r.parsed_title,
                "create_time": str(r.create_time)[:19] if r.create_time else "",
            } for r in rows]
            return records, total
        finally:
            sess.close()

    def get_crawl_record(self, rid: int) -> dict:
        """获取单条爬取记录"""
        sess = self.Session()
        try:
            r = sess.query(CrawlRecord).filter_by(id=rid).first()
            if not r:
                return None
            return {"id": r.id, "url": r.url, "retype": r.retype, "file_path": r.file_path,
                    "preview": r.preview, "result_length": r.result_length,
                    "parsed_title": r.parsed_title, "parsed_text": r.parsed_text, "parsed_links": r.parsed_links,
                    "create_time": str(r.create_time)[:19] if r.create_time else ""}
        finally:
            sess.close()

    def save_parsed_data(self, rid: int, title: str, text: str, links: list) -> bool:
        """保存解析结果到爬取记录"""
        sess = self.Session()
        try:
            import json
            r = sess.query(CrawlRecord).filter_by(id=rid).first()
            if not r:
                return False
            r.parsed_title = title[:500]
            r.parsed_text = text[:50000]
            r.parsed_links = json.dumps(links, ensure_ascii=False)[:5000]
            sess.commit()
            return True
        finally:
            sess.close()

    def delete_crawl_record(self, rid: int) -> bool:
        """删除爬取记录及关联文件"""
        sess = self.Session()
        try:
            r = sess.query(CrawlRecord).filter_by(id=rid).first()
            if not r:
                return False
            # 删除关联文件
            if r.file_path:
                import os
                try:
                    if os.path.exists(r.file_path):
                        os.remove(r.file_path)
                except Exception:
                    pass
            sess.delete(r)
            sess.commit()
            return True
        finally:
            sess.close()


    # --------------------------------------------------------------------------
    # 数据集管理
    # --------------------------------------------------------------------------
    def add_dataset(self, name: str, file_path: str, file_type: str, file_size: int,
                    row_count: int, columns_info: list, preview_rows: list, source: str = 'upload',
                    user_id: int = None) -> int:
        """添加数据集记录，返回 id"""
        import json
        sess = self.Session()
        try:
            ds = Dataset(
                name=name, file_path=file_path, file_type=file_type,
                file_size=file_size, row_count=row_count,
                columns_info=json.dumps(columns_info, ensure_ascii=False),
                preview_rows=json.dumps(preview_rows, ensure_ascii=False),
                source=source, user_id=user_id,
            )
            sess.add(ds)
            sess.commit()
            return ds.id
        finally:
            sess.close()

    def get_datasets(self, user_id: int = None) -> list:
        """获取数据集列表，user_id=None 则返回全部（admin）"""
        sess = self.Session()
        try:
            q = sess.query(Dataset)
            if user_id is not None:
                q = q.filter(Dataset.user_id == user_id)
            rows = q.order_by(Dataset.create_time.desc()).all()
            datasets = []
            for r in rows:
                try:
                    columns_info = json.loads(r.columns_info) if r.columns_info else []
                except Exception:
                    columns_info = []
                datasets.append({
                    "id": r.id, "name": r.name, "file_type": r.file_type,
                    "file_size": r.file_size, "row_count": r.row_count,
                    "columns": columns_info,
                    "source": r.source,
                    "create_time": str(r.create_time)[:19] if r.create_time else "",
                })
            return datasets
        finally:
            sess.close()

    def get_dataset(self, ds_id: int) -> dict:
        """获取单个数据集详情（含预览数据）"""
        import json
        sess = self.Session()
        try:
            r = sess.query(Dataset).filter_by(id=ds_id).first()
            if not r:
                return None
            try:
                columns_info = json.loads(r.columns_info) if r.columns_info else []
            except Exception:
                columns_info = []
            try:
                preview_rows = json.loads(r.preview_rows) if r.preview_rows else []
            except Exception:
                preview_rows = []
            return {
                "id": r.id, "name": r.name, "file_type": r.file_type,
                "file_path": r.file_path, "file_size": r.file_size,
                "row_count": r.row_count,
                "columns": columns_info, "preview_rows": preview_rows,
                "source": r.source, "user_id": r.user_id,
                "create_time": str(r.create_time)[:19] if r.create_time else "",
            }
        finally:
            sess.close()

    def delete_dataset(self, ds_id: int, user_id: int = None) -> bool:
        """删除数据集记录及文件，user_id 非 None 时校验所有权"""
        import os
        sess = self.Session()
        try:
            q = sess.query(Dataset).filter_by(id=ds_id)
            if user_id is not None:
                q = q.filter(Dataset.user_id == user_id)
            r = q.first()
            if not r:
                return False
            if r.file_path and os.path.exists(r.file_path):
                try:
                    os.remove(r.file_path)
                except Exception:
                    pass
            sess.delete(r)
            sess.commit()
            return True
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # 知识星球（星球 / 导图 / 笔记 / 任务）
    # --------------------------------------------------------------------------
    def create_planet(self, user_id: int, name: str, description: str = "", sort_order: int = 0) -> dict:
        """创建星球，返回 {id, name}"""
        sess = self.Session()
        try:
            p = Planet(user_id=user_id, name=name, description=description, sort_order=sort_order)
            sess.add(p)
            sess.commit()
            return {"id": p.id, "name": p.name}
        finally:
            sess.close()

    def list_planets(self, user_id: int) -> list:
        """我的星球列表（按 sort_order 升序，同序按创建时间）"""
        sess = self.Session()
        try:
            rows = sess.query(Planet).filter_by(user_id=user_id) \
                .order_by(Planet.sort_order, Planet.id).all()
            return [{"id": r.id, "name": r.name, "description": r.description or "",
                     "map_count": r.map_count, "note_count": r.note_count,
                     "create_time": str(r.create_time)[:19] if r.create_time else ""} for r in rows]
        finally:
            sess.close()

    def get_planet(self, pid: int, user_id: int = None) -> dict:
        sess = self.Session()
        try:
            q = sess.query(Planet).filter_by(id=pid)
            if user_id is not None:
                q = q.filter_by(user_id=user_id)
            r = q.first()
            if not r:
                return None
            return {"id": r.id, "name": r.name, "description": r.description or "",
                    "map_count": r.map_count, "note_count": r.note_count}
        finally:
            sess.close()

    def update_planet(self, pid: int, user_id: int, name: str = None, description: str = None,
                      sort_order: int = None) -> bool:
        sess = self.Session()
        try:
            r = sess.query(Planet).filter_by(id=pid, user_id=user_id).first()
            if not r:
                return False
            if name is not None:
                r.name = name
            if description is not None:
                r.description = description
            if sort_order is not None:
                r.sort_order = sort_order
            sess.commit()
            return True
        finally:
            sess.close()

    def delete_planet(self, pid: int, user_id: int) -> bool:
        """删星球（DB 行级联；文件目录与 Milvus 由 store 层负责）"""
        sess = self.Session()
        try:
            r = sess.query(Planet).filter_by(id=pid, user_id=user_id).first()
            if not r:
                return False
            sess.query(PlanetMap).filter_by(planet_id=pid).delete()
            sess.query(PlanetNote).filter_by(planet_id=pid).delete()
            sess.query(PlanetJob).filter_by(planet_id=pid).delete()
            sess.delete(r)
            sess.commit()
            return True
        finally:
            sess.close()

    def add_map(self, user_id: int, planet_id: int, title: str, source_format: str,
                origin_filename: str, dir_path: str, node_count: int, max_depth: int,
                quality: str, warnings: list) -> int:
        sess = self.Session()
        try:
            m = PlanetMap(user_id=user_id, planet_id=planet_id, title=title,
                          source_format=source_format, origin_filename=origin_filename,
                          dir_path=dir_path, node_count=node_count, max_depth=max_depth,
                          quality=quality, warnings=json.dumps(warnings, ensure_ascii=False))
            sess.add(m)
            sess.commit()
            self._refresh_planet_counts(sess, planet_id)
            return m.id
        finally:
            sess.close()

    def get_map(self, mid: int, user_id: int = None) -> dict:
        sess = self.Session()
        try:
            q = sess.query(PlanetMap).filter_by(id=mid)
            if user_id is not None:
                q = q.filter_by(user_id=user_id)
            r = q.first()
            if not r:
                return None
            try:
                warnings = json.loads(r.warnings) if r.warnings else []
            except Exception:
                warnings = []
            return {"id": r.id, "planet_id": r.planet_id, "user_id": r.user_id, "title": r.title,
                    "source_format": r.source_format, "origin_filename": r.origin_filename,
                    "dir_path": r.dir_path, "node_count": r.node_count, "max_depth": r.max_depth,
                    "quality": r.quality, "warnings": warnings, "note_id": r.note_id,
                    "status": r.status, "error": r.error or "",
                    "create_time": str(r.create_time)[:19] if r.create_time else ""}
        finally:
            sess.close()

    def list_maps(self, planet_id: int, user_id: int = None) -> list:
        sess = self.Session()
        try:
            q = sess.query(PlanetMap).filter_by(planet_id=planet_id)
            if user_id is not None:
                q = q.filter_by(user_id=user_id)
            rows = q.order_by(PlanetMap.id.desc()).all()
            out = []
            for r in rows:
                try:
                    warnings = json.loads(r.warnings) if r.warnings else []
                except Exception:
                    warnings = []
                out.append({"id": r.id, "planet_id": r.planet_id, "title": r.title,
                            "source_format": r.source_format, "node_count": r.node_count,
                            "max_depth": r.max_depth, "quality": r.quality, "warnings": warnings,
                            "note_id": r.note_id, "status": r.status, "error": r.error or "",
                            "create_time": str(r.create_time)[:19] if r.create_time else ""})
            return out
        finally:
            sess.close()

    def update_map(self, mid: int, user_id: int, **fields) -> bool:
        sess = self.Session()
        try:
            r = sess.query(PlanetMap).filter_by(id=mid, user_id=user_id).first()
            if not r:
                return False
            for k, v in fields.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            sess.commit()
            return True
        finally:
            sess.close()

    def delete_map(self, mid: int, user_id: int) -> dict:
        """删导图行，返回 {planet_id} 供 store 层清目录与索引；不存在返回 None"""
        sess = self.Session()
        try:
            r = sess.query(PlanetMap).filter_by(id=mid, user_id=user_id).first()
            if not r:
                return None
            planet_id = r.planet_id
            sess.query(PlanetNote).filter_by(map_id=mid).delete()
            sess.query(PlanetJob).filter_by(map_id=mid).delete()
            sess.delete(r)
            sess.commit()
            self._refresh_planet_counts(sess, planet_id)
            return {"planet_id": planet_id}
        finally:
            sess.close()

    def add_note(self, user_id: int, planet_id: int, map_id: int, title: str, content: str,
                 source: str = "user", model: str = "", summary: str = "") -> int:
        from yuanai_core.pure.vault_note import note_body_hash
        sess = self.Session()
        try:
            n = PlanetNote(user_id=user_id, planet_id=planet_id, map_id=map_id, title=title,
                           content=content, source=source, model=model, summary=summary,
                           word_count=len(content),
                           content_hash=note_body_hash(content, map_id or 0))
            sess.add(n)
            sess.commit()
            if map_id:
                sess.query(PlanetMap).filter_by(id=map_id).update({"note_id": n.id, "status": "ready"})
                sess.commit()
            self._refresh_planet_counts(sess, planet_id)
            return n.id
        finally:
            sess.close()

    def get_note(self, nid: int, user_id: int = None) -> dict:
        sess = self.Session()
        try:
            q = sess.query(PlanetNote).filter_by(id=nid)
            if user_id is not None:
                q = q.filter_by(user_id=user_id)
            r = q.first()
            if not r:
                return None
            return {"id": r.id, "planet_id": r.planet_id, "map_id": r.map_id, "title": r.title,
                    "content": r.content or "", "summary": r.summary or "", "source": r.source,
                    "model": r.model, "word_count": r.word_count,
                    "create_time": str(r.create_time)[:19] if r.create_time else "",
                    "update_time": str(r.update_time)[:19] if r.update_time else ""}
        finally:
            sess.close()

    def list_notes(self, user_id: int, planet_id: int = None, map_id: int = None) -> list:
        """笔记列表（不含正文，仅标题/摘要/字数）"""
        sess = self.Session()
        try:
            q = sess.query(PlanetNote).filter_by(user_id=user_id)
            if planet_id is not None:
                q = q.filter_by(planet_id=planet_id)
            if map_id is not None:
                q = q.filter_by(map_id=map_id)
            rows = q.order_by(PlanetNote.id.desc()).all()
            return [{"id": r.id, "planet_id": r.planet_id, "map_id": r.map_id, "title": r.title,
                     "summary": r.summary or "", "source": r.source, "word_count": r.word_count,
                     "update_time": str(r.update_time)[:19] if r.update_time else ""} for r in rows]
        finally:
            sess.close()

    def update_note(self, nid: int, user_id: int, content: str = None, title: str = None,
                    summary: str = None, source: str = None) -> bool:
        from yuanai_core.pure.vault_note import note_body_hash
        sess = self.Session()
        try:
            r = sess.query(PlanetNote).filter_by(id=nid, user_id=user_id).first()
            if not r:
                return False
            if content is not None:
                r.content = content
                r.word_count = len(content)
                r.content_hash = note_body_hash(content, r.map_id or 0)
            if title is not None:
                r.title = title
            if summary is not None:
                r.summary = summary
            if source is not None:
                r.source = source
            sess.commit()
            return True
        finally:
            sess.close()

    # --------------------------------------------------------------------------
    # vault 同步专用读接口
    # --------------------------------------------------------------------------
    def list_notes_index(self, user_id: int) -> list:
        """笔记索引（不含正文）：id/map_id/title/content_hash/update_time + 星球名（tags 用）。
        content_hash 空 = 存量未回填 → 现算（读一次正文，兼容先发代码后迁移）。"""
        from yuanai_core.pure.vault_note import note_body_hash
        sess = self.Session()
        try:
            rows = (sess.query(PlanetNote, Planet.name)
                    .outerjoin(Planet, Planet.id == PlanetNote.planet_id)
                    .filter(PlanetNote.user_id == user_id)
                    .order_by(PlanetNote.id).all())
            out = []
            for r, planet_name in rows:
                h = r.content_hash or ""
                if not h and r.content:
                    h = note_body_hash(r.content, r.map_id or 0)
                out.append({"id": r.id, "map_id": r.map_id or 0, "title": r.title,
                            "planet": planet_name or "收件箱",
                            "content_hash": h, "source": r.source,
                            "update_time": str(r.update_time)[:19] if r.update_time else ""})
            return out
        finally:
            sess.close()

    def get_notes_content(self, user_id: int, nids: list) -> list:
        """批量取正文（pull content 用；无正文内容返回 content='' 而非缺行）"""
        sess = self.Session()
        try:
            rows = sess.query(PlanetNote).filter(
                PlanetNote.user_id == user_id, PlanetNote.id.in_(nids)).all()
            found = {r.id: r for r in rows}
            return [{"id": nid, "title": found[nid].title,
                     "content": found[nid].content or "",
                     "map_id": found[nid].map_id or 0,
                     "content_hash": found[nid].content_hash or ""}
                    for nid in nids if nid in found]
        finally:
            sess.close()

    def find_note_by_map(self, user_id: int, map_id: int):
        """按 map_id 找笔记（vault 锚点 map_id 反查云端行）"""
        sess = self.Session()
        try:
            r = sess.query(PlanetNote).filter_by(user_id=user_id, map_id=map_id).first()
            if not r:
                return None
            return {"id": r.id, "planet_id": r.planet_id, "map_id": r.map_id or 0,
                    "title": r.title, "content": r.content or "",
                    "content_hash": r.content_hash or "", "source": r.source}
        finally:
            sess.close()

    def delete_note(self, nid: int, user_id: int) -> dict:
        """删笔记行，返回 {planet_id, map_id} 供索引清理；不存在返回 None"""
        sess = self.Session()
        try:
            r = sess.query(PlanetNote).filter_by(id=nid, user_id=user_id).first()
            if not r:
                return None
            planet_id, map_id = r.planet_id, r.map_id
            sess.delete(r)
            if map_id:
                sess.query(PlanetMap).filter_by(id=map_id).update({"note_id": None})
            sess.commit()
            self._refresh_planet_counts(sess, planet_id)
            return {"planet_id": planet_id, "map_id": map_id}
        finally:
            sess.close()

    def create_job(self, user_id: int, job_type: str, planet_id: int = None, map_id: int = None) -> int:
        sess = self.Session()
        try:
            j = PlanetJob(user_id=user_id, job_type=job_type, planet_id=planet_id, map_id=map_id,
                          status="pending", progress=0)
            sess.add(j)
            sess.commit()
            return j.id
        finally:
            sess.close()

    def get_job(self, jid: int, user_id: int = None) -> dict:
        sess = self.Session()
        try:
            q = sess.query(PlanetJob).filter_by(id=jid)
            if user_id is not None:
                q = q.filter_by(user_id=user_id)
            r = q.first()
            if not r:
                return None
            return {"id": r.id, "job_type": r.job_type, "status": r.status, "progress": r.progress,
                    "total_steps": r.total_steps, "done_steps": r.done_steps,
                    "message": r.message or "", "error": r.error or "",
                    "result_json": r.result_json or "",
                    "planet_id": r.planet_id, "map_id": r.map_id,
                    "update_time": str(r.update_time)[:19] if r.update_time else ""}
        finally:
            sess.close()

    def update_job(self, jid: int, user_id: int, **fields) -> bool:
        sess = self.Session()
        try:
            r = sess.query(PlanetJob).filter_by(id=jid, user_id=user_id).first()
            if not r:
                return False
            for k, v in fields.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            sess.commit()
            return True
        finally:
            sess.close()

    def has_running_job(self, user_id: int, job_type: str) -> bool:
        sess = self.Session()
        try:
            return sess.query(PlanetJob).filter_by(user_id=user_id, job_type=job_type,
                                                   status="running").count() > 0
        finally:
            sess.close()

    def _refresh_planet_counts(self, sess, planet_id: int):
        """重算星球的 map/note 冗余计数（写入后调用）"""
        from sqlalchemy import func as sa_func
        map_count = sess.query(sa_func.count(PlanetMap.id)).filter_by(planet_id=planet_id).scalar() or 0
        note_count = sess.query(sa_func.count(PlanetNote.id)).filter_by(planet_id=planet_id).scalar() or 0
        sess.query(Planet).filter_by(id=planet_id).update({"map_count": map_count, "note_count": note_count})
        sess.commit()

    # ===================== 简易键值存储（审计反馈等） =====================

    def set_state(self, key: str, value: dict) -> None:
        """保存键值对状态（JSON 文件存储，跨 Agent 重启持久化）"""
        import json as _json, os as _os, threading as _threading
        _lock = getattr(self, '_state_lock', None)
        if _lock is None:
            _lock = _threading.Lock()
            self._state_lock = _lock
        with _lock:
            try:
                state_file = _os.path.join(
                    _os.path.dirname(_os.path.dirname(__file__)), 'data', 'agent_state.json'
                )
                _os.makedirs(_os.path.dirname(state_file), exist_ok=True)
                data = {}
                if _os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f:
                        data = _json.load(f)
                data[key] = value
                with open(state_file, 'w', encoding='utf-8') as f:
                    _json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("set_state 失败 key=%s: %s", key, e)

    def get_state(self, key: str) -> dict | None:
        """读取键值对状态"""
        import json as _json, os as _os
        try:
            state_file = _os.path.join(
                _os.path.dirname(_os.path.dirname(__file__)), 'data', 'agent_state.json'
            )
            if not _os.path.exists(state_file):
                return None
            with open(state_file, 'r', encoding='utf-8') as f:
                data = _json.load(f)
            return data.get(key)
        except Exception as e:
            logger.warning("get_state 失败 key=%s: %s", key, e)
            return None

    def get_all_states(self) -> dict:
        """读取全部键值对状态"""
        import json as _json, os as _os
        try:
            state_file = _os.path.join(
                _os.path.dirname(_os.path.dirname(__file__)), 'data', 'agent_state.json'
            )
            if not _os.path.exists(state_file):
                return {}
            with open(state_file, 'r', encoding='utf-8') as f:
                return _json.load(f)
        except Exception as e:
            logger.warning("get_all_states 失败: %s", e)
            return {}

    # --------------------------------------------------------------------------
    # Token 用量统计（支付与金融分析）
    # --------------------------------------------------------------------------
    def record_visit(self, path: str, ip: str, user_agent: str, user_id: int = 0) -> None:
        """记录一次页面访问（用户维度分析数据源；游客 user_id=0）"""
        sess = self.Session()
        try:
            sess.add(VisitLog(path=path[:200], ip=ip[:64],
                              user_agent=user_agent[:300], user_id=user_id or 0))
            sess.commit()
        finally:
            sess.close()

    def query_visit_analytics(self, days: int = 30) -> dict:
        """用户行为分析（指标体系 L1-L3）：
        - overview: 今日/近N天 PV、UV（按 IP 去重）、登录用户 PV 占比
        - pages: 页面访问排行（path → PV/UV/登录PV）
        - daily: 近 N 天 PV/UV 趋势
        - users: 活跃用户排行（用户名/访问次数/访问天数/会话数/消息数/最后活跃）
        - segments: 活跃分层（高活≥15天/中活7-14/低活1-6/流失0，近30天口径）
        """
        from sqlalchemy import func as _func, distinct, text as _text, case as _case
        sess = self.Session()
        try:
            since = _text(f"DATE_SUB(CURDATE(), INTERVAL {int(days) - 1} DAY)")
            today = _text("CURDATE()")

            # 今日
            t_pv, t_uv, t_login = sess.query(
                _func.count(VisitLog.id),
                _func.count(distinct(VisitLog.ip)),
                _func.count(VisitLog.id),
            ).filter(VisitLog.create_time >= today).first()
            t_login_uv = sess.query(_func.count(distinct(VisitLog.user_id))).filter(
                VisitLog.create_time >= today, VisitLog.user_id > 0).first()[0] or 0
            # 近 N 天
            n_pv, n_uv, n_login = sess.query(
                _func.count(VisitLog.id),
                _func.count(distinct(VisitLog.ip)),
                _func.count(VisitLog.id),
            ).filter(VisitLog.create_time >= since).first()
            n_login_uv = sess.query(_func.count(distinct(VisitLog.user_id))).filter(
                VisitLog.create_time >= since, VisitLog.user_id > 0).first()[0] or 0

            overview = {
                "today": {"pv": int(t_pv or 0), "uv": int(t_uv or 0),
                          "login_uv": int(t_login_uv)},
                "period": {"pv": int(n_pv or 0), "uv": int(n_uv or 0),
                           "login_uv": int(n_login_uv),
                           "login_ratio": round((int(n_login or 0) / max(int(n_pv or 0), 1)) * 100, 1)},
            }

            # 页面排行（近 N 天，前 12）
            page_rows = (sess.query(VisitLog.path.label("path"),
                                    _func.count(VisitLog.id).label("pv"),
                                    _func.count(distinct(VisitLog.ip)).label("uv"),
                                    _func.sum(_case((VisitLog.user_id > 0, 1), else_=0)).label("login_pv"))
                         .filter(VisitLog.create_time >= since)
                         .group_by(VisitLog.path)
                         .order_by(_func.count(VisitLog.id).desc()).limit(12).all())
            pages = [{"path": r.path, "pv": int(r.pv or 0), "uv": int(r.uv or 0),
                      "login_pv": int(r.login_pv or 0)} for r in page_rows]

            # 日趋势（补零由前端做）
            daily_rows = (sess.query(_func.date(VisitLog.create_time).label("d"),
                                     _func.count(VisitLog.id).label("pv"),
                                     _func.count(distinct(VisitLog.ip)).label("uv"))
                          .filter(VisitLog.create_time >= since)
                          .group_by("d").order_by("d").all())
            daily = [{"date": str(r.d), "pv": int(r.pv or 0), "uv": int(r.uv or 0)}
                     for r in daily_rows]

            # 活跃用户排行（JOIN users；访问天数 = 有访问记录的不同日期数）
            user_rows = (sess.query(VisitLog.user_id.label("uid"),
                                    User.username.label("username"),
                                    _func.count(VisitLog.id).label("visits"),
                                    _func.count(distinct(_func.date(VisitLog.create_time))).label("days"),
                                    _func.max(VisitLog.create_time).label("last"))
                         .join(User, User.id == VisitLog.user_id)
                         .filter(VisitLog.user_id > 0, VisitLog.create_time >= since)
                         .group_by(VisitLog.user_id, User.username)
                         .order_by(_func.count(VisitLog.id).desc()).limit(15).all())
            users = [{"user_id": r.uid, "username": r.username, "visits": int(r.visits or 0),
                      "active_days": int(r.days or 0),
                      "last_active": str(r.last)[:10] if r.last else ""} for r in user_rows]

            # 会话/消息数（JOIN chat_session / ai_chat 聚合）
            sess_rows = (sess.query(ChatSession.user_id.label("uid"),
                                    _func.count(ChatSession.id).label("sessions"),
                                    _func.count(AIChat.id).label("messages"))
                         .outerjoin(AIChat, AIChat.session_id == ChatSession.session_id)
                         .filter(ChatSession.user_id.isnot(None))
                         .group_by(ChatSession.user_id).all())
            sess_map = {r.uid: {"sessions": int(r.sessions or 0), "messages": int(r.messages or 0)}
                        for r in sess_rows}
            for u in users:
                u.update(sess_map.get(u["user_id"], {"sessions": 0, "messages": 0}))

            # 活跃分层（近 30 天访问天数）
            seg = {"high": 0, "mid": 0, "low": 0, "churned": 0}
            for u in users:
                d = u["active_days"]
                if d >= 15:
                    seg["high"] += 1
                elif d >= 7:
                    seg["mid"] += 1
                elif d >= 1:
                    seg["low"] += 1
            # 流失 = 有账号但从未来过（30 天内 0 访问）
            total_users = sess.query(_func.count(User.id)).scalar() or 0
            seg["churned"] = max(0, int(total_users) - (seg["high"] + seg["mid"] + seg["low"]))

            return {"overview": overview, "pages": pages, "daily": daily,
                    "users": users, "segments": seg, "days": days}
        finally:
            sess.close()

    def query_chat_analytics(self, days: int = 30) -> dict:
        """对话维度分析：消息/会话趋势、深度使用（长会话）、满意度（点赞率）、活跃时段"""
        from sqlalchemy import func as _func, distinct, text as _text
        sess = self.Session()
        try:
            since = _text(f"DATE_SUB(CURDATE(), INTERVAL {int(days) - 1} DAY)")

            daily_rows = (sess.query(_func.date(AIChat.create_time).label("d"),
                                     _func.count(AIChat.id).label("messages"),
                                     _func.count(distinct(AIChat.session_id)).label("sessions"))
                          .filter(AIChat.create_time >= since)
                          .group_by("d").order_by("d").all())
            daily = [{"date": str(r.d), "messages": int(r.messages or 0),
                      "sessions": int(r.sessions or 0)} for r in daily_rows]

            total_msgs = sess.query(_func.count(AIChat.id)).filter(AIChat.create_time >= since).scalar() or 0
            total_sessions = sess.query(_func.count(distinct(AIChat.session_id))).filter(AIChat.create_time >= since).scalar() or 0
            per_session = (sess.query(AIChat.session_id.label("sid"), _func.count(AIChat.id).label("c"))
                           .filter(AIChat.create_time >= since)
                           .group_by(AIChat.session_id).all())
            long_sessions = sum(1 for r in per_session if (r.c or 0) >= 10)

            likes = sess.query(_func.count(AIChatFeedback.id)).filter(
                AIChatFeedback.liked == 1, AIChatFeedback.create_time >= since).scalar() or 0
            dislikes = sess.query(_func.count(AIChatFeedback.id)).filter(
                AIChatFeedback.disliked == 1, AIChatFeedback.create_time >= since).scalar() or 0

            hour_rows = (sess.query(_func.hour(AIChat.create_time).label("h"), _func.count(AIChat.id).label("c"))
                         .filter(AIChat.create_time >= since)
                         .group_by("h").order_by("h").all())
            hours = [{"hour": int(r.h or 0), "count": int(r.c or 0)} for r in hour_rows]

            return {
                "daily": daily,
                "overview": {
                    "messages": int(total_msgs),
                    "sessions": int(total_sessions),
                    "avg_per_session": round(int(total_msgs) / max(int(total_sessions), 1), 1),
                    "long_session_ratio": round(long_sessions / max(len(per_session), 1) * 100, 1),
                    "likes": int(likes), "dislikes": int(dislikes),
                    "like_ratio": round(int(likes) / max(int(likes) + int(dislikes), 1) * 100, 1),
                },
                "hours": hours,
                "days": days,
            }
        finally:
            sess.close()

    def query_feature_analytics(self, days: int = 30) -> dict:
        """功能维度分析：各功能数据量与近 N 天新增 + 使用用户数（渗透率）"""
        from sqlalchemy import func as _func, distinct, text as _text
        sess = self.Session()
        try:
            since = _text(f"DATE_SUB(CURDATE(), INTERVAL {int(days) - 1} DAY)")

            def counts(model, user_col="user_id", via_session=False):
                total = sess.query(_func.count(model.id)).scalar() or 0
                recent = sess.query(_func.count(model.id)).filter(model.create_time >= since).scalar() or 0
                if via_session:
                    # 无 user_id 的表（AnalysisHistory）经 chat_session 关联用户
                    recent_sids = sess.query(model.session_id).filter(
                        model.create_time >= since).subquery()
                    users = sess.query(_func.count(distinct(ChatSession.user_id))).filter(
                        ChatSession.session_id.in_(recent_sids),
                        ChatSession.user_id.isnot(None)).scalar() or 0
                else:
                    users = sess.query(_func.count(distinct(getattr(model, user_col)))).filter(
                        getattr(model, "create_time") >= since,
                        getattr(model, user_col).isnot(None)).scalar() or 0
                return {"total": int(total), "recent": int(recent), "active_users": int(users)}

            active_users = sess.query(_func.count(distinct(VisitLog.user_id))).filter(
                VisitLog.user_id > 0, VisitLog.create_time >= since).scalar() or 0

            features = {
                "planet": {"label": "知识星球（笔记）", **counts(PlanetNote)},
                "datasets": {"label": "数据集上传", **counts(Dataset)},
                "analysis": {"label": "分析大屏", **counts(AnalysisHistory, via_session=True)},
                "crawl": {"label": "数据采集记录", **counts(CrawlRecord)},
            }
            for key in features:
                f = features[key]
                f["penetration"] = round(f["active_users"] / max(int(active_users), 1) * 100, 1)
            return {"features": features, "active_users": int(active_users), "days": days}
        finally:
            sess.close()

    def query_retention_analytics(self, days: int = 90) -> dict:
        """留存维度分析：注册趋势 + 注册周留存矩阵（第1/2/3/4周回访率）

        口径：按注册周分组，注册后第 k 周内（7k,7k+7 天）有访问的用户占比。
        """
        from sqlalchemy import func as _func, text as _text
        from datetime import datetime, timedelta
        sess = self.Session()
        try:
            since = _text(f"DATE_SUB(CURDATE(), INTERVAL {int(days) - 1} DAY)")

            reg_rows = (sess.query(User.id, User.create_time)
                        .filter(User.create_time >= since).all())
            users = [(r.id, r.create_time) for r in reg_rows]
            reg_daily = {}
            for _uid, ct in users:
                d = str(ct)[:10]
                reg_daily[d] = reg_daily.get(d, 0) + 1

            visits = (sess.query(VisitLog.user_id, VisitLog.create_time)
                      .filter(VisitLog.user_id > 0).all())
            user_visits = {}
            for uid, vt in visits:
                user_visits.setdefault(uid, []).append(vt)

            matrix = []
            today = datetime.utcnow().date()
            for week_off in range(7, -1, -1):
                w_start = today - timedelta(days=today.weekday()) - timedelta(weeks=week_off)
                w_end = w_start + timedelta(days=7)
                # ct 是 datetime（TIMESTAMP 列）→ .date() 归一；w_start/w_end 是 date
                cohort = [uid for uid, ct in users if w_start <= ct.date() < w_end]
                if not cohort:
                    matrix.append({"week": w_start.strftime("%m-%d"), "registered": 0,
                                   "r1": 0, "r2": 0, "r3": 0, "r4": 0})
                    continue
                ret = {}
                for k in (1, 2, 3, 4):
                    lo = w_end + timedelta(days=7 * (k - 1))
                    hi = w_end + timedelta(days=7 * k)
                    cnt = 0
                    for uid in cohort:
                        for vt in user_visits.get(uid, []):
                            # lo/hi 是 date；vt 是 datetime（TIMESTAMP 列）→ vt.date()
                            if lo <= vt.date() < hi:
                                cnt += 1
                                break
                    ret[f"r{k}"] = round(cnt / len(cohort) * 100, 1)
                matrix.append({"week": w_start.strftime("%m-%d"), "registered": len(cohort), **ret})

            reg_trend = sorted(reg_daily.items())
            return {"daily": [{"date": d, "count": c} for d, c in reg_trend],
                    "matrix": matrix, "days": days}
        finally:
            sess.close()

    def query_cost_analytics(self, days: int = 30) -> dict:
        """成本维度分析：每模型成本 / 成本效率（每用户成本待明细拆分后补充）"""
        from sqlalchemy import func as _func, text as _text
        from yuanai_core.usage import model_cost
        sess = self.Session()
        try:
            since = _text(f"DATE_SUB(CURDATE(), INTERVAL {int(days) - 1} DAY)")

            model_rows = (sess.query(TokenUsage.model.label("m"),
                                     _func.sum(TokenUsage.prompt_tokens).label("p"),
                                     _func.sum(TokenUsage.completion_tokens).label("c"),
                                     _func.count(TokenUsage.id).label("n"))
                          .filter(TokenUsage.create_time >= since)
                          .group_by(TokenUsage.model).all())
            models = []
            total_cost = 0.0
            for r in model_rows:
                cost = model_cost(r.m, int(r.p or 0), int(r.c or 0))
                total_cost += cost
                models.append({"model": r.m, "prompt_tokens": int(r.p or 0),
                               "completion_tokens": int(r.c or 0), "calls": int(r.n or 0),
                               "cost": round(cost, 2)})
            models.sort(key=lambda x: -x["cost"])

            msgs = sess.query(_func.count(AIChat.id)).filter(AIChat.create_time >= since).scalar() or 0
            return {"models": models,
                    "overview": {"total_cost": round(total_cost, 2),
                                 "cost_per_message": round(total_cost / max(int(msgs), 1), 6),
                                 "messages": int(msgs)},
                    "days": days}
        finally:
            sess.close()

    def add_token_usage_rows(self, rows: list) -> None:
        """批量落库用量记录（usage.py 缓冲冲刷用；失败整批回滚）"""
        sess = self.Session()
        try:
            for r in rows:
                sess.add(TokenUsage(
                    user_id=r.get("user_id") or 0,
                    model=(r.get("model") or "")[:64],
                    purpose=(r.get("purpose") or "chat")[:32],
                    prompt_tokens=r.get("prompt_tokens") or 0,
                    completion_tokens=r.get("completion_tokens") or 0,
                    total_tokens=r.get("total_tokens") or 0,
                    source=(r.get("source") or "cloud")[:16],
                ))
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def query_token_usage(self, days: int = 7, group_by: str = "day",
                          user_id: int = None) -> list:
        """聚合用量：group_by = day / model / user（近 N 天）"""
        from sqlalchemy import func as _func
        sess = self.Session()
        try:
            q = sess.query(TokenUsage)
            if user_id is not None:
                q = q.filter(TokenUsage.user_id == user_id)
            if group_by == "model":
                key = TokenUsage.model
            elif group_by == "user":
                key = TokenUsage.user_id
            else:  # day
                key = _func.date(TokenUsage.create_time)
            rows = (q.with_entities(
                key.label("k"),
                _func.sum(TokenUsage.total_tokens).label("total"),
                _func.sum(TokenUsage.prompt_tokens).label("prompt"),
                _func.sum(TokenUsage.completion_tokens).label("completion"),
                _func.count(TokenUsage.id).label("calls"))
                .group_by(key)
                .order_by(key.desc() if group_by == "day" else None)
                .limit(60).all())
            return [{"key": str(r.k), "total_tokens": int(r.total or 0),
                     "prompt_tokens": int(r.prompt or 0),
                     "completion_tokens": int(r.completion or 0),
                     "calls": int(r.calls or 0)} for r in rows]
        finally:
            sess.close()

_db_instance = None



def get_db():
    """获取 MySQL 数据库实例（单例）"""
    global _db_instance
    if _db_instance is None:
        _db_instance = AgentDatabase()
    return _db_instance


# ---------------------- 测试代码 ----------------------
if __name__ == '__main__':
    db = AgentDatabase()
    print("AgentDatabase initialized OK")


