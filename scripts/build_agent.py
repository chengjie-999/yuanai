# -*- coding: utf-8 -*-
"""一键打包 Agent 安装包（2026-10-30 统一命名规范）

统一产物命名 = `yuanai-agent-v{version}.exe`（与服务器版本库存放规范一致，
上传时后台版本号直接填 version 即可，本地产物与线上清单同名可对照）。

用法：
    python scripts/build_agent.py 20261030          # 指定版本号
    python scripts/build_agent.py                   # 留空自动用日期 YYYYMMDD

流程：版本号写入 agent/tray.py 的 AGENT_VERSION（打包后还原）→ PyInstaller
按 agent/yuanai_agent.spec 打包 → 产物重命名为 yuanai-agent-v{version}.exe 放
dist/versions/ → 计算 sha256 打印（上传后可与后台清单核对；发布顺序纪律：
先后端上传含 hash → 再发布）。
"""
import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAY = os.path.join(ROOT, "agent", "tray.py")
SPEC = os.path.join(ROOT, "agent", "yuanai_agent.spec")
OUT_DIR = os.path.join(ROOT, "dist", "versions")


def _set_agent_version(version: str) -> str | None:
    """把版本号写入 tray.py 的 AGENT_VERSION，返回原文（用于打包后还原）"""
    with open(TRAY, "r", encoding="utf-8") as f:
        src = f.read()
    m = re.search(r'^(AGENT_VERSION = )".*?"', src, re.M)
    if not m:
        print("未找到 AGENT_VERSION 定义，跳过注入")
        return None
    new_src = src[:m.start(1)] + f'{m.group(1)}"{version}"' + src[m.end():]
    with open(TRAY, "w", encoding="utf-8") as f:
        f.write(new_src)
    return src


def main() -> int:
    version = (sys.argv[1] if len(sys.argv) > 1 else "").strip() \
        or datetime.now().strftime("%Y%m%d")
    if not re.match(r"^[A-Za-z0-9._-]{1,32}$", version):
        print("版本号仅限字母/数字/._-（≤32 字符）")
        return 1

    original = _set_agent_version(version)
    try:
        print(f"== 打包 v{version}（PyInstaller）==")
        ret = subprocess.call(
            [sys.executable, "-m", "PyInstaller", SPEC, "--noconfirm", "--clean"],
            cwd=ROOT)
        if ret != 0:
            print("PyInstaller 打包失败")
            return 1
    finally:
        if original is not None:
            with open(TRAY, "w", encoding="utf-8") as f:
                f.write(original)
            print("tray.py 版本号已还原")

    built = os.path.join(ROOT, "dist", "yuanai-agent.exe")
    if not os.path.isfile(built):
        print(f"未找到打包产物: {built}")
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)
    final_name = f"yuanai-agent-v{version}.exe"
    final_path = os.path.join(OUT_DIR, final_name)
    os.replace(built, final_path)

    sha = hashlib.sha256()
    with open(final_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
    size = os.path.getsize(final_path)
    print(f"== 完成 ==\n产物: {final_path}\n大小: {size / 1024 / 1024:.0f}MB\n"
          f"sha256: {sha.hexdigest()}")
    print("上传：后台「Agent 管理 → 发布新版本」填版本号 " + version +
          " 并拖入该文件；上传后对照后台清单 sha256。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
