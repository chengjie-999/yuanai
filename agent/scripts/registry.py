import os
import re
import sys
import base64
import subprocess
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class _ScriptHandle:
    """脚本句柄"""
    def __init__(self, name: str, description: str, filepath: str):
        self.name = name
        self.description = description
        self._filepath = filepath

    def run(self, **params) -> str:
        """子进程执行脚本，参数通过命令行传入。自动检测 __IMAGES__ 标记并嵌入 base64 图片"""
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
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(self._filepath))),
            )
            if result.returncode != 0:
                return f"脚本执行失败 (exit={result.returncode}):\n{result.stderr[:1000]}"

            output = result.stdout.strip() or "(脚本无输出)"

            # 解析 __IMAGES__:path1,path2 标记，嵌入 base64 图片
            img_match = re.search(r'__IMAGES__:(.+)', output)
            if img_match:
                output = output.replace(img_match.group(0), "")
                for img_path in img_match.group(1).split(","):
                    img_path = img_path.strip()
                    if os.path.isfile(img_path):
                        ext = os.path.splitext(img_path)[1].lower()
                        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext[1:], "image/png")
                        with open(img_path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                        output += f"\ndata:{mime};base64,{b64}"

            return output.strip()
        except subprocess.TimeoutExpired:
            return "脚本执行超时（5分钟）"
        except Exception as e:
            return f"脚本执行异常: {e}"


class ScriptRegistry:
    def __init__(self, package: str):
        """
        package: 脚本包路径，如 "agent.scripts.crawl"
        纯文本解析 → 不导入模块，避免执行分析代码
        """
        self._scripts: Dict[str, _ScriptHandle] = {}
        self._discover(package)

    def _discover(self, package: str):
        import importlib
        pkg = importlib.import_module(package)
        pkg_dir = os.path.dirname(pkg.__file__)

        for fname in sorted(os.listdir(pkg_dir)):
            if fname.startswith('_') or not fname.endswith('.py'):
                continue

            filepath = os.path.join(pkg_dir, fname)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    source = f.read()
            except Exception:
                logger.warning("读取脚本 %s 失败", fname, exc_info=True)
                continue

            # 从源码中正则提取 __script_name__ 和 __script_desc__
            name_match = re.search(r'__script_name__\s*=\s*["\']([^"\']+)["\']', source)
            desc_match = re.search(r'__script_desc__\s*=\s*["\']([^"\']+)["\']', source)

            if not name_match:
                # 兼容旧的 BaseScript 类模式
                self._discover_class(filepath, package, fname)
                continue

            name = name_match.group(1)
            desc = desc_match.group(1) if desc_match else ""
            handle = _ScriptHandle(name, desc, filepath)

            # 提取参数顺序声明
            params_match = re.search(r'__script_params__\s*=\s*\[([^\]]+)\]', source)
            if params_match:
                handle._param_order = [
                    p.strip().strip('"').strip("'")
                    for p in params_match.group(1).split(",")
                ]

            self._scripts[name] = handle
            logger.info("已注册脚本: %s → %s", name, filepath)

    def _discover_class(self, filepath: str, package: str, fname: str):
        """兼容：导入模块查找 BaseScript 子类"""
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
        lines = [f"- {s.name}: {s.description}" for s in self._scripts.values()]
        return "\n".join(lines)

    def run(self, name: str, **params) -> str:
        script = self._scripts.get(name)
        if not script:
            return f"未知脚本: {name}"
        return script.run(**params)
