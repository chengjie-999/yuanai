# -*- coding: utf-8 -*-
"""用户认证测试（使用 SQLite 内存数据库）"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.session import Base, AgentDatabase


def _make_test_db():
    """创建使用 SQLite 内存数据库的 AgentDatabase 实例"""
    db = AgentDatabase.__new__(AgentDatabase)
    db.engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db.engine)
    db._run_alembic_migrations = lambda: None
    db.Session = sessionmaker(bind=db.engine)
    return db


def test_register_and_login():
    db = _make_test_db()
    r = db.register_user('testuser', 'test123')
    assert 'error' not in r
    assert r['username'] == 'testuser'
    assert r['role'] == 'user'
    print('[OK] register')

    r2 = db.register_user('testuser', 'test123')
    assert 'error' in r2
    print('[OK] duplicate register rejected')

    user = db.authenticate_user('testuser', 'test123')
    assert user is not None
    assert user.username == 'testuser'
    print('[OK] login')

    user2 = db.authenticate_user('testuser', 'wrongpass')
    assert user2 is None
    print('[OK] wrong password rejected')

    user3 = db.authenticate_user('nobody', 'test123')
    assert user3 is None
    print('[OK] nonexistent user rejected')


def test_admin_registration():
    db = _make_test_db()
    r = db.register_user('admin1', 'admin123', role='admin')
    assert r['role'] == 'admin'
    user = db.authenticate_user('admin1', 'admin123')
    assert user.role == 'admin'
    print('[OK] admin registration')


if __name__ == '__main__':
    test_register_and_login()
    test_admin_registration()
    print('\nAll tests passed')
