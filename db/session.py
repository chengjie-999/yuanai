import os
import sqlite3
import json
from utils.data_path import root_path


class AgentDatabase:
    def __init__(self, db_path=None):
        # 不传路径则默认使用 agent.db
        if db_path is None:
            db_path = os.path.join(root_path(), "agent.db")
        self.db_path = db_path
        self._init_tables()  # 自动建表

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_tables(self):
        conn = self._get_connection()
        c = conn.cursor()

        # 状态表
        c.execute('''
        CREATE TABLE IF NOT EXISTS streamlit_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        # AI 聊天表
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        conn.commit()
        conn.close()

    # --------------------------------------------------------------------------
    # 状态操作（增删改查）
    # --------------------------------------------------------------------------
    def set_state(self, key, value):
        """创建或更新状态（增/改）"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('''
            REPLACE INTO streamlit_state (key, value)
            VALUES (?, ?)
        ''', (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
        conn.close()

    def get_state(self, key, default=None):
        """获取指定状态值（查单条）"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('SELECT value FROM streamlit_state WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return default

    def delete_state(self, key):
        """删除指定状态（删）"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('DELETE FROM streamlit_state WHERE key = ?', (key,))
        conn.commit()
        conn.close()

    def get_all_states(self):
        """获取所有状态键值对（查全部）"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('SELECT key, value FROM streamlit_state')
        rows = c.fetchall()
        conn.close()
        return {key: json.loads(value) for key, value in rows}

    def clear_all_states(self):
        """清除所有状态（批量删）"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('DELETE FROM streamlit_state')
        conn.commit()
        conn.close()

    def exists_state(self, key):
        """检查状态是否存在（辅助查询）"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('SELECT 1 FROM streamlit_state WHERE key = ?', (key,))
        exists = c.fetchone() is not None
        conn.close()
        return exists

    # --------------------------------------------------------------------------
    # 聊天记录操作（原有功能保留）
    # --------------------------------------------------------------------------
    def add_chat(self, role, content):
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO ai_chat (role, content)
            VALUES (?, ?)
        ''', (role, content))
        conn.commit()
        conn.close()

    def get_all_chats(self):
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT role, content
            FROM ai_chat
            ORDER BY id ASC
        ''')
        rows = c.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in rows]

    def clear_chats(self):
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('DELETE FROM ai_chat')
        conn.commit()
        conn.close()


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