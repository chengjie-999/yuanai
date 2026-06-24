import os
import re
import sys
import base64
import subprocess
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# 项目根目录 = agent/scripts/registry.py 上 3 级
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _ScriptHandle:
    def __init__(self, name: str, description: str, filepath: str, tags: List[str] = None):
        self.name = name
        self.description = description
        self._filepath = filepath
        self.tags = tags or []

    def run(self, **params) -> str:
        args = [sys.executable, self._filepath]
        param_order = getattr(self, '_param_order', [])
        if param_order:
            for p in param_order:
                if p in params:
                    args.append(str(params[p]))
        else:
            for k in sorted(params):
                args.append(str(params[k]))

        try:
            result = subprocess.run(
                args,
                capture_output=True, text=True,
                timeout=300,
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                return f"脚本执行失败 (exit={result.returncode}):\n{result.stderr[:1000]}"

            output = result.stdout.strip() or "(脚本无输出)"

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

            return output.strip()
        except subprocess.TimeoutExpired:
            return "脚本执行超时（5分钟）"
        except Exception as e:
            return f"脚本执行异常: {e}"


class ScriptRegistry:
    def __init__(self, script_dir: str):
        """
        script_dir: 脚本目录，相对于项目根，如 "agent/datanalysis/scripts"
        """
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
        """按 __script_tags__ 分组，输出给 LLM 看的脚本清单"""
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

    def run(self, name: str, **params) -> str:
        script = self._scripts.get(name)
        if not script:
            return f"未知脚本: {name}"
        return script.run(**params)
