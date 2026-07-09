import os
import re
import sys
import json
import uuid
import time
import shutil
import base64
import subprocess
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _purge_html_cache(max_age_seconds: int = 3600):
    """清理过期的 HTML 缓存文件（默认 TTL 1 小时）"""
    cache_dir = os.path.join(PROJECT_ROOT, "data", "analysis", "html_cache")
    if not os.path.isdir(cache_dir):
        return
    now = time.time()
    for fname in os.listdir(cache_dir):
        fpath = os.path.join(cache_dir, fname)
        if fname.endswith(".html") and now - os.path.getmtime(fpath) > max_age_seconds:
            try:
                os.remove(fpath)
            except OSError:
                pass


class _ScriptHandle:
    def __init__(self, name: str, description: str, filepath: str, tags: List[str] = None):
        self.name = name
        self.description = description
        self._filepath = filepath
        self.tags = tags or []

    _SAFE_PARAM = re.compile(r'^[a-zA-Z0-9_\-一-鿿./: .,;!?@#$%^&*()+=<>\[\]{}|~`\'"]+$')

    def run(self, **params) -> str:
        _purge_html_cache()
        args = [sys.executable, self._filepath]
        param_order = getattr(self, '_param_order', [])
        keys = param_order if param_order else sorted(params)
        for k in keys:
            if k in params:
                val = str(params[k])
                if not self._SAFE_PARAM.match(val):
                    return f"参数校验失败: {k}={val[:100]} 含非法字符"
                args.append(val)

        try:
            result = subprocess.run(
                args,
                capture_output=True, text=True, encoding="utf-8",
                timeout=300,
                cwd=PROJECT_ROOT,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if result.returncode != 0:
                return f"脚本执行失败 (exit={result.returncode}):\n{result.stderr[:1000]}"

            output = result.stdout.strip() or "(脚本无输出)"

            # extract __RESULT__:json line
            result_match = re.search(r'__RESULT__:(.+)$', output, re.MULTILINE)
            if result_match:
                try:
                    data = json.loads(result_match.group(1))
                    result_dir = os.path.join(PROJECT_ROOT, "data", "analysis", "results")
                    os.makedirs(result_dir, exist_ok=True)
                    result_file = os.path.join(result_dir, f"{uuid.uuid4().hex[:8]}.json")
                    with open(result_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    output = output.replace(result_match.group(0), "")
                    output += f"\n__DASHBOARD__:{result_file}"
                except Exception as e:
                    logger.warning("parse __RESULT__ failed: %s", e)

            # extract __IMAGES__:path
            img_match = re.search(r'__IMAGES__:(.+)', output)
            if img_match:
                output = output.replace(img_match.group(0), "")
                for img_path in img_match.group(1).split(","):
                    img_path = img_path.strip()
                    if os.path.isfile(img_path):
                        ext = os.path.splitext(img_path)[1].lower()
                        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(
                            ext[1:], "image/png"
                        )
                        with open(img_path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                        output += f"\ndata:{mime};base64,{b64}"

            # extract __HTML__:path → copy to cache → __HTML__URL:url
            html_match = re.search(r'__HTML__:(.+)', output)
            if html_match:
                output = output.replace(html_match.group(0), "")
                html_urls = []
                for html_path in html_match.group(1).split(","):
                    html_path = html_path.strip()
                    if os.path.isfile(html_path):
                        cache_dir = os.path.join(PROJECT_ROOT, "data", "analysis", "html_cache")
                        os.makedirs(cache_dir, exist_ok=True)
                        cache_id = uuid.uuid4().hex[:12]
                        cached_path = os.path.join(cache_dir, f"{cache_id}.html")
                        shutil.copy2(html_path, cached_path)
                        html_urls.append(f"/api/v1/data/script-html/{cache_id}")
                if html_urls:
                    output += f"\n__HTML__URL:{','.join(html_urls)}"

            return output.strip()
        except subprocess.TimeoutExpired:
            return "脚本执行超时（5分钟）"
        except Exception as e:
            return f"脚本执行异常: {e}"


class ScriptRegistry:
    def __init__(self, script_dir: str):
        self._scripts: Dict[str, _ScriptHandle] = {}
        full_dir = os.path.join(PROJECT_ROOT, script_dir)
        self._discover(full_dir, script_dir.replace("/", ".").replace("\\", "."))

    def _discover(self, script_dir: str, package_hint: str):
        if not os.path.isdir(script_dir):
            logger.warning("脚本目录不存在: %s", script_dir)
            return

        for fname in sorted(os.listdir(script_dir)):
            if fname.startswith('_') or not fname.endswith('.py'):
                continue

            filepath = os.path.join(script_dir, fname)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    source = f.read()
            except Exception:
                logger.warning("读取脚本 %s 失败", fname, exc_info=True)
                continue

            name_match = re.search(r'__script_name__\s*=\s*["\']([^"\']+)["\']', source)
            desc_match = re.search(r'__script_desc__\s*=\s*["\']([^"\']+)["\']', source)
            tags_match = re.search(r'__script_tags__\s*=\s*\[([^\]]+)\]', source)

            if not name_match:
                self._discover_class(filepath, package_hint, fname)
                continue

            name = name_match.group(1)
            desc = desc_match.group(1) if desc_match else ""
            tags = []
            if tags_match:
                tags = [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(",") if t.strip()]

            handle = _ScriptHandle(name, desc, filepath, tags)

            params_match = re.search(r'__script_params__\s*=\s*\[([^\]]+)\]', source)
            if params_match:
                handle._param_order = [
                    p.strip().strip('"').strip("'")
                    for p in params_match.group(1).split(",")
                ]

            self._scripts[name] = handle
            logger.info("已注册脚本: %s (tags=%s) → %s", name, tags, filepath)

    def _discover_class(self, filepath: str, package: str, fname: str):
        import importlib.util, inspect
        from .base import BaseScript

        mod_name = f"{package}.{fname[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, filepath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:
            logger.warning("加载脚本 %s 失败", fname, exc_info=True)
            return

        for _, obj in inspect.getmembers(mod):
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseScript)
                and obj is not BaseScript
                and obj.name
            ):
                instance = obj()
                handle = _ScriptHandle(instance.name, instance.description, filepath)
                self._scripts[instance.name] = handle
                logger.info("已注册脚本(类): %s → %s", instance.name, filepath)

    def list_for_llm(self) -> str:
        if not self._scripts:
            return "（暂无可用脚本）"

        tagged: Dict[str, list] = {}
        untagged: list = []
        for s in self._scripts.values():
            if s.tags:
                for tag in s.tags:
                    tagged.setdefault(tag, []).append(s)
            else:
                untagged.append(s)

        lines = []
        for tag in sorted(tagged):
            lines.append(f"[{tag}]")
            for s in tagged[tag]:
                lines.append(f"- {s.name}: {s.description}")
        if untagged:
            lines.append("[其他]")
            for s in untagged:
                lines.append(f"- {s.name}: {s.description}")

        return "\n".join(lines)

    def run(self, name: str, params: dict = None) -> str:
        script = self._scripts.get(name)
        if not script:
            return f"未知脚本: {name}"
        return script.run(**(params or {}))
