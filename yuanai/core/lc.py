from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from yuanai.tools import all_tools as tools
from utils.sensitive_data import get_api_key
import sys


# LLM初始化
def get_llm(model='deepseek-chat', **kwargs):
    dsllm = ['deepseek-chat', 'deepseek-coder', 'deepseek-reasoner']
    dsmm = ['deepseek-vl2']
    if model in dsllm:
        model_type = 'dsllm'
        ds_api_key = get_api_key(model_type)
        return ChatOpenAI(
            api_key=ds_api_key,
            base_url="https://api.deepseek.com/v1",
            model=model,
            **kwargs,
        )
    elif model in dsmm:
        model_type = 'dsmm'
        ds_api_key = get_api_key(model_type)
        return ChatOpenAI(
            api_key=ds_api_key,
            base_url="https://api.deepseek.com/v1",
            model=model,
            **kwargs,
        )
    else:
        raise ValueError(f"无效的model值：{model}")


def get_prompt():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个能调用工具的助手"),
        MessagesPlaceholder(variable_name="chat_history"),  # 可选：保留对话历史
        ("user", "{input}"),  # 正确：变量名改为 input（和调用时一致）
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    return prompt


# Agent和执行器
def get_agent_executor(llm, tools, prompt):
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        # callbacks=[CustomStdOutCallbackHandler()],
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=True
    )


# 对外统一接口
def ai_with_tools(question: str):
    llm = get_llm(
        'deepseek-chat',
        temperature=1,
        verbose=False
    )
    prompt = get_prompt()
    agent_executor = get_agent_executor(llm, tools, prompt)
    try:
        result = agent_executor.invoke({
            "input": question,
            "agent_scratchpad": [],
            "chat_history": []  # 添加这一行
        })
        return result["output"]
    except Exception as e:
        print(f"❌ 调用出错：{str(e)}", file=sys.stderr)
        return f"抱歉，处理你的问题时出错了：{str(e)}"


# 测试
if __name__ == "__main__":
    print(ai_with_tools("北京今天多少度？再算 100+200"))
