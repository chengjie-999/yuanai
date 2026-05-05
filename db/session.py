from sqlalchemy import create_engine, Column, Integer, Text, TIMESTAMP, String, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from sqlalchemy.sql import func
import os
import json
import uuid
from utils.data_path import root_path

# ---------------------- SQLAlchemy 基础配置 ----------------------
Base = declarative_base()


# ---------------------- 数据库模型定义（对应原表结构） ----------------------
class StreamlitState(Base):
    """状态表模型"""
    __tablename__ = 'streamlit_state'
    key = Column(String(200), primary_key=True)
    value = Column(Text)


class ChatSession(Base):
    """会话表"""
    __tablename__ = 'chat_session'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    title = Column(String(200), default='新对话')
    model = Column(String(50), default='doubao-seed-2-0-pro-260215')
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class AIChat(Base):
    """AI 聊天记录表模型"""
    __tablename__ = 'ai_chat'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    create_time = Column(TIMESTAMP, server_default=func.now())


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


class User(Base):
    """用户表"""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    display_name = Column(String(50), default='')
    role = Column(String(20), default='user')
    create_time = Column(TIMESTAMP, server_default=func.now())


# ---------------------- 数据库操作类（功能完全对齐原代码） ----------------------
class AgentDatabase:
    def __init__(self, db_path=None, use_mysql=False, mysql_config: dict = None):
        self.db_path = db_path
        if use_mysql:
            cfg = mysql_config or {}
            conn_url = URL.create(
                "mysql+pymysql",
                username=cfg.get("user", "root"),
                password=cfg.get("password", ""),
                host=cfg.get("host", "localhost"),
                port=cfg.get("port", 3306),
                database=cfg.get("database", "ai_agent"),
            )
            self.engine = create_engine(conn_url, pool_size=5, max_overflow=10)
            Base.metadata.create_all(self.engine)
            # 迁移：添加 user_id 列（兼容旧数据库）
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE chat_session ADD COLUMN user_id INTEGER"))
                    conn.commit()
                    print("📦 迁移: chat_session 表添加了 user_id 列")
            except Exception:
                pass
            # 迁移：将 NULL 的用户会话归到 admin
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("UPDATE chat_session SET user_id = 1 WHERE user_id IS NULL"))
                    conn.commit()
            except Exception:
                pass
        else:
            if db_path is None:
                db_path = os.path.join(root_path(), "agent.db")
            self.db_path = db_path
            self.engine = create_engine(f'sqlite:///{self.db_path}')
            Base.metadata.create_all(self.engine)
            # 迁移：添加 user_id 列（兼容旧数据库）
            try:
                from sqlalchemy import text
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE chat_session ADD COLUMN user_id INTEGER"))
                    conn.commit()
                    print("📦 迁移: chat_session 表添加了 user_id 列")
            except Exception:
                pass
        self.Session = sessionmaker(bind=self.engine)

    def _init_tables(self):
        """自动创建表：SQLite 全表创建，MySQL 只建聊天相关表"""
        pass

    # --------------------------------------------------------------------------
    # 状态操作（增删改查）
    # --------------------------------------------------------------------------
    def set_state(self, key, value):
        """创建或更新状态（增/改）"""
        session = self.Session()
        try:
            # 先查询是否存在，存在则更新，不存在则插入
            state = session.query(StreamlitState).filter_by(key=key).first()
            if state:
                state.value = json.dumps(value, ensure_ascii=False)
            else:
                state = StreamlitState(key=key, value=json.dumps(value, ensure_ascii=False))
                session.add(state)
            session.commit()
        finally:
            session.close()

    def get_state(self, key, default=None):
        """获取指定状态值（查单条）"""
        session = self.Session()
        try:
            state = session.query(StreamlitState).filter_by(key=key).first()
            if state:
                return json.loads(state.value)
            return default
        finally:
            session.close()

    def delete_state(self, key):
        """删除指定状态（删）"""
        session = self.Session()
        try:
            session.query(StreamlitState).filter_by(key=key).delete()
            session.commit()
        finally:
            session.close()

    def get_all_states(self):
        """获取所有状态键值对（查全部）"""
        session = self.Session()
        try:
            states = session.query(StreamlitState).all()
            return {state.key: json.loads(state.value) for state in states}
        finally:
            session.close()

    def clear_all_states(self):
        """清除所有状态（批量删）"""
        session = self.Session()
        try:
            session.query(StreamlitState).delete()
            session.commit()
        finally:
            session.close()

    def exists_state(self, key):
        """检查状态是否存在（辅助查询）"""
        session = self.Session()
        try:
            return session.query(StreamlitState).filter_by(key=key).first() is not None
        finally:
            session.close()

    def update_states_from_df(self, df):
        """
        通过 pandas DataFrame 批量更新或插入状态。
        df 必须包含 'key' 和 'value' 两列。
        若 key 已存在，则更新其 value；否则插入新记录。
        如果 value 无法 JSON 序列化，则跳过该行并给出提示。
        """
        session = self.Session()
        skipped = []
        try:
            # 验证 DataFrame 必须包含所需列
            if 'key' not in df.columns or 'value' not in df.columns:
                raise ValueError("DataFrame 必须包含 'key' 和 'value' 列")

            # 遍历每一行，使用 session.merge 进行 upsert
            for _, row in df.iterrows():
                key = row['key']
                value = row['value']
                try:
                    # 尝试序列化 value，若失败则跳过
                    value_json = json.dumps(value, ensure_ascii=False)
                    state = StreamlitState(key=key, value=value_json)
                    session.merge(state)
                except (TypeError, ValueError) as e:
                    # 记录跳过的记录
                    skipped.append((key, value))
                    print(f"⚠️ 跳过无法序列化的记录: key='{key}', value={value!r}, 错误: {e}")
            session.commit()
            if skipped:
                print(f"📊 共跳过 {len(skipped)} 条无法序列化的记录")
        finally:
            session.close()

    # --------------------------------------------------------------------------
    # 会话操作
    # --------------------------------------------------------------------------
    def create_session(self, title: str = "新对话", model: str = "doubao-seed-2-0-pro-260215", user_id: int = None) -> dict:
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
        """获取会话列表（按创建时间倒序）"""
        session = self.Session()
        try:
            q = session.query(ChatSession)
            if user_id is not None:
                q = q.filter(ChatSession.user_id == user_id)
            q = q.order_by(ChatSession.create_time.desc()).limit(limit).all()
            return [{"session_id": s.session_id, "title": s.title, "model": s.model,
                     "create_time": str(s.create_time), "update_time": str(s.update_time)} for s in q]
        finally:
            session.close()

    def delete_session(self, session_id: str):
        """删除会话及其所有消息"""
        sess = self.Session()
        try:
            sess.query(AIChat).filter_by(session_id=session_id).delete()
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
            return [{"role": c.role, "content": c.content, "create_time": str(c.create_time)} for c in chats]
        finally:
            session.close()

    def clear_chats(self):
        """清空所有聊天记录"""
        session = self.Session()
        try:
            session.query(AIChat).delete()
            session.query(ChatSession).delete()
            session.commit()
        finally:
            session.close()

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
        """验证用户登录，成功返回 user 对象，失败返回 None"""
        import bcrypt as _bcrypt
        sess = self.Session()
        try:
            user = sess.query(User).filter_by(username=username).first()
            if user and _bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                return user
            return None
        finally:
            sess.close()

    def get_user_by_id(self, user_id: int):
        """根据 ID 获取用户"""
        sess = self.Session()
        try:
            return sess.query(User).filter_by(id=user_id).first()
        finally:
            sess.close()


def get_db():
    """获取 MySQL 数据库实例（带配置）"""
    from utils.sensitive_data import get_mysql_config
    return AgentDatabase(use_mysql=True, mysql_config=get_mysql_config())


# ---------------------- 测试代码 ----------------------
if __name__ == '__main__':
    db = AgentDatabase()

    db.set_state("test_key", {"foo": "bar"})
    db.delete_state("user")
    print(db.get_all_states())
