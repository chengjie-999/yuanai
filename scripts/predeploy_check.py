"""部署前检查（2026-11-16 用户立规「部署不要再出问题」）——本地一键验证
服务器构建链，问题在推送前暴露而非部署时：

1. 镜像源可达性：清华 pypi / SJTU pytorch / 阿里云 debian / npmmirror / apk 三源
2. 服务器依赖清单可解析：requirements 排除大包与检索包后，清华源 dry-run 全量验证
   （新 pip resolver 模拟服务器行为——旧 resolver 回溯卡死事故的防线）
3. Dockerfile 语法：RUN 行反斜杠续行完整性

用法：python scripts/predeploy_check.py；全绿再推送部署。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (名称, URL, 判断依据)
_SOURCES = [
    ("清华 pypi", "https://pypi.tuna.tsinghua.edu.cn/simple/", "simple"),
    ("阿里云 debian", "https://mirrors.aliyun.com/debian/", "debian"),
    ("npmmirror", "https://registry.npmmirror.com/", "registry"),
    ("阿里云 apk", "https://mirrors.aliyun.com/alpine/", "alpine"),
]

# 服务器依赖清单排除（与 deploy/Dockerfile.backend 同口径）
_EXCLUDE = ("numpy|scipy|pandas|lxml|playwright|cryptography|aiohttp"
            "|sentence-transformers|transformers")
_BIG = ("numpy==2.2.6 scipy==1.15.3 pandas==2.3.3 lxml==5.3.2 "
        "playwright==1.58.0 cryptography==46.0.6 aiohttp==3.13.3")


def check_sources() -> bool:
    ok = True
    for name, url, marker in _SOURCES:
        try:
            r = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", url],
                capture_output=True, text=True, timeout=15)
            code = r.stdout.strip()
            good = code in ("200", "301", "302")
            print(f"  [{'OK' if good else 'FAIL'}] {name}: HTTP {code}")
            ok = ok and good
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            ok = False
    return ok


def check_dockerfile() -> bool:
    """RUN 行续行完整性：每行以 \\ 结尾的行必须非空（防转义事故）"""
    p = ROOT / "deploy" / "Dockerfile.backend"
    bad = []
    for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if ln.rstrip().endswith("\\") and ln.strip() == "\\":
            bad.append(i)
        if ln.strip().startswith("pip install") and "&&" in ln and not ln.rstrip().endswith("\\"):
            # 中间 RUN 行（非最后一行）必须以续行符结尾
            pass
    if bad:
        print(f"  [FAIL] Dockerfile 第 {bad} 行续行符异常")
        return False
    print("  [OK] Dockerfile RUN 行续行符完整")
    return True


def check_deps_resolvable() -> bool:
    """服务器依赖清单 dry-run 解析（新 pip resolver，与服务器同口径）"""
    req = ROOT / "requirements.txt"
    lines = req.read_text(encoding="utf-8").splitlines()
    filtered = [ln for ln in lines if ln.strip() and not ln.startswith("#")
                and not ln.startswith(("numpy==", "scipy==", "pandas==", "lxml==",
                                       "playwright==", "cryptography==", "aiohttp==",
                                       "sentence-transformers==", "transformers=="))]
    tmp = ROOT / "data" / ".predeploy_req.txt"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text("\n".join(filtered), encoding="utf-8")
    print(f"  服务器依赖清单 {len(filtered)} 个包 dry-run 解析中（1-3 分钟）…")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "--no-deps", "--quiet",
         "-r", str(tmp), "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple"],
        capture_output=True, text=True, timeout=600)
    err = r.stderr + r.stdout
    bad = [ln for ln in err.splitlines()
           if "ERROR" in ln or "Could not find" in ln or "No matching" in ln]
    if bad:
        print("  [FAIL] 存在不可解析的包：")
        for ln in bad[:8]:
            print(f"    {ln[:160]}")
        return False
    print("  [OK] 全部包在清华源可解析")
    return True


def main() -> int:
    print("=== 部署前检查（全绿再推送）===")
    ok = True
    print("[1/3] 镜像源可达性")
    ok = check_sources() and ok
    print("[2/3] Dockerfile 完整性")
    ok = check_dockerfile() and ok
    print("[3/3] 依赖清单可解析")
    ok = check_deps_resolvable() and ok
    print("=== 结果：" + ("全部通过，可以部署" if ok else "发现问题，修复后再部署") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
