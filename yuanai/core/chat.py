import re
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
            if isinstance(msg.content, list):
                text = "".join(
                    c["text"] for c in msg.content if isinstance(c, dict) and c.get("type") == "text"
                )
                input_messages.append({"role": "user", "content": text})
            else:
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

                if hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content
                    yield {"type": "token", "data": chunk.content}

                if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
                    full_reasoning += chunk.reasoning_content
                    yield {"type": "reasoning", "data": chunk.reasoning_content}

            elif event["event"] == "on_tool_start":
                yield {
                    "type": "tool_start",
                    "data": {"name": event.get("name", "未知工具")}
                }

            elif event["event"] == "on_tool_end":
                output = event["data"].get("output", "")
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', str(output))
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
                yield {
                    "type": "tool_end",
                    "data": {"name": event.get("name", "未知工具"), "output": clean_output}
                }

        yield {
            "type": "done",
            "data": {
                "display_content": full_response,
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


async def stream_agent_with_messages(
        llm,
        messages: List[BaseMessage],
        tools: List[Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """使用 LangChain Message 对象流式调用 Agent"""
    agent = get_langgraph_agent(llm, tools)

    full_response = ""
    full_reasoning = ""

    try:
        async for event in agent.astream_events(
                {"messages": messages},
                version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]

                if hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content
                    yield {"type": "token", "data": chunk.content}

                if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
                    full_reasoning += chunk.reasoning_content
                    yield {"type": "reasoning", "data": chunk.reasoning_content}

            elif event["event"] == "on_tool_start":
                yield {
                    "type": "tool_start",
                    "data": {"name": event.get("name", "未知工具")}
                }

            elif event["event"] == "on_tool_end":
                output = event["data"].get("output", "")
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', str(output))
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
                yield {
                    "type": "tool_end",
                    "data": {"name": event.get("name", "未知工具"), "output": clean_output}
                }

        yield {
            "type": "done",
            "data": {
                "display_content": full_response,
                "reasoning_content": full_reasoning
            }
        }
    except Exception as e:
        yield {"type": "error", "data": str(e)}

async def stream_agent_with_inject(
        llm,
        initial_messages: List[BaseMessage],
        tools: List[Any],
        on_tool_end,
        max_rounds: int = 3,
) -> AsyncGenerator[Dict[str, Any], None]:
    """支持工具调用后注入新截图消息的 Agent 流式调用。"""
    messages = list(initial_messages)

    for round_idx in range(max_rounds):
        agent = get_langgraph_agent(llm, tools)
        full_response = ""
        full_reasoning = ""
        tool_names = set()

        try:
            async for event in agent.astream_events({"messages": messages}, version="v2"):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        yield {"type": "token", "data": chunk.content}
                    if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
                        full_reasoning += chunk.reasoning_content
                        yield {"type": "reasoning", "data": chunk.reasoning_content}
                elif event["event"] == "on_tool_start":
                    yield {"type": "tool_start", "data": {"name": event.get("name", "未知工具")}}
                elif event["event"] == "on_tool_end":
                    name = event.get("name", "未知工具")
                    tool_names.add(name)
                    yield {"type": "tool_end", "data": {"name": name}}
        except Exception as e:
            yield {"type": "error", "data": str(e)}
            return

        inject_result = on_tool_end(list(tool_names))
        if inject_result and round_idx < max_rounds - 1:
            messages.append(HumanMessage(content="[系统提示] 已滚动并重新截图，这是更新后的内容："))
            messages.extend(inject_result)
            yield {"type": "inject", "data": {"round": round_idx + 1, "tool_names": list(tool_names)}}
            continue

        yield {"type": "done", "data": {
            "display_content": full_response,
            "reasoning_content": full_reasoning
        }}
        return

    yield {"type": "error", "data": f"已达到最大轮次({max_rounds})，可能仍未获取完整题目"}