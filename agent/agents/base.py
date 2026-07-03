"""Agent 基类 + 脚本派发 Agent"""

import json
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from yuanai_core.core.lc import get_llm
from yuanai_core.core.schemas import AgentEvent
from agent.scripts.registry import ScriptRegistry

logger = logging.getLogger(__name__)


class AgentBase(ABC):
    """所有 Agent 的统一抽象基类"""

    name: str = "base"
    model_name: str = ""

    @abstractmethod
    def run(self, prompt: str) -> str:
        """同步执行（子类实现）。Orchestrator 通过 delegate 工具调用。"""
        ...


class ScriptDispatchAgent(AgentBase):
    """子类只需声明 script_dir / model_name / system_prompt / builtins 即可"""

    # —— 子类必须覆盖 ——
    script_dir: str
    system_prompt: str
    builtins: dict[str, str] = {}

    def __init__(self):
        super().__init__()
        self.registry = ScriptRegistry(self.script_dir)

    # —— 子类可选覆盖 ——
    def run(self, prompt: str) -> str:
        script_list = self.registry.list_for_llm()
        full_list = self._build_script_list(script_list)

        llm = get_llm(self.model_name, temperature=0, verbose=False)
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"可用操作：\n{full_list}\n\n用户需求：{prompt}"),
        ]
        response = llm.invoke(messages)
        choice = self._parse_json(response.content)

        if choice is None:
            logger.warning("LLM 返回非 JSON: %s", response.content[:200])
            return f"无法解析意图，请重新描述需求。原始响应: {response.content[:300]}"

        if not choice.get("script"):
            return f"无法处理：{choice.get('reason', '未知原因')}"

        script_name = choice["script"]
        params = choice.get("params", {})

        if script_name.startswith("builtin_"):
            return self._dispatch_builtin(script_name, params)

        return self.registry.run(script_name, params)

    # —— 内部方法 ——
    def _build_script_list(self, script_list: str) -> str:
        if not self.builtins:
            return script_list

        builtin_lines = "\n".join(
            f"- {name}: {desc}" for name, desc in self.builtins.items()
        )
        if "暂无可用脚本" in script_list:
            return builtin_lines
        return f"{builtin_lines}\n{script_list}"

    def _parse_json(self, text: str) -> dict | None:
        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @abstractmethod
    def _dispatch_builtin(self, name: str, params: dict) -> str:
        """子类实现内置操作的派发"""
        ...
