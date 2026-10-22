from pydantic import BaseModel, Field
from typing import List, Optional


class ChatRequest(BaseModel):
    # 默认主模型 = deepseek-flash（与前端 DEFAULT_MODEL 一致，2026-10-22 修正——
    # 曾默认豆包 pro：请求不带 model 字段时（API 直调/老客户端）全落豆包，
    # 与「主模型永远 deepseek」的产品定位相悖）
    model: str = Field("deepseek-flash", description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="生成温度")
    prompt: str = Field(..., description="用户输入文本")
    images: List[str] = Field(default_factory=list, description="Base64 图片列表")
    history: List[dict] = Field(default_factory=list, description='历史消息，格式 [{"role": "user/assistant", "content": "..."}]')
    system_prompt: str = Field("你是一个能调用工具的助手", description="系统提示")
    session_id: str = Field("", description="会话ID（Claude 桥接用于会话持久化）")
    decision: Optional[dict] = Field(None, description="审批决议（Claude 桥接）：{decision_id, approve}")
    force_cloud: bool = Field(False, description="强制走云端 LLM，跳过本地 Agent WebSocket 桥接")
    reasoning_effort: str = Field("low", description="推理强度：low 快答 / medium 标准 / high 深思（聊天框滑块）")
    target_agent: str = Field("", description="@指定智能体：analysis/collection/automation/claude/orchestrator；空=统筹自行路由")
    chat_mode: str = Field("work", description="产品模式：work=工作（云+本地Agent）/ entertainment=娱乐（纯云端，强制跳过本地 Agent 桥接）")


class ToolRequest(BaseModel):
    name: str = Field(..., description="工具名称")
    args: dict = Field(default_factory=dict, description="工具参数")


class ToolResponse(BaseModel):
    name: str
    result: str


class ToolInfo(BaseModel):
    name: str
    description: str
    args: dict
    category: str = Field("其他", description="工具分类")
    admin_only: bool = Field(False, description="仅 admin 可用")


class SaveMessagesRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    messages: List[dict] = Field(..., description='[{"role": "user/assistant", "content": "..."}]')
    title: Optional[str] = Field(None, description="会话标题（可选）")
