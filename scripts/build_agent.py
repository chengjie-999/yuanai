# -*- coding: utf-8 -*-
"""一键打包 + 一键发布 Agent 安装包（2026-10-30 统一命名规范；
2026-11-07 企业级安装器：PyInstaller 裸 exe + Inno Setup 安装器双产物）

统一产物命名 = `yuanai-agent-v{version}.exe`（与服务器版本库存放规范一致，
上传时后台版本号直接填 version 即可，本地产物与线上清单同名可对照）；
安装器 = `yuanai-agent-setup-v{version}.exe`（内容固定不含码，码在下载
端点动态写入 Content-Disposition 文件名——签名对文件名改动免疫）。

用法：
    python scripts/build_agent.py 20261030                     # 指定版本号打包
    python scripts/build_agent.py                              # 留空自动用日期 YYYYMMDD
    python scripts/build_agent.py 20261030 --upload https://cjyuanai.cn
                                                               # 打包后一键上传发布
    --note "本次更新内容"                                      # 版本备注（随上传提交）
    --token <长令牌>                                           # 管理员长令牌；或环境变量
                                                               # YUAN_ADMIN_TOKEN（后台
                                                               # 「Agent 管理 → 签发长令牌」，90 天有效）

流程：版本号写入 agent/tray.py 的 AGENT_VERSION（打包后还原）→ PyInstaller
按 agent/yuanai_agent.spec 打包 → 产物重命名为 yuanai-agent-v{version}.exe 放
dist/versions/ → ISCC 编译安装器（捆绑裸 exe + 协议页 + 免输码提取）→ 双产物
sha256 打印（上传后可与后台清单核对；发布顺序纪律：先后端上传含 hash → 再发布）。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAY = os.path.join(ROOT, "agent", "tray.py")
SPEC = os.path.join(ROOT, "agent", "yuanai_agent.spec")
ISS = os.path.join(ROOT, "agent", "installer", "yuanai_agent.iss")
OUT_DIR = os.path.join(ROOT, "dist", "versions")
LICENSE_MD = os.path.join(ROOT, "docs", "agreements", "用户协议.md")
LICENSE_TXT = os.path.join(ROOT, "docs", "agreements", "用户协议.txt")


def _find_iscc() -> str:
    """定位 Inno Setup 编译器：env INNO_ISCC > 常见安装路径 > D:\\installed"""
    env = os.environ.get("INNO_ISCC", "").strip()
    if env and os.path.isfile(env):
        return env
    candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
        r"D:\installed\Inno Setup 6\ISCC.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ""


def _gen_license_txt() -> None:
    """《用户协议》.md → .txt（安装器协议页 LicenseFile 只吃纯文本；
    剥掉 markdown 标记，正文不变）"""
    if not os.path.isfile(LICENSE_MD):
        print("警告: 未找到用户协议 md，安装器协议页将缺失")
        return
    with open(LICENSE_MD, "r", encoding="utf-8") as f:
        md = f.read()
    lines = []
    for line in md.splitlines():
        s = line.strip()
        if not s or set(s) <= {"-", "=", "*"}:
            continue
        s = re.sub(r"^#{1,6}\s*", "", s)
        s = s.replace("**", "").replace("`", "").replace("> ", "")
        lines.append(s)
    with open(LICENSE_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("用户协议 txt 已生成（安装器协议页用）")


def _build_setup(version: str, exe_path: str) -> str:
    """ISCC 编译安装器 → dist/versions/yuanai-agent-setup-v{version}.exe。
    返回产物路径；ISCC 缺失或编译失败抛异常（安装器是本链路交付物）。"""
    iscc = _find_iscc()
    if not iscc:
        raise RuntimeError(
            "未找到 Inno Setup 编译器（ISCC.exe）。请安装 Inno Setup 6 "
            "（https://www.innosetup.com）或设置环境变量 INNO_ISCC 指向 ISCC.exe")
    _gen_license_txt()
    print(f"== 编译安装器 v{version}（ISCC: {iscc}）==")
    ret = subprocess.call(
        [iscc, f"/DAppVersion={version}", f"/DExeSource={exe_path}", ISS],
        cwd=ROOT)
    if ret != 0:
        raise RuntimeError("ISCC 编译失败")
    tmp_setup = os.path.join(ROOT, "dist", "yuanai-agent-setup-tmp.exe")
    if not os.path.isfile(tmp_setup):
        raise RuntimeError(f"未找到安装器产物: {tmp_setup}")
    final_path = os.path.join(OUT_DIR, f"yuanai-agent-setup-v{version}.exe")
    os.makedirs(OUT_DIR, exist_ok=True)
    os.replace(tmp_setup, final_path)
    return final_path


def _set_agent_version(version: str):
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


def _upload_one(server: str, token: str, version: str, note: str,
                final_path: str, final_name: str, kind: str = "exe") -> bool:
    """单文件上传：POST /admin/agent-exe-upload（kind=exe 入版本清单并默认
    指向；kind=setup 附安装器标记）"""
    import requests
    with open(final_path, "rb") as f:
        resp = requests.post(
            f"{server}/api/v1/admin/agent-exe-upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"version": version, "note": note, "kind": kind},
            files={"file": (final_name, f, "application/octet-stream")},
            timeout=600)
    data = {}
    try:
        data = resp.json()
    except Exception:
        pass
    if resp.status_code == 200 and data.get("ok"):
        print(f"已上传 {kind}（sha256: {str(data.get('sha256', ''))[:16]}...）")
        return True
    print(f"上传失败 HTTP {resp.status_code}: {str(data.get('detail', resp.text[:200]))}")
    return False


def _upload_publish(server: str, token: str, version: str, note: str,
                    final_path: str, final_name: str, setup_path: str,
                    setup_name: str) -> int:
    """一键发布：先传裸 exe（版本入清单，默认自动指向）→ 再传安装器
    （发布顺序纪律：后端含 hash 先生效，安装器最后到位）。"""
    if not token:
        print("--upload 需要管理员长令牌：--token 或环境变量 YUAN_ADMIN_TOKEN")
        print("获取：后台「Agent 管理 → 签发长令牌」（90 天有效）")
        return 1
    print(f"== 上传发布到 {server} ==")
    try:
        if not _upload_one(server, token, version, note, final_path, final_name, "exe"):
            return 1
        print("自动更新已指向该版本（发布顺序纪律：后端含 hash 先生效）")
        if not _upload_one(server, token, version, note, setup_path, setup_name, "setup"):
            print("⚠ 安装器上传失败——带码下载将退回裸 exe 旧链路（输码注册）")
            return 1
        print(f"已发布 v{version}（裸 exe + 企业级安装器双产物）")
        return 0
    except Exception as e:
        print(f"上传失败: {str(e)[:200]}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="一键打包 + 一键发布 Agent 安装包")
    ap.add_argument("version", nargs="?", default="", help="版本号（留空自动 YYYYMMDD）")
    ap.add_argument("--upload", default="", help="打包后一键上传发布的服务器地址（如 https://cjyuanai.cn）")
    ap.add_argument("--token", default="", help="管理员长令牌（或环境变量 YUAN_ADMIN_TOKEN）")
    ap.add_argument("--note", default="", help="版本备注（随上传提交）")
    args = ap.parse_args()

    version = args.version.strip() or datetime.now().strftime("%Y%m%d")
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
    print(f"== 裸 exe 完成 ==\n产物: {final_path}\n大小: {size / 1024 / 1024:.0f}MB\n"
          f"sha256: {sha.hexdigest()}")

    # 企业级安装器（2026-11-07）：捆绑裸 exe + 协议页 + 免输码提取
    try:
        setup_path = _build_setup(version, final_path)
    except RuntimeError as e:
        print(f"安装器编译失败: {e}")
        return 1
    setup_sha = hashlib.sha256()
    with open(setup_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            setup_sha.update(chunk)
    print(f"== 安装器完成 ==\n产物: {setup_path}\n大小: {os.path.getsize(setup_path) / 1024 / 1024:.0f}MB\n"
          f"sha256: {setup_sha.hexdigest()}")

    if args.upload:
        return _upload_publish(args.upload.rstrip("/"),
                               args.token or os.environ.get("YUAN_ADMIN_TOKEN", ""),
                               version, args.note, final_path, final_name,
                               setup_path, f"yuanai-agent-setup-v{version}.exe")
    print("上传：后台「Agent 管理 → 发布新版本」填版本号 " + version +
          " 并拖入两个产物（裸 exe 先传，安装器后传）；或加 --upload 一键发布；"
          "上传后对照后台清单 sha256。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
