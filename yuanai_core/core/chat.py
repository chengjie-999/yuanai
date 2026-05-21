import re
import json
from typing import List, AsyncGenerator, Dict, Any

from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage,
)

from yuanai_core.core.lc import get_langgraph_agent


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


def _dicts_to_lc_messages(msg_dicts: List[dict]) -> List[BaseMessage]:
    """将字典列表转为 LangChain 消息，保活 reasoning_content"""
    lc_messages = []
    for m in msg_dicts:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            additional_kwargs = {}
            if m.get("reasoning_content"):
                additional_kwargs["reasoning_content"] = m["reasoning_content"]
            if m.get("tool_calls"):
                additional_kwargs["tool_calls"] = m["tool_calls"]
            ai_msg = AIMessage(content=content, additional_kwargs=additional_kwargs)
            if m.get("tool_calls"):
                ai_msg.tool_calls = m["tool_calls"]
            lc_messages.append(ai_msg)
        elif role == "tool":
            lc_messages.append(ToolMessage(
                content=content,
                tool_call_id=m.get("tool_call_id", ""),
            ))
    return lc_messages


async def stream_agent_events(
        llm,
        input_messages: List[Dict[str, Any]],
        tools: List[Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """流式 Agent — DeepSeek V4 兼容版

    工具调用阶段用非流式 ainvoke（确保 reasoning_content 正确回传），
    最终回复阶段切 astream 逐 token 输出，保持前端流式体验。
    """
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)
    state = [dict(m) for m in input_messages]

    full_response = ""
    full_reasoning = ""

    try:
        for round_idx in range(5):
            lc_messages = _dicts_to_lc_messages(state)

            # 工具调用阶段：非流式，确保 reasoning_content 正确保留在消息中
            if round_idx < 4:
                response = await llm_with_tools.ainvoke(lc_messages)
            else:
                # 最后一轮兜底，理论上前面已结束
                response = await llm_with_tools.ainvoke(lc_messages)

            # 构建 assistant 消息，保活 reasoning_content
            assistant_dict: dict = {
                "role": "assistant",
                "content": response.content or "",
            }
            reasoning = (
                response.additional_kwargs.get("reasoning_content")
                if hasattr(response, "additional_kwargs")
                else None
            )
            if reasoning:
                assistant_dict["reasoning_content"] = reasoning
                full_reasoning += reasoning
                yield {"type": "reasoning", "data": reasoning}

            # 检查是否有工具调用
            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls:
                # 没有工具调用 → 最终回复，流式输出
                final_lc_messages = _dicts_to_lc_messages(state + [assistant_dict])
                async for chunk in llm_with_tools.astream(final_lc_messages):
                    if hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        yield {"type": "token", "data": chunk.content}
                state.append({"role": "assistant", "content": full_response})
                yield {
                    "type": "done",
                    "data": {
                        "display_content": full_response,
                        "reasoning_content": full_reasoning,
                    },
                }
                return

            # 有工具调用
            assistant_dict["tool_calls"] = tool_calls
            state.append(assistant_dict)

            for tc in tool_calls:
                # ToolCall 在 langchain-openai 0.1.x 中是 dict
                tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")

                yield {"type": "tool_start", "data": {"name": tc_name}}

                tool_func = tools_by_name.get(tc_name)
                if tool_func:
                    try:
                        result = await tool_func.ainvoke(tc_args)
                        result_str = result.content if hasattr(result, "content") else str(result)
                    except Exception as e:
                        result_str = f"工具执行出错: {e}"
                else:
                    result_str = f"未找到工具: {tc_name}"

                # 提取图片
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', result_str)
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', result_str)

                yield {
                    "type": "tool_end",
                    "data": {"name": tc_name, "output": clean_output},
                }

                state.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": clean_output,
                })

        # 超过最大轮次
        yield {"type": "error", "data": "工具调用超过最大轮次"}

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
