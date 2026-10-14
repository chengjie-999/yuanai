import os
import ast
import re
import sys
import json
import uuid
import time
import shutil
import base64
import subprocess
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# S1.6：path 型参数允许落脚的根目录（realpath 包含校验）
ALLOWED_ROOTS = [
    "data",
    "agent/datanalysis/scripts",
    "agent/datanalysis/crawl",
    "skills",
]

# 枚举型参数字符集：禁 / \ 与 ..（路径语义），禁首字符 -（选项注入）；
# 参数经 Popen 列表传递（无 shell），其余标点无注入能力
_ENUM_FORBIDDEN = ("/", "\\", "..")
_INT_RE = re.compile(r"^\d{1,10}$")
_FLOAT_RE = re.compile(r"^\d{1,4}(\.\d{1,6})?$")

# 脚本规范名 → ASCII 工具 key（provider 函数名限制 ^[a-zA-Z0-9_-]{1,64}$，
# 中文名不能直接当工具名）。未登记的脚本 fallback script_+md5[:8]（确定性，
# 跨机一致）。
SCRIPT_KEYS = {
    "描述性统计分析": "descriptive_stats",
    "相关性分析": "correlation",
    "回归分析": "regression",
    "分类数据分析": "categorical",
    "时间序列分析": "timeseries",
    "数据预处理": "preprocess",
    "RFM客户分群": "rfm_cluster",
    "客户流失预测": "churn_predict",
    "基因表达分布分析": "gene_expression",
    "通用网页采集": "generic_crawl",
}


def _script_key(name: str) -> str:
    """规范名 → ASCII key（无登记则确定性 fallback）"""
    if name in SCRIPT_KEYS:
        return SCRIPT_KEYS[name]
    import hashlib
    return "script_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8]

# 旧格式字符串参数名的类型启发式（含 path|file|dir → path；含 id|num|count|top|size|limit|pages|period → int）
_PATH_HINT = ("path", "file", "dir")
_INT_HINT = ("id", "num", "count", "top", "size", "limit", "pages", "period", "depth", "index")


def _guess_type(name: str) -> str:
    lower = name.lower()
    if any(h in lower for h in _PATH_HINT):
        return "path"
    if any(h in lower for h in _INT_HINT):
        return "int"
    return "enum"


def _validate_param(key: str, val: str, schema: Dict) -> str:
    """单参数类型化校验，返回错误文案或空串（通过）。"""
    if val.startswith("-"):
        return f"参数 {key} 不得以 - 开头"
    ptype = schema.get("type") or _guess_type(key)
    if ptype == "int":
        return "" if _INT_RE.fullmatch(val) else f"参数 {key} 需为整数"
    if ptype == "float":
        return "" if _FLOAT_RE.fullmatch(val) else f"参数 {key} 需为数字（如 0.2）"
    if ptype == "path":
        p = os.path.realpath(os.path.join(PROJECT_ROOT, val) if not os.path.isabs(val) else val)
        allowed = [os.path.realpath(os.path.join(PROJECT_ROOT, r)) for r in ALLOWED_ROOTS]
        if not any(p == a or p.startswith(a + os.sep) for a in allowed):
            return f"参数 {key} 路径越界（仅允许 data/ 与脚本目录内）"
        return ""
    if ptype == "url":
        from yuanai_core.pure.ssrf import validate_url
        try:
            validate_url(val)
            return ""
        except ValueError as e:
            return f"参数 {key} 不是合法 URL: {e}"
    # enum
    choices = schema.get("choices")
    if choices and val not in choices:
        return f"参数 {key} 仅支持: {', '.join(map(str, choices))}"
    if any(bad in val for bad in _ENUM_FORBIDDEN) or not val or len(val) > 128:
        return f"参数 {key} 含非法字符"
    return ""


def _parse_params_decl(raw: str, handle: "_ScriptHandle") -> None:
    """解析 __script_params__ 声明（S1.6 双格式）：

    - 新格式：[{"name": "file_path", "type": "path"}, {"name": "chart_type",
      "type": "enum", "choices": ["all", ...]}]（ast.literal_eval）
    - 旧格式：["file_path", "dataset_id"]（类型启发式：含 path|file|dir → path，
      含 id|num|count|top 等 → int，其余 enum 默认拒绝路径语义）
    """
    try:
        data = ast.literal_eval(raw)
    except Exception:
        return
    if not isinstance(data, list):
        return
    for item in data:
        if isinstance(item, dict):
            pname = str(item.get("name", "")).strip()
            if not pname:
                continue
            schema = {"type": item.get("type") or _guess_type(pname)}
            if isinstance(item.get("choices"), list):
                schema["choices"] = [str(c) for c in item["choices"]]
            handle._param_schemas[pname] = schema
            if pname not in handle._param_order:
                handle._param_order.append(pname)
        elif isinstance(item, str) and item.strip():
            pname = item.strip()
            handle._param_schemas[pname] = {"type": _guess_type(pname)}
            if pname not in handle._param_order:
                handle._param_order.append(pname)


def _purge_html_cache(max_age_seconds: int = 3600):
    """清理过期的 HTML 缓存文件（默认 TTL 1 小时）；.owner 归属文件随 html 一并清"""
    cache_dir = os.path.join(PROJECT_ROOT, "data", "analysis", "html_cache")
    if not os.path.isdir(cache_dir):
        return
    now = time.time()
    for fname in os.listdir(cache_dir):
        fpath = os.path.join(cache_dir, fname)
        if fname.endswith((".html", ".owner")) and now - os.path.getmtime(fpath) > max_age_seconds:
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
        self.key = _script_key(name)          # ASCII 工具名（统筹 function calling 用）
        self.skill = ""                       # 归属 skill（registry 构造时注入）
        self._param_order: List[str] = []
        self._param_schemas: Dict[str, Dict] = {}  # S1.6：name → {"type":..., "choices":[...]}

    def run(self, progress_cb=None, **params) -> str:
        _purge_html_cache()
        # 冻结模式（PyInstaller exe）：本 exe 不是 Python 解释器，通过 --run-script 入口复用自身执行脚本（自包含）
        frozen = getattr(sys, "frozen", False)
        args = [sys.executable, "--run-script", self._filepath] if frozen else [sys.executable, self._filepath]
        param_order = self._param_order or sorted(params)
        for k in param_order:
            if k in params:
                val = str(params[k])
                # S1.6：类型化校验（int/path/enum/url + 启发式默认）；不通过即拒绝启动子进程
                err = _validate_param(k, val, self._param_schemas.get(k, {}))
                if err:
                    return f"参数校验失败: {err}（收到 {val[:100]!r}）"
                args.append(val)

        try:
            popen_kwargs = {
                "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                "text": True, "encoding": "utf-8",
                "cwd": PROJECT_ROOT,
                "env": {**os.environ, "PYTHONIOENCODING": "utf-8"},
                "bufsize": 1,  # 行缓冲：脚本输出实时可见
            }
            # Windows 托盘模式下子进程不弹黑窗
            if frozen and os.name == "nt":
                popen_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
            proc = subprocess.Popen(args, **popen_kwargs)

            # 流式读输出（读线程跨平台）：stdout 识别 __PROGRESS__:{json} 协议；
            # 时间心跳 10s 一次（存量脚本零改动也有进度反馈）
            stdout_lines: List[str] = []
            stderr_lines: List[str] = []

            def _read_stream(stream, sink, is_stdout):
                try:
                    for line in iter(stream.readline, ""):
                        sink.append(line)
                        if is_stdout:
                            m = re.search(r"__PROGRESS__:(\{.*\})", line)
                            if m:
                                try:
                                    d = json.loads(m.group(1))
                                    if progress_cb:
                                        progress_cb(d.get("current", 0), d.get("total", 0), d.get("message", ""))
                                except Exception:
                                    pass
                except (ValueError, OSError):
                    pass

            import threading
            t_out = threading.Thread(target=_read_stream, args=(proc.stdout, stdout_lines, True), daemon=True)
            t_err = threading.Thread(target=_read_stream, args=(proc.stderr, stderr_lines, False), daemon=True)
            t_out.start()
            t_err.start()

            start_time = time.time()
            last_beat = start_time
            while True:
                if proc.poll() is not None:
                    break
                elapsed = time.time() - start_time
                if elapsed > 300:
                    proc.kill()
                    proc.wait()
                    return "脚本执行超时（300 秒），已终止"
                if progress_cb and time.time() - last_beat >= 10:
                    progress_cb(0, 0, f"分析中（已运行 {int(elapsed)} 秒）...")
                    last_beat = time.time()
                time.sleep(0.2)

            t_out.join(timeout=5)
            t_err.join(timeout=5)

            if proc.returncode != 0:
                err_text = "".join(stderr_lines)
                return f"脚本执行失败 (exit={proc.returncode}):\n{err_text[:1000]}"

            output = "".join(stdout_lines).strip() or "(脚本无输出)"

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
                        # S1.2：写 .owner 归属（云端 serve_script_html 校验，防越权读他人分析 HTML）
                        try:
                            from yuanai_core.rag import current_user_id
                            with open(os.path.join(cache_dir, f"{cache_id}.owner"),
                                      "w", encoding="utf-8") as of:
                                of.write(str(current_user_id.get()))
                        except Exception as e:
                            logger.warning("write .owner failed: %s", e)
                        html_urls.append(f"/api/v1/data/script-html/{cache_id}")
                if html_urls:
                    output += f"\n__HTML__URL:{','.join(html_urls)}"

            return output.strip()
        except subprocess.TimeoutExpired:
            return "脚本执行超时（5分钟）"
        except Exception as e:
            return f"脚本执行异常: {e}"


class ScriptRegistry:
    def __init__(self, script_dir: str, skill: str = ""):
        self._scripts: Dict[str, _ScriptHandle] = {}
        self.skill = skill
        full_dir = os.path.join(PROJECT_ROOT, script_dir)
        self._discover(full_dir, script_dir.replace("/", ".").replace("\\", "."))
        if skill:
            for h in self._scripts.values():
                h.skill = skill

    def iter_handles(self) -> List["_ScriptHandle"]:
        """公开枚举（注册序）；测试与工具工厂用，不翻 _scripts 私有"""
        return list(self._scripts.values())

    def resolve(self, name: str) -> Optional[str]:
        """规范中文名 / ASCII key（带不带 script_ 前缀）→ 规范名；未知返回 None"""
        s = str(name or "").strip()
        if s in self._scripts:
            return s
        for h in self._scripts.values():
            if s == h.key or s == f"script_{h.key}":
                return h.name
        return None

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

            params_match = re.search(r'__script_params__\s*=\s*(\[.*\])', source)
            if params_match:
                _parse_params_decl(params_match.group(1), handle)

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

    def run(self, name: str, params: dict = None, progress_cb=None) -> str:
        """执行脚本。progress_cb(current, total, message)：进度回调透传 handle。
        名字先经 resolve（中文名/key 双通道，工具化后 model 传 key）。

        修复（2026-10-12）：base.py 一直传 progress_cb 进来但本方法不接受 →
        委派路径抛 TypeError。回归断言在 test/test_plan_pure.py::test_registry_run_accepts_progress_cb。
        """
        resolved = self.resolve(name)
        script = self._scripts.get(resolved or "") if resolved else None
        if not script:
            return f"未知脚本: {name}"
        return script.run(progress_cb=progress_cb, **(params or {}))
