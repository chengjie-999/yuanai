"""冻结模式 settings 导入回归（2026-11-06 exe 启动崩溃修复）

事故：config/settings.py 把 .jwt_secret 写在 __file__ 旁——exe 冻结模式下
__file__ 在 _MEI 临时解包目录，config/ 不是真实文件夹，write_text 抛
FileNotFoundError，tray 启动即崩。修复后秘密落数据根（%LOCALAPPDATA%\
XiaoYuanAI\.jwt_secret）。子进程模拟 sys.frozen=True 断言导入不崩。"""

import os
import subprocess
import sys
import tempfile

import pytest


def _run_frozen_import(env_extra=None) -> subprocess.CompletedProcess:
    local = tempfile.mkdtemp(prefix="yuan_frozen_")
    env = dict(os.environ)
    env["LOCALAPPDATA"] = local
    env.pop("JWT_SECRET_KEY", None)
    if env_extra:
        env.update(env_extra)
    code = (
        "import sys; sys.frozen = True\n"
        "import config.settings as s\n"
        "import os\n"
        "p = os.path.join(os.environ['LOCALAPPDATA'], 'XiaoYuanAI', '.jwt_secret')\n"
        "assert os.path.isfile(p), p\n"
        "assert len(s.JWT_SECRET_KEY) == 64\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env,
        timeout=120,
    )


def test_frozen_import_writes_secret_to_data_root():
    """冻结模拟：导入不崩，秘密落在数据根（而非 _MEI 临时目录）"""
    r = _run_frozen_import()
    assert r.returncode == 0, f"stderr:\n{r.stderr}"


def test_frozen_import_reuses_existing_secret():
    """第二次导入读回同一秘密（重启后 token 不失效）"""
    local = tempfile.mkdtemp(prefix="yuan_frozen_")
    secret_path = os.path.join(local, "XiaoYuanAI", ".jwt_secret")
    os.makedirs(os.path.dirname(secret_path))
    with open(secret_path, "w", encoding="utf-8") as f:
        f.write("a" * 64)
    env = dict(os.environ)
    env["LOCALAPPDATA"] = local
    env.pop("JWT_SECRET_KEY", None)
    code = (
        "import sys; sys.frozen = True\n"
        "import config.settings as s\n"
        "assert s.JWT_SECRET_KEY == 'a' * 64\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env,
        timeout=120,
    )
    assert r.returncode == 0, f"stderr:\n{r.stderr}"
