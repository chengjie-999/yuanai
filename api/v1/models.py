from pydantic import BaseModel, Field
from typing import List, Optional


class ChatRequest(BaseModel):
    model: str = Field("doubao-seed-2-0-pro-260215", description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="生成温度")
    prompt: str = Field(..., description="用户输入文本")
    images: List[str] = Field(default_factory=list, description="Base64 图片列表")
    history: List[dict] = Field(default_factory=list, description='历史消息，格式 [{"role": "user/assistant", "content": "..."}]')
    system_prompt: str = Field("你是一个能调用工具的助手", description="系统提示")


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    create_time: str


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
