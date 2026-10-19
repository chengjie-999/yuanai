import os
import re
import json
import asyncio
from typing import List, AsyncGenerator, Dict, Any

from openai import AsyncOpenAI
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage,
)
from langchain_core.tools import BaseTool

from yuanai_core.core.lc import get_langgraph_agent, current_reasoning_effort
from yuanai_core.pure.dsml import DsmlStreamFilter


def _is_deepseek_v4(model_name: str) -> bool:
    # V4.1 Flash 新 ID 为 deepseek-flash（v4-flash 已退役路由至它）；v4-flash 保留兼容旧配置
    return model_name in ('deepseek-flash', 'deepseek-v4-flash', 'deepseek-v4-pro')


def _tool_output_str(output) -> str:
    """on_tool_end 的 output 归一化：LangGraph v2 给的是 ToolMessage 对象，
    str() 会带 content='...' 外壳（曾泄漏进工具卡并被模型复述）。"""
    if hasattr(output, "content"):
        c = output.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts = []
            for x in c:
                if isinstance(x, dict):
                    parts.append(str(x.get("text", "")))
                else:
                    parts.append(str(x))
            return "\n".join(parts)
        return str(c)
    return str(output or "")


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
            content = msg.content or ""
            # 保留 tool_calls（DeepSeek V4 路径需要）
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tc_list = []
                for tc in msg.tool_calls:
                    tc_dict = _tc_to_dict(tc)
                    tc_list.append(tc_dict)
                input_messages.append({"role": "assistant", "content": content, "tool_calls": tc_list})
            else:
                input_messages.append({"role": "assistant", "content": content})
        elif isinstance(msg, ToolMessage):
            input_messages.append({
                "role": "tool",
                "tool_call_id": getattr(msg, "tool_call_id", ""),
                "content": msg.content or "",
            })
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

    # 推理强度：显式传参 > 请求上下文（聊天框开关）> settings（修硬编码 low 吞掉
    # 用户「快答/深思」开关——DeepSeek V4 专用路径此前固定 low）
    _effort = ((getattr(llm, "extra_body", None) or {}).get("reasoning_effort")
               or current_reasoning_effort.get()
               or os.environ.get("REASONING_EFFORT", "low"))

    try:
        for round_idx in range(5):
            extra_body = {"reasoning_effort": _effort}

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
            # DSML 抑制：本轮 content/reasoning 各一路过滤器
            content_f = DsmlStreamFilter()
            reasoning_f = DsmlStreamFilter()

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # DeepSeek V4 特有字段，openai SDK ChoiceDelta 未定义该属性
                reasoning = getattr(delta, 'reasoning_content', None)
                if reasoning:
                    rclean = reasoning_f.feed(reasoning)
                    if rclean:
                        round_reasoning += rclean
                        full_reasoning += rclean
                        yield {"type": "reasoning", "data": rclean}

                if delta.tool_calls:
                    tool_call_chunks.append(delta.tool_calls[0])

                if delta.content:
                    clean = content_f.feed(delta.content)
                    if clean:
                        round_content += clean
                        yield {"type": "token", "data": clean}

            # 轮末 flush：把被暂扣的合法尾部吐出
            c_tail = content_f.flush()
            if c_tail:
                round_content += c_tail
                yield {"type": "token", "data": c_tail}
            r_tail = reasoning_f.flush()
            if r_tail:
                round_reasoning += r_tail
                full_reasoning += r_tail
                yield {"type": "reasoning", "data": r_tail}

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

                yield {"type": "tool_start", "data": {"name": tc_name, "sender": "orchestrator", "args": tc_args}}

                tool_func = tools_by_name.get(tc_name)
                if tool_func:
                    try:
                        result = await asyncio.wait_for(
                            tool_func.ainvoke(tc_args), timeout=120
                        )
                        result_str = result.content if hasattr(result, "content") else str(result)
                    except asyncio.TimeoutError:
                        result_str = f"工具 {tc_name} 执行超时（超过120秒）"
                    except Exception as e:
                        result_str = f"工具执行出错: {e}"
                else:
                    result_str = f"未找到工具: {tc_name}"

                # 提取图片
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', result_str)
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',?data:image/\w+;base64,[A-Za-z0-9+/=]+', '', result_str)

                yield {
                    "type": "tool_end",
                    "data": {"name": tc_name, "output": clean_output, "sender": "orchestrator"},
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": clean_output,
                })

        yield {"type": "error", "data": "工具调用超过最大轮次"}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("DeepSeek agent 流异常: %s", e, exc_info=True)
        yield {"type": "error", "data": str(e)}


# ——— DSML 流式抑制（DeepSeek 工具调用标记泄漏）———
# run_id → (content_filter, reasoning_filter)；LangGraph 流式路径共用
def dsml_filters() -> Dict[str, Any]:
    """创建空 filter 表（run_id → [DsmlStreamFilter, DsmlStreamFilter]）"""
    return {}


def _dsml_pair(filters: Dict[str, Any], run_id: str):
    from yuanai_core.pure.dsml import DsmlStreamFilter
    if run_id not in filters:
        filters[run_id] = [DsmlStreamFilter(), DsmlStreamFilter()]
    return filters[run_id]


def feed_dsml(filters: Dict[str, Any], run_id: str, kind: str, text: str) -> str:
    """喂入流式增量，返回清洗后文本（kind: content|reasoning）"""
    if not text:
        return ""
    pair = _dsml_pair(filters, run_id)
    return pair[0 if kind == "content" else 1].feed(text)


def flush_dsml(filters: Dict[str, Any], run_id: str, kind: str) -> str:
    """流结束 flush 尾部（BLOCK 态残留丢弃）"""
    pair = filters.get(run_id)
    return (pair[0 if kind == "content" else 1].flush()) if pair else ""


def dsml_saw_block(filters: Dict[str, Any], run_id: str) -> bool:
    """本轮是否剥过完整 DSML 工具调用块（配合『无结构化 tool_call 则报错』）"""
    pair = filters.get(run_id)
    return bool(pair and (pair[0].saw_block or pair[1].saw_block))


def limited_tools(tools: List[BaseTool], max_calls_per_tool: int = 3) -> List[BaseTool]:
    """同名工具单轮调用上限：超限不执行、返回引导语（防模型对失败/不存在的工具
    死循环重试——曾出现同一工具被连续调用 20+ 次）。包一层计数，工具本身不改。

    2026-10-19 修复：原实现只包 sync func——async-only 工具（delegate_to_claude_agent
    等）被 Agent 以 ainvoke 调用时走 sync 包装直接 NotImplementedError，Claude 委派
    整条链断。同时提供 func/coroutine 双路径，按调用方式正确转发。"""
    from langchain_core.tools import StructuredTool

    counts: Dict[str, int] = {}
    wrapped = []
    for t in tools:
        name = t.name
        counts[name] = 0

        def _guard(tname):
            if counts[tname] >= max_calls_per_tool:
                return (f"工具「{tname}」本轮已调用 {max_calls_per_tool} 次，"
                        "请停止重复调用，基于已有结果继续回答，或直接告诉用户结果。")
            counts[tname] += 1
            return None

        def make_run(inner, tname):
            def _run_tool(**kwargs):
                g = _guard(tname)
                if g is not None:
                    return g
                return inner.invoke(kwargs)
            return _run_tool

        def make_arun(inner, tname):
            async def _arun_tool(**kwargs):
                g = _guard(tname)
                if g is not None:
                    return g
                return await inner.ainvoke(kwargs)
            return _arun_tool

        wrapped.append(StructuredTool(
            name=t.name,
            description=t.description,
            args_schema=t.args_schema,
            func=make_run(t, name),
            coroutine=make_arun(t, name),
        ))
    return wrapped


async def stream_agent_events(
        llm,
        input_messages: List[Dict[str, Any]],
        tools: List[Any],
        max_tool_rounds: int = 8,
) -> AsyncGenerator[Dict[str, Any], None]:
    """流式 Agent 入口，DeepSeek V4 走专用通道。
    max_tool_rounds：LangGraph 路径的模型↔工具最大轮数（防工具循环跑满 25 步）"""
    model_name = llm.model_name if hasattr(llm, 'model_name') else ""

    if _is_deepseek_v4(model_name):
        async for event in _deepseek_agent_stream(llm, input_messages, tools, model_name):
            yield event
        return

    # Doubao 等模型：走原来的 LangGraph agent（recursion_limit 约束工具循环轮数）
    agent = get_langgraph_agent(llm, tools)
    config = {"recursion_limit": max_tool_rounds * 2 + 4}
    full_response = ""
    full_reasoning = ""
    filters = dsml_filters()   # DSML 抑制：run_id → (content, reasoning) 过滤器
    try:
        async for event in agent.astream_events({"messages": input_messages}, version="v2", config=config):
            run_id = event.get("run_id", "")
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    clean = feed_dsml(filters, run_id, "content", chunk.content)
                    if clean:
                        full_response += clean
                        yield {"type": "token", "data": clean}
                rc = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                if not rc:
                    rc = getattr(chunk, "reasoning_content", "")
                if rc:
                    rclean = feed_dsml(filters, run_id, "reasoning", rc)
                    if rclean:
                        full_reasoning += rclean
                        yield {"type": "reasoning", "data": rclean}
            elif event["event"] == "on_chat_model_end":
                tail = flush_dsml(filters, run_id, "content")
                if tail:
                    full_response += tail
                    yield {"type": "token", "data": tail}
                rtail = flush_dsml(filters, run_id, "reasoning")
                if rtail:
                    full_reasoning += rtail
                    yield {"type": "reasoning", "data": rtail}
            elif event["event"] == "on_tool_start":
                yield {"type": "tool_start", "data": {"name": event.get("name", "未知工具"), "sender": "orchestrator", "args": (event.get("data") or {}).get("input")}}
            elif event["event"] == "on_tool_end":
                output = _tool_output_str(event["data"].get("output", ""))
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', output)
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',?data:image/\w+;base64,[A-Za-z0-9+/=]+', '', output)
                yield {"type": "tool_end", "data": {"name": event.get("name", "未知工具"), "output": clean_output, "sender": "orchestrator"}}
        yield {
            "type": "done",
            "data": {"display_content": full_response, "reasoning_content": full_reasoning},
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("LangGraph agent 流异常: %s", e, exc_info=True)
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
        elif role == "tool":
            # 工具执行结果消息 — 保留在对话上下文中，让模型知道工具执行历史
            chat_history.append(ToolMessage(content=content, tool_call_id=""))
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
                rc = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                if not rc:
                    rc = getattr(chunk, "reasoning_content", "")
                if rc:
                    full_reasoning += rc
                    yield {"type": "reasoning", "data": rc}
            elif event["event"] == "on_tool_start":
                yield {"type": "tool_start", "data": {"name": event.get("name", "未知工具"), "sender": "orchestrator", "args": (event.get("data") or {}).get("input")}}
            elif event["event"] == "on_tool_end":
                output = _tool_output_str(event["data"].get("output", ""))
                img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', output)
                for img_url in img_urls:
                    yield {"type": "image", "data": img_url}
                clean_output = re.sub(r',?data:image/\w+;base64,[A-Za-z0-9+/=]+', '', output)
                yield {"type": "tool_end", "data": {"name": event.get("name", "未知工具"), "output": clean_output, "sender": "orchestrator"}}
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
                    yield {"type": "tool_start", "data": {"name": event.get("name", "未知工具"), "sender": "orchestrator", "args": (event.get("data") or {}).get("input")}}
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
