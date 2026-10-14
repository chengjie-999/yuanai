"""脚本工具工厂 — ScriptRegistry 的每个脚本生成 langchain StructuredTool（统筹直调）

融合架构（2026-10-14 用户拍板对齐业界）：脚本类能力不再是「子 Agent 选脚本」，
而是统筹的 function calling 工具——LLM 一次调用直接产出 (脚本, 参数)，执行仍走
registry.run（参数校验/ALLOWED_ROOTS/SSRF 的唯一咽喉不变）。

- 工具名 = script_{key}（ASCII，provider 函数名限制；key 表在 registry.SCRIPT_KEYS）
- 描述 = [{skill 显示名}] {脚本中文名}：{脚本自述}（含参数说明）
- args_schema 动态生成：int/float→Optional[int/float]、enum+choices→Literal、其余
  →Optional[str]；全 optional（脚本声明无必填标记），校验由 registry 兜底
"""
import logging
from typing import Callable, Dict, List, Optional

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# script_dir → ScriptRegistry 缓存（目录扫描有 I/O，进程内复用）
_registry_cache: Dict[str, "ScriptRegistry"] = {}

# skill → 显示名（工具描述首段标签，前端 ToolCallCard 中文标签同源）
SKILL_LABELS = {"analysis": "数据分析", "collection": "数据采集"}


def get_registry(skill_name: str) -> Optional["ScriptRegistry"]:
    """按 skill 取脚本注册表（script_dir 来自 skills/*/skill.yaml；缓存）"""
    from agent.scripts.registry import ScriptRegistry
    from skills import skill_registry

    cfg = skill_registry.get(skill_name)
    if not cfg or not cfg.script_dir:
        return None
    if cfg.script_dir not in _registry_cache:
        _registry_cache[cfg.script_dir] = ScriptRegistry(cfg.script_dir, skill=skill_name)
    return _registry_cache[cfg.script_dir]


def _field_type(ptype: str, choices: Optional[list]):
    """registry 参数类型 → pydantic 字段类型"""
    if ptype == "int":
        return Optional[int]
    if ptype == "float":
        return Optional[float]
    if ptype == "enum" and choices:
        from typing import Literal
        return Optional[Literal[tuple(str(c) for c in choices)]]
    return Optional[str]


def _safe_field_name(name: str) -> str:
    """参数名非常规 Python 标识符时映射为安全字段名（保持 registry 校验用原名）"""
    import re
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return name
    return "arg_" + re.sub(r"\W", "_", name)


def build_script_tools(registry, skill: str = "",
                       progress_cb: Optional[Callable] = None,
                       enabled: bool = True) -> List[StructuredTool]:
    """registry 的每个脚本 → 一个 StructuredTool。enabled=False（托盘开关关）返回空列表。"""
    if not enabled:
        return []
    from pydantic import create_model

    label = SKILL_LABELS.get(skill or registry.skill, "")
    tools = []
    for h in registry.iter_handles():
        field_defs = {}
        field_desc = {}
        for pname in h._param_order:
            schema = h._param_schemas.get(pname, {})
            ptype = schema.get("type") or "str"
            fname = _safe_field_name(pname)
            field_defs[fname] = (_field_type(ptype, schema.get("choices")), None)
            hints = [ptype]
            if schema.get("choices"):
                hints.append("可选: " + "/".join(map(str, schema["choices"])))
            field_desc[fname] = f"{pname}（{'，'.join(hints)}）"

        model = create_model(f"Script_{h.key}_Params", **field_defs)
        if field_desc:
            fields = getattr(model, "model_fields", None) or getattr(model, "__fields__", {})
            for fname, desc in field_desc.items():
                finfo = fields[fname]
                if hasattr(finfo, "description"):
                    finfo.description = desc  # pydantic v2
                elif hasattr(finfo, "field_info"):
                    finfo.field_info.description = desc  # pydantic v1

        name_to_run = h.name

        def make_body(name):
            def _run_tool(**kwargs):
                params = {k: v for k, v in kwargs.items() if v is not None}
                return registry.run(name, params, progress_cb=progress_cb)
            return _run_tool

        desc = h.description or h.name
        prefix = f"[{label}] " if label else ""
        tools.append(StructuredTool(
            name=f"script_{h.key}",
            description=f"{prefix}{h.name}：{desc}",
            args_schema=model,
            func=make_body(name_to_run),
        ))
    return tools
