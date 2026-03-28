from sqlalchemy import create_engine, Column, Integer, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import json
from utils.data_path import root_path

# ---------------------- SQLAlchemy 基础配置 ----------------------
Base = declarative_base()


# ---------------------- 数据库模型定义（对应原表结构） ----------------------
class StreamlitState(Base):
    """状态表模型"""
    __tablename__ = 'streamlit_state'
    key = Column(Text, primary_key=True)
    value = Column(Text)


class AIChat(Base):
    """AI 聊天记录表模型"""
    __tablename__ = 'ai_chat'
    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    create_time = Column(TIMESTAMP, server_default='CURRENT_TIMESTAMP')


# ---------------------- 数据库操作类（功能完全对齐原代码） ----------------------
class AgentDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(root_path(), "agent.db")
        self.db_path = db_path

        # 1. 创建 SQLAlchemy 引擎
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        # 2. 创建会话工厂
        self.Session = sessionmaker(bind=self.engine)
        # 3. 自动建表
        self._init_tables()

    def _init_tables(self):
        """自动创建所有表（如果不存在）"""
        Base.metadata.create_all(self.engine)

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

    # --------------------------------------------------------------------------
    # 聊天记录操作（原有功能保留）
    # --------------------------------------------------------------------------
    def add_chat(self, role, content):
        """添加一条聊天记录"""
        session = self.Session()
        try:
            chat = AIChat(role=role, content=content)
            session.add(chat)
            session.commit()
        finally:
            session.close()

    def get_all_chats(self):
        """获取所有聊天记录（按时间排序）"""
        session = self.Session()
        try:
            chats = session.query(AIChat).order_by(AIChat.id).all()
            return [{"role": chat.role, "content": chat.content} for chat in chats]
        finally:
            session.close()

    def clear_chats(self):
        """清空所有聊天记录"""
        session = self.Session()
        try:
            session.query(AIChat).delete()
            session.commit()
        finally:
            session.close()


# ---------------------- 测试代码（与原代码完全一致） ----------------------
if __name__ == '__main__':
    db = AgentDatabase()

    # 状态示例
    db.set_state("page", "chat")
    page = db.get_state("page")
    print("page state:", page)

    all_states = db.get_all_states()
    print("all states:", all_states)

    print("exists 'page'?", db.exists_state("page"))
    db.delete_state("page")
    print("exists 'page' after delete?", db.exists_state("page"))

    # 聊天示例
    db.add_chat("user", "你好")
    history = db.get_all_chats()
    print("chat history:", history)
    db.clear_chats()