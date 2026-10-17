# -*- coding: utf-8 -*-
"""工具注册清单守门员 — 防「新增工具模块漏登记 _registry」导致 exe 内工具缺失

运行：pytest test/test_tools_registry.py -v（纯离线）
背景（2026-10-17）：os.walk 自动发现在 PyInstaller exe 内扫不到模块，工具
改为静态 _registry 清单加载；本测试保证清单与磁盘模块永远一致。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


def _scan_tool_modules(base_dir: str) -> set:
    """os.walk 收集含 BaseTool 的模块 stem（与 __init__ 补扫同口径）"""
    from langchain_core.tools import BaseTool
    import importlib
    found = set()
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith('__') and not d.startswith('.'))
        for file in sorted(files):
            if file.endswith('.py') and not file.startswith('_'):
                rel = os.path.relpath(os.path.join(root, file), base_dir)
                module_path = rel[:-3].replace(os.sep, '.')
                try:
                    mod = importlib.import_module(module_path)
                except Exception:
                    continue
                if any(isinstance(getattr(mod, a), BaseTool) for a in dir(mod)):
                    found.add(rel.replace(os.sep, '.'))
    return found


def test_shared_tools_registry_covers_all():
    """yuanai_core/tools 的每个含工具模块都在 _registry 清单"""
    base = os.path.join(os.path.dirname(__file__), '..', 'yuanai_core', 'tools')
    from yuanai_core.tools import _registry
    registered = {m.__name__ for m in _registry.TOOL_MODULES}
    found = _scan_tool_modules(os.path.abspath(base))
    missing = {f for f in found if f not in registered}
    assert not missing, f"未登记的工具模块（在 _registry.py 登记一行即可）: {missing}"


def test_agent_tools_registry_covers_all():
    """agent/tools 的每个含工具模块都在 _registry 清单"""
    base = os.path.join(os.path.dirname(__file__), '..', 'agent', 'tools')
    from agent.tools import _registry
    registered = {m.__name__ for m in _registry.TOOL_MODULES}
    found = _scan_tool_modules(os.path.abspath(base))
    missing = {f for f in found if f not in registered}
    assert not missing, f"未登记的工具模块（在 _registry.py 登记一行即可）: {missing}"


def test_all_tools_loads_via_registry():
    """all_tools 加载正常且 search_web 在列（打包修复的直接断言）"""
    from yuanai_core.tools import all_tools
    names = {t.name for t in all_tools}
    assert "search_web" in names, "search_web 必须在共享工具里（生产 exe 曾缺失）"
    assert len(all_tools) >= 30


def test_agent_tools_load():
    from agent.tools import _scan_agent_tools
    names = {t.name for t in _scan_agent_tools()}
    assert len(names) >= 30, f"专用工具数异常: {len(names)}"


if __name__ == "__main__":
    print("测试入口：pytest test/test_tools_registry.py -v")
