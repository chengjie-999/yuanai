"""
数据库迁移辅助命令

用法：
  python -m db.migrations.helper revision -m "添加xxx字段"   # 自动生成迁移
  python -m db.migrations.helper upgrade                       # 升级到最新
  python -m db.migrations.helper downgrade -1                  # 回滚一个版本
  python -m db.migrations.helper history                       # 查看历史
  python -m db.migrations.helper current                       # 当前版本
"""

import os
import sys

# 确保项目根在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from alembic.config import Config
from alembic import command


def main():
    alembic_ini = os.path.join(os.path.dirname(__file__), '..', '..', 'alembic.ini')
    if not os.path.exists(alembic_ini):
        print(f"错误：找不到 {alembic_ini}")
        sys.exit(1)

    cfg = Config(alembic_ini)

    # 将当前工作目录改为项目根
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.chdir(project_root)

    # 解析参数
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    action = args[0]
    extra = args[1:]

    if action == 'revision':
        msg = extra[0] if extra else 'auto'
        command.revision(cfg, autogenerate=True, message=msg)
        print(f"✅ 迁移文件已生成到 db/migrations/versions/")
    elif action == 'upgrade':
        rev = extra[0] if extra else 'head'
        command.upgrade(cfg, rev)
        print(f"✅ 已升级到 {rev}")
    elif action == 'downgrade':
        rev = extra[0] if extra else '-1'
        command.downgrade(cfg, rev)
        print(f"✅ 已回滚 {rev}")
    elif action == 'history':
        command.history(cfg)
    elif action == 'current':
        command.current(cfg)
    elif action == 'stamp':
        rev = extra[0] if extra else 'head'
        command.stamp(cfg, rev)
        print(f"✅ 已标记为 {rev}")
    else:
        print(f"未知命令: {action}")
        sys.exit(1)


if __name__ == '__main__':
    main()
