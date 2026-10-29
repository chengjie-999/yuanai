"""
迁移文件健全性测试（2026-10-30 生产事故防回归）

事故：0020 迁移重写时漏写 revision 块——alembic 报「Could not determine
revision id」，叠加 create_all 兜底先建表 → 升级撞「Table already exists」
容器崩溃循环、全站 502。此测试锁死：每个迁移文件必须可导入且声明
revision/down_revision（链完整性由 alembic upgrade 运行时保证）。
"""
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

VERSIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'db', 'migrations', 'versions')


def _load_migration(path: str):
    spec = importlib.util.spec_from_file_location('_mig_check', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_all_migrations_declare_revision():
    files = sorted(f for f in os.listdir(VERSIONS_DIR) if f.endswith('.py') and not f.startswith('_'))
    assert files, "迁移目录为空"
    revisions = set()
    for f in files:
        mod = _load_migration(os.path.join(VERSIONS_DIR, f))
        assert getattr(mod, 'revision', None), f"{f} 缺少 revision 声明"
        # down_revision 允许 None（仅根迁移，数量唯一性由链测试保证）
        assert hasattr(mod, 'down_revision'), f"{f} 缺少 down_revision 声明"
        revisions.add(mod.revision)
    # 版本号唯一
    assert len(revisions) == len(files), "revision 重复"


def test_migration_chain_connected():
    """除根迁移外，每个 down_revision 都必须能找到对应迁移"""
    files = sorted(f for f in os.listdir(VERSIONS_DIR) if f.endswith('.py') and not f.startswith('_'))
    mods = {}
    roots = []
    for f in files:
        m = _load_migration(os.path.join(VERSIONS_DIR, f))
        mods[m.revision] = m
        if m.down_revision is None:
            roots.append(m.revision)
    assert len(roots) == 1, f"根迁移数量异常: {roots}"
    for rev, m in mods.items():
        if m.down_revision is None:
            continue
        assert m.down_revision in mods, f"{rev} 的 down_revision({m.down_revision}) 不存在"
