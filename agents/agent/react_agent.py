from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from agents.model.factory import chat_model
from agents.utils.prompt_loader import load_system_prompts
from agents.tools.agent_tools import (rag_summarize, get_weather, get_user_location)
from agents.tools.middleware import monitor_tool, log_before_model
from agents.rag.vector_store import VectorStoreService


class ReactAgent:
    def __init__(self):
        # 启动时加载知识库，MD5去重，已加载的自动跳过
        VectorStoreService().load_document()

        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_summarize, get_weather, get_user_location],
            middleware=[monitor_tool, log_before_model],
        )

    def execute_stream(self, messages: list[dict]):
        input_dict = {"messages": messages}
        for chunk in self.agent.stream(input_dict, stream_mode="values"):
            latest_message = chunk["messages"][-1]
            # 仅输出最终回答：必须是 AI 消息且不含工具调用。
            # 过滤掉 ReAct 中间思考（带 tool_calls 的 AIMessage）与工具返回结果（ToolMessage），
            # 避免把「检索知识库」等内部过程暴露给用户。
            if not isinstance(latest_message, AIMessage) or getattr(latest_message, "tool_calls", None):
                continue
            if latest_message.content:
                yield latest_message.content.strip() + "\n"