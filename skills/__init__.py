"""Skill 注册中心 — 自动发现、加载、校验 skill 配置。

目录结构：
    skills/
    ├── __init__.py          ← 本文件（SkillRegistry）
    ├── analysis/skill.yaml   ← 数据分析
    ├── collection/skill.yaml ← 数据采集
    ├── automation/skill.yaml ← 自动化
    └── xxx/skill.yaml        ← 新增 skill（丢文件夹即可自动发现）

用法：
    from skills import skill_registry
    for skill in skill_registry.get_all():
        print(skill.name, skill.display_name)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class SkillConfig:
    """单个 Skill 的配置"""
    name: str                           # 唯一标识（英文，如 "analysis"）
    display_name: str                   # 显示名称（中文，如 "数据分析"）
    description: str                    # 一句话描述，Orchestrator 用来匹配意图
    model: str                          # 使用的 LLM 模型
    type: str = "script_dispatch"       # 运行模式：script_dispatch | react
    icon: str = "📦"                    # 图标 emoji
    keywords: list = field(default_factory=list)
    system_prompt: str = ""             # 系统提示词（从文件外置）
    script_dir: Optional[str] = None    # type=script_dispatch 时的脚本目录
    builtins: dict = field(default_factory=dict)  # 内置工具 {name: description}
    tool_filter: Optional[list] = None  # type=react 时的工具白名单（None=全部）


class SkillRegistry:
    """Skill 注册中心，扫描 skills/ 子目录自动发现"""

    def __init__(self, skills_dir: str = None):
        self._skills: dict[str, SkillConfig] = {}
        self._discover(skills_dir or SKILLS_DIR)

    def _discover(self, skills_dir: str):
        """遍历 skills_dir 下的子目录，解析 skill.yaml"""
        if not os.path.isdir(skills_dir):
            logger.warning("Skills 目录不存在: %s", skills_dir)
            return

        for entry in sorted(os.listdir(skills_dir)):
            skill_dir = os.path.join(skills_dir, entry)
            yaml_path = os.path.join(skill_dir, "skill.yaml")

            if not os.path.isdir(skill_dir) or entry.startswith("_"):
                continue
            if not os.path.isfile(yaml_path):
                continue

            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not data or "name" not in data:
                    logger.warning("跳过无效 skill 配置: %s", yaml_path)
                    continue

                config = SkillConfig(**data)
                self._skills[config.name] = config
                logger.info("✅ 已注册 Skill: %s (%s) — %s", config.name, config.display_name, config.type)
            except Exception as e:
                logger.warning("加载 Skill 失败 %s: %s", entry, e)

    def get_all(self) -> list:
        """返回所有已注册的 Skill"""
        return list(self._skills.values())

    def get(self, name: str) -> Optional[SkillConfig]:
        """按名称获取 Skill"""
        return self._skills.get(name)

    @property
    def names(self) -> list:
        """所有 Skill 名称列表"""
        return list(self._skills.keys())

    def list_for_llm(self) -> str:
        """生成给 Orchestrator LLM 看的 skill 简介"""
        if not self._skills:
            return "（暂无可用子Agent）"
        lines = []
        for s in self._skills.values():
            lines.append(f"- delegate_to_{s.name}_agent：{s.description}")
        return "\n".join(lines)


# 全局单例
skill_registry = SkillRegistry()
