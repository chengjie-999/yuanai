# -*- coding: utf-8 -*-
"""本地联调种子脚本（2026-10-30）：给本地版本库造演示版本，方便测试下载卡。

本地后端从未上传过版本 → /chat/agent 下载卡显示「暂无可用版本」无法联调。
本脚本生成一个小占位 exe 并按真实 sha256 写入本地 versions.json（与后台上传
同链路：_load_versions/_save_versions/_sync_version_json），刷新 Agent 页即见。

用法：
    python scripts/seed_local_agent_version.py              # 版本号自动 20990101-演示
    python scripts/seed_local_agent_version.py 20261030     # 指定版本号
生产环境请勿运行（演示版本会进生产清单）。
"""
import hashlib
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    version = (sys.argv[1] if len(sys.argv) > 1 else "").strip() \
        or datetime.now().strftime("%Y%m%d") + "-demo"
    from api.v1.admin.agent_devices import (_load_versions, _save_versions,
                                            _sync_version_json, _versions_dir)
    os.makedirs(_versions_dir(), exist_ok=True)
    filename = f"yuanai-agent-v{version}.exe"
    path = os.path.join(_versions_dir(), filename)
    if not os.path.isfile(path):
        # 占位 exe（DOS 头 + 说明文本；仅供本地 UI 联调，不可执行）
        payload = b"MZ" + ("XiaoYuanAI demo agent version %s - local dev only, "
                           "DO NOT RUN" % version).encode() + b"\x00" * 256
        with open(path, "wb") as f:
            f.write(payload)
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
    data = _load_versions()
    entry = {"version": version, "filename": filename,
             "size": os.path.getsize(path), "sha256": sha.hexdigest(),
             "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "note": "本地联调演示版本（seed 脚本生成）"}
    data["versions"] = [v for v in data["versions"] if v["version"] != version] + [entry]
    if not data.get("default_version"):
        data["default_version"] = version
    _save_versions(data)
    _sync_version_json(data)
    print(f"演示版本 v{version} 已入本地版本库（默认版本）")
    print("刷新 /chat/agent 页面即可看到下载入口；测试安装码在页面自取。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
