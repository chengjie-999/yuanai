import logging
from sqlalchemy import create_engine, Column, Integer, Text, TIMESTAMP, String, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from sqlalchemy.sql import func
import os
import json
import uuid
from utils.data_path import root_path

logger = logging.getLogger(__name__)

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
    images = Column(Text, nullable=True)
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
    frozen_until = Column(TIMESTAMP, nullable=True)
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


# ---------------------- 数据库操作类（功能完全对齐原代码） ----------------------
class AgentDatabase:
    def __init__(self, db_path=None, use_mysql=False, mysql_config: dict = None):
        self.db_path = db_path
        if use_mysql:
            cfg = mysql_config or {}
            logger.info("连接 MySQL: %s:%s/%s", cfg.get('host', 'localhost'), cfg.get('port', 3306), cfg.get('database', 'ai_agent'))
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
                    logger.info("迁移: chat_session 表添加了 user_id 列")
            except Exception:
                logger.debug("迁移: user_id 列可能已存在")
            # 迁移：将 NULL 的用户会话归到 admin
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("UPDATE chat_session SET user_id = 1 WHERE user_id IS NULL"))
                    conn.commit()
            except Exception:
                logger.debug("迁移: 修复 NULL user_id 跳过")
            # 迁移：添加 frozen_until 列
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN frozen_until DATETIME"))
                    conn.commit()
            except Exception:
                logger.debug("迁移: frozen_until 列可能已存在")
            # 迁移：添加 parsed 列
            for col in ["parsed_title VARCHAR(500) DEFAULT ''", "parsed_text TEXT", "parsed_links TEXT"]:
                try:
                    with self.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE crawl_records ADD COLUMN {col}"))
                        conn.commit()
                except Exception:
                    logger.debug("迁移: %s 列可能已存在", col.split()[0])
            # 迁移：添加 images 列
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE ai_chat ADD COLUMN images TEXT"))
                    conn.commit()
                    logger.info("迁移: ai_chat 表添加了 images 列")
            except Exception:
                logger.debug("迁移: images 列可能已存在")
        else:
            if db_path is None:
                db_path = os.path.join(root_path(), "agent.db")
            self.db_path = db_path
            self.engine = create_engine(
                f'sqlite:///{self.db_path}',
                connect_args={"check_same_thread": False}
            )
            Base.metadata.create_all(self.engine)
            # 迁移：添加 user_id 列（兼容旧数据库）
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE chat_session ADD COLUMN user_id INTEGER"))
                    conn.commit()
                    logger.info("迁移: chat_session 表添加了 user_id 列")
            except Exception:
                logger.debug("迁移: user_id 列可能已存在")
            # 迁移：添加 images 列
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE ai_chat ADD COLUMN images TEXT"))
                    conn.commit()
                    logger.info("迁移: ai_chat 表添加了 images 列")
            except Exception:
                logger.debug("迁移: images 列可能已存在")
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
