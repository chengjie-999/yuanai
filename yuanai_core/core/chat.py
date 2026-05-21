import re
import json
from typing import List, AsyncGenerator, Dict, Any

from openai import AsyncOpenAI
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage,
)
from langchain_core.tools import BaseTool

from yuanai_core.core.lc import get_langgraph_agent


def _is_deepseek_v4(model_name: str) -> bool:
    return model_name in ('deepseek-v4-flash', 'deepseek-v4-pro')


def _convert_tools_to_openai(tools: List[BaseTool]) -> list:
    result = []
    for t in tools:
        params = {}
        if t.args_schema:
            try:
                params = t.args_schema.model_json_schema()
            except Exception:
                try:
                    params = t.args_schema.schema()
                except Exception:
                    params = {}
        result.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": params,
            },
        })
    return result


def _tc_to_dict(tc) -> dict:
    """将 ToolCall 对象/字典标准化为 dict"""
    if isinstance(tc, dict):
        return tc
    d = {"id": getattr(tc, "id", ""), "type": "function"}
    fn = {"name": getattr(tc, "name", "")}
    args = getattr(tc, "args", {})
    fn["arguments"] = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
    d["function"] = fn
    return d


def build_input_messages(
        prompt: str,
        images_base64: List[str],
        history: List[BaseMessage],
        system_message: SystemMessage,
) -> List[Dict[str, Any]]:
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
            content.append({"type": "image_url", "image_url": {"url": img}})
        input_messages.append({"role": "user", "content": content})
    else:
        input_messages.append({"role": "user", "content": prompt})
    return input_messages


async def _deepseek_agent_stream(
        llm,
        input_messages: List[Dict[str, Any]],
        tools: List[BaseTool],
        model_name: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """DeepSeek V4 专用 agent：用 openai 客户端直接控制消息格式"""
    api_key = llm.openai_api_key.get_secret_value() if hasattr(llm.openai_api_key, 'get_secret_value') else str(llm.openai_api_key)
    base_url = llm.openai_api_base if hasattr(llm, 'openai_api_base') else "https://api.deepseek.com/beta"
    temperature = llm.temperature if hasattr(llm, 'temperature') else 0.7

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    openai_tools = _convert_tools_to_openai(tools)
    tools_by_name = {t.name: t for t in tools}

    messages = [dict(m) for m in input_messages]
    full_reasoning = ""

    try:
        for round_idx in range(5):
            extra_body = {"reasoning_effort": "low"}

            # 流式调用，逐 token 输出思考过程
            stream = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=openai_tools or None,
                temperature=temperature,
                extra_body=extra_body,
                stream=True,
            )

            assistant: dict = {"role": "assistant", "content": ""}
            round_reasoning = ""
            round_content = ""
            tool_call_chunks: list = []

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.reasoning_content:
                    round_reasoning += delta.reasoning_content
                    full_reasoning += delta.reasoning_content
                    yield {"type": "reasoning", "data": delta.reasoning_content}

                if delta.tool_calls:
                    tool_call_chunks.append(delta.tool_calls[0])

                if delta.content:
                    round_content += delta.content
                    yield {"type": "token", "data": delta.content}

            # 合并 tool_call chunks 为完整 tool_calls
            if tool_call_chunks:
                merged_calls = []
                for tc_delta in tool_call_chunks:
                    idx = getattr(tc_delta, 'index', 0)
                    while len(merged_calls) <= idx:
                        merged_calls.append({
                            "id": "", "type": "function",
                            "function": {"name": "", "arguments": ""},
                        })
                    if getattr(tc_delta, 'id', None):
                        merged_calls[idx]["id"] = tc_delta.id
                    fn = getattr(tc_delta, 'function', None)
                    if fn:
                        if getattr(fn, 'name', None):
                            merged_calls[idx]["function"]["name"] = fn.name
                        if getattr(fn, 'arguments', None):
                            merged_calls[idx]["function"]["arguments"] += fn.arguments

                assistant["tool_calls"] = merged_calls
                assistant["content"] = None
            else:
                assistant["content"] = round_content

            if round_reasoning:
                assistant["reasoning_content"] = round_reasoning

            messages.append(assistant)

            if not tool_call_chunks:
                # 没有工具调用，最终回复已流式输出完毕
                yield {
                    "type": "done",
                    "data": {
                        "display_content": round_content,
                        "reasoning_content": full_reasoning,
                    },
                }
                return

            # 执行工具
            for tc in assistant["tool_calls"]:
                fn = tc.get("function", tc) if isinstance(tc, dict) else getattr(tc, "function", tc)
                tc_name = fn.get("name", "") if isinstance(fn, dict) else getattr(fn, "name", "")
                tc_args_raw = fn.get("arguments", "{}") if isinstance(fn, dict) else getattr(fn, "arguments", "{}")
                tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")

                if isinstance(tc_args_raw, str):
                    try:
                        tc_args = json.loads(tc_args_raw)
                    except json.JSONDecodeError:
                        tc_args = tc_args_raw
                else:
                    tc_args = tc_args_raw

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

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": clean_output,
                })

        yield {"type": "error", "data": "工具调用超过最大轮次"}

    except Exception as e:
        yield {"type": "error", "data": str(e)}


async def stream_agent_events(
        llm,
        input_messages: List[Dict[str, Any]],
        tools: List[Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """流式 Agent 入口，DeepSeek V4 走专用通道"""
    model_name = llm.model_name if hasattr(llm, 'model_name') else ""

    if _is_deepseek_v4(model_name):
        async for event in _deepseek_agent_stream(llm, input_messages, tools, model_name):
            yield event
        return

    # Doubao 等模型：走原来的 LangGraph agent
    agent = get_langgraph_agent(llm, tools)
    full_response = ""
    full_reasoning = ""
    try:
        async for event in agent.astream_events({"messages": input_messages}, version="v2"):
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
                output = event["data"].get("output", "")
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', str(output))
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
                yield {"type": "tool_end", "data": {"name": event.get("name", "未知工具"), "output": clean_output}}
        yield {
            "type": "done",
            "data": {"display_content": full_response, "reasoning_content": full_reasoning},
        }
    except Exception as e:
        yield {"type": "error", "data": str(e)}


def parse_session_message(msg) -> tuple:
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
    chat_history = []
    for msg in session_messages:
        role, content, images, reasoning_content = parse_session_message(msg)
        if role == "user":
            if images:
                content_list = [{"type": "text", "text": content}]
                for img in images:
                    content_list.append({"type": "image_url", "image_url": {"url": img}})
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
        llm, messages: List[BaseMessage], tools: List[Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    agent = get_langgraph_agent(llm, tools)
    full_response = ""
    full_reasoning = ""
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
                output = event["data"].get("output", "")
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', str(output))
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
                yield {"type": "tool_end", "data": {"name": event.get("name", "未知工具"), "output": clean_output}}
        yield {
            "type": "done",
            "data": {"display_content": full_response, "reasoning_content": full_reasoning},
        }
    except Exception as e:
        yield {"type": "error", "data": str(e)}


async def stream_agent_with_inject(
        llm, initial_messages: List[BaseMessage], tools: List[Any],
        on_tool_end, max_rounds: int = 3,
) -> AsyncGenerator[Dict[str, Any], None]:
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
        yield {"type": "done", "data": {"display_content": full_response, "reasoning_content": full_reasoning}}
        return
    yield {"type": "error", "data": f"已达到最大轮次({max_rounds})，可能仍未获取完整题目"}
