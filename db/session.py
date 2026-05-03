from sqlalchemy import create_engine, Column, Integer, Text, TIMESTAMP, String
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
    key = Column(Text, primary_key=True)
    value = Column(Text)


class ChatSession(Base):
    """会话表"""
    __tablename__ = 'chat_session'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
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
            ChatSession.__table__.create(self.engine, checkfirst=True)
            AIChat.__table__.create(self.engine, checkfirst=True)
        else:
            if db_path is None:
                db_path = os.path.join(root_path(), "agent.db")
            self.db_path = db_path
            self.engine = create_engine(f'sqlite:///{self.db_path}')
            Base.metadata.create_all(self.engine)
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
    def create_session(self, title: str = "新对话", model: str = "doubao-seed-2-0-pro-260215") -> dict:
        """创建新会话"""
        session = self.Session()
        try:
            sid = str(uuid.uuid4())
            cs = ChatSession(session_id=sid, title=title, model=model)
            session.add(cs)
            session.commit()
            return {"session_id": sid, "title": title, "model": model}
        finally:
            session.close()

    def get_sessions(self, limit: int = 50) -> list:
        """获取会话列表（按更新时间倒序）"""
        session = self.Session()
        try:
            q = session.query(ChatSession).order_by(ChatSession.update_time.desc()).limit(limit).all()
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


# ---------------------- 测试代码（与原代码完全一致） ----------------------
if __name__ == '__main__':
    db = AgentDatabase()

    db.set_state("test_key", {"foo": "bar"})
    db.delete_state("user")
    print(db.get_all_states())
