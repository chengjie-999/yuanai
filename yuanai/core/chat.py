from typing import List, AsyncGenerator, Dict, Any

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

from yuanai.core.lc import get_langgraph_agent


def build_input_messages(
        prompt: str,
        images_base64: List[str],
        history: List[BaseMessage],
        system_message: SystemMessage,
) -> List[Dict[str, Any]]:
    """构建输入消息列表"""
    input_messages = []

    input_messages.append({"role": "system", "content": system_message.content})

    for msg in history:
        if isinstance(msg, HumanMessage):
            input_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            input_messages.append({"role": "assistant", "content": msg.content})

    if images_base64:
        content = [{"type": "text", "text": prompt}]
        for img in images_base64:
            content.append({
                "type": "image_url",
                "image_url": {"url": img}
            })
        input_messages.append({"role": "user", "content": content})
    else:
        input_messages.append({"role": "user", "content": prompt})

    return input_messages


async def stream_agent_events(
        llm,
        input_messages: List[Dict[str, Any]],
        tools: List[Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """流式获取 Agent 事件"""
    agent = get_langgraph_agent(llm, tools)

    full_response = ""
    full_reasoning = ""

    try:
        async for event in agent.astream_events(
                {"messages": input_messages},
                version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                token = ""

                if hasattr(chunk, "content") and chunk.content:
                    token = chunk.content
                    full_response += token

                if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
                    full_reasoning += chunk.reasoning_content
                    token = f"💭 {chunk.reasoning_content}"
                    full_response += token

                if token:
                    yield {"type": "token", "data": token}

            elif event["event"] == "on_tool_start":
                yield {
                    "type": "tool_start",
                    "data": {"name": event.get("name", "未知工具")}
                }

            elif event["event"] == "on_tool_end":
                yield {
                    "type": "tool_end",
                    "data": {"name": event.get("name", "未知工具")}
                }

        yield {
            "type": "done",
            "data": {
                "display_content": full_response,
                "raw_content": full_response.replace("💭 ", ""),
                "reasoning_content": full_reasoning
            }
        }
    except Exception as e:
        yield {"type": "error", "data": str(e)}


def parse_session_message(msg) -> tuple:
    """解析 session_state 中的消息元组，兼容新旧格式"""
    if len(msg) == 2:
        role, content = msg
        images = []
        reasoning = ""
    elif len(msg) == 3:
        role, content, images = msg
        reasoning = ""
        if images is None:
            images = []
        elif isinstance(images, str):
            images = [images]
    else:
        role, content, images, reasoning = msg
        if images is None:
            images = []
        elif isinstance(images, str):
            images = [images]
    return role, content, images, reasoning


def build_chat_history(session_messages: List[tuple]) -> List[BaseMessage]:
    """将 session 消息转换为 LangChain 消息列表"""
    chat_history = []
    for msg in session_messages:
        role, content, images, reasoning_content = parse_session_message(msg)

        if role == "user":
            if images:
                content_list = [{"type": "text", "text": content}]
                for img in images:
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": img}
                    })
                chat_history.append(HumanMessage(content=content_list))
            else:
                chat_history.append(HumanMessage(content=content))
        elif role == "assistant":
            ai_msg = AIMessage(content=content)
            if reasoning_content:
                ai_msg.additional_kwargs = {"reasoning_content": reasoning_content}
            chat_history.append(ai_msg)
    return chat_history


async def execute_chat(llm, prompt, images_base64, tools, history, system_message):
    """执行流式聊天，返回完整响应和推理内容"""
    input_messages = build_input_messages(prompt, images_base64, history, system_message)

    full_response = ""
    reasoning_content = ""

    async for event in stream_agent_events(llm, input_messages, tools):
        if event["type"] == "done":
            full_response = event["data"]["display_content"]
            reasoning_content = event["data"].get("reasoning_content", "")

    return full_response, reasoning_content