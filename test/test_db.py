# -*- coding: utf-8 -*-
"""数据库 CRUD 测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from db.session import AgentDatabase


def test_session_crud():
    db = AgentDatabase(db_path=':memory:')
    r = db.create_session('Test Session', user_id=1)
    assert 'session_id' in r
    sid = r['session_id']
    print('[OK] create_session')

    sessions = db.get_sessions(user_id=1)
    assert len(sessions) >= 1
    print('[OK] list sessions')

    sessions2 = db.get_sessions(user_id=999)
    assert len(sessions2) == 0
    print('[OK] user isolation')

    db.add_chat(sid, 'user', 'hello')
    db.add_chat(sid, 'assistant', 'hi')
    print('[OK] add messages')

    chats = db.get_chats(sid)
    assert len(chats) == 2
    assert chats[0]['role'] == 'user'
    assert chats[1]['role'] == 'assistant'
    print('[OK] get chats')

    db.delete_session(sid)
    chats2 = db.get_chats(sid)
    assert len(chats2) == 0
    print('[OK] delete session')


def test_task_image():
    db = AgentDatabase(db_path=':memory:')
    r = db.save_task_images('test-sid', 'Test Task', 'http://example.com', '/tmp/test', 2, [{"index": 0, "type": "screenshot"}])
    assert 'id' in r
    print('[OK] save_task_images')


if __name__ == '__main__':
    test_session_crud()
    test_task_image()
    print('\nAll tests passed')
