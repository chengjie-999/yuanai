import os.path
import sqlite3
import datetime
from typing import List, Dict, Any

from utils.data_path import root_path


class AgentDB:
    """智能体会话数据数据库管理类"""

    def __init__(self, db_path: str = os.path.join(root_path(), "agent.db")):
        """
        初始化数据库连接
        :param db_path: 数据库文件路径
        """
        self.db_path = db_path
        # 初始化数据库表
        self._init_tables()

    def _init_tables(self):
        """创建会话数据表（如果不存在）"""
        conn = None
        try:
            # 连接数据库（不存在则自动创建）
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建会话表：存储会话基础信息
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,  -- 会话唯一ID
                    agent_id TEXT NOT NULL,             -- 智能体ID
                    user_id TEXT NOT NULL,              -- 用户ID
                    create_time TIMESTAMP NOT NULL,     -- 会话创建时间
                    update_time TIMESTAMP NOT NULL,     -- 会话更新时间
                    status INTEGER DEFAULT 1            -- 会话状态：1-活跃 0-结束
                )
            ''')

            # 创建消息表：存储会话中的具体消息
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 消息自增ID
                    conversation_id TEXT NOT NULL,                 -- 关联的会话ID
                    sender_type TEXT NOT NULL,                     -- 发送者类型：user/agent
                    content TEXT NOT NULL,                         -- 消息内容
                    send_time TIMESTAMP NOT NULL,                  -- 消息发送时间
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                )
            ''')

            conn.commit()
        except sqlite3.Error as e:
            print(f"初始化数据库表失败: {e}")
        finally:
            if conn:
                conn.close()

    def create_conversation(self, conversation_id: str, agent_id: str, user_id: str) -> bool:
        """
        创建新会话
        :param conversation_id: 会话ID（建议用UUID生成）
        :param agent_id: 智能体ID
        :param user_id: 用户ID
        :return: 是否创建成功
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.datetime.now()

            cursor.execute('''
                INSERT INTO conversations 
                (conversation_id, agent_id, user_id, create_time, update_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, agent_id, user_id, now, now))

            conn.commit()
            return True
        except sqlite3.IntegrityError:
            print(f"会话ID {conversation_id} 已存在")
            return False
        except sqlite3.Error as e:
            print(f"创建会话失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def add_message(self, conversation_id: str, sender_type: str, content: str) -> bool:
        """
        添加消息到会话
        :param conversation_id: 会话ID
        :param sender_type: 发送者类型（user/agent）
        :param content: 消息内容
        :return: 是否添加成功
        """
        if sender_type not in ["user", "agent"]:
            print("发送者类型只能是 user 或 agent")
            return False

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.datetime.now()

            # 插入消息
            cursor.execute('''
                INSERT INTO messages 
                (conversation_id, sender_type, content, send_time)
                VALUES (?, ?, ?, ?)
            ''', (conversation_id, sender_type, content, now))

            # 更新会话的更新时间
            cursor.execute('''
                UPDATE conversations 
                SET update_time = ? 
                WHERE conversation_id = ?
            ''', (now, conversation_id))

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"添加消息失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        获取指定会话的所有消息
        :param conversation_id: 会话ID
        :return: 消息列表（按发送时间排序）
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            # 设置返回结果为字典格式（方便使用）
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT message_id, conversation_id, sender_type, content, send_time
                FROM messages 
                WHERE conversation_id = ?
                ORDER BY send_time ASC
            ''', (conversation_id,))

            # 将查询结果转为字典列表
            messages = [dict(row) for row in cursor.fetchall()]
            return messages
        except sqlite3.Error as e:
            print(f"获取会话消息失败: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def close_conversation(self, conversation_id: str) -> bool:
        """
        结束指定会话
        :param conversation_id: 会话ID
        :return: 是否操作成功
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE conversations 
                SET status = 0, update_time = ? 
                WHERE conversation_id = ?
            ''', (datetime.datetime.now(), conversation_id))

            conn.commit()
            return cursor.rowcount > 0  # 检查是否有行被更新
        except sqlite3.Error as e:
            print(f"结束会话失败: {e}")
            return False
        finally:
            if conn:
                conn.close()


# ------------------- 测试使用示例 -------------------
if __name__ == "__main__":
    # 初始化数据库
    db = AgentDB()

    # 1. 创建新会话（建议用UUID作为conversation_id，这里简化为固定值）
    conv_id = "conv_001"
    db.create_conversation(
        conversation_id=conv_id,
        agent_id="agent_chat_01",
        user_id="user_123456"
    )

    # 2. 添加用户消息
    db.add_message(conv_id, "user", "你好，我想查询今天的天气")

    # 3. 添加智能体回复
    db.add_message(conv_id, "agent", "你好！今天的天气是晴转多云，温度18-25℃。")

    # 4. 再添加一条用户消息
    db.add_message(conv_id, "user", "谢谢，那明天呢？")

    # 5. 获取并打印会话所有消息
    messages = db.get_conversation_messages(conv_id)
    print("=== 会话消息列表 ===")
    for msg in messages:
        print(f"[{msg['send_time']}] {msg['sender_type']}: {msg['content']}")

    # 6. 结束会话
    db.close_conversation(conv_id)
    print("\n会话已结束")