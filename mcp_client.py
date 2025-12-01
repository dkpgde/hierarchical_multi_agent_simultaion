import asyncio
import sys
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Annotated, TypedDict, Type, Any

from pydantic import BaseModel, Field, create_model
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langchain_ollama import ChatOllama

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL_NAME = "qwen2.5:14b"
SERVER_SCRIPT = "mcp_server.py"

def jsonschema_to_pydantic(name: str, schema: dict) -> Type[BaseModel]:
    fields = {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict
    }

    for field_name, detail in properties.items():
        json_type = detail.get("type", "string")
        py_type = type_map.get(json_type, str)
        
        is_required = field_name in required
        default = ... if is_required else None
        
        description = detail.get("description", "")
        fields[field_name] = (py_type, Field(default=default, description=description))

    return create_model(name, **fields)

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

@asynccontextmanager
async def mcp_server_context() -> AsyncGenerator:
    if not os.path.exists(SERVER_SCRIPT):
        raise FileNotFoundError(f"Server script not found: {SERVER_SCRIPT}")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env=env
    )

    print(f"Connecting to MCP Server ({SERVER_SCRIPT})...")
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                mcp_tools = await session.list_tools()
                langchain_tools = []

                for tool in mcp_tools.tools:
                    def create_tool_wrapper(tool_name):
                        async def wrapper(**kwargs):
                            return await session.call_tool(tool_name, arguments=kwargs)
                        return wrapper

                    args_schema = jsonschema_to_pydantic(f"{tool.name}Schema", tool.inputSchema)

                    langchain_tools.append(StructuredTool.from_function(
                        func=None,
                        coroutine=create_tool_wrapper(tool.name),
                        name=tool.name,
                        description=tool.description,
                        args_schema=args_schema
                    ))
                
                print(f"Loaded {len(langchain_tools)} tools with schemas.")

                llm = ChatOllama(model=MODEL_NAME, temperature=0, num_ctx=4096)
                llm_with_tools = llm.bind_tools(langchain_tools)

                def agent_node(state: AgentState):
                    return {"messages": [llm_with_tools.invoke(state["messages"])]}

                workflow = StateGraph(AgentState)
                workflow.add_node("agent", agent_node)
                workflow.add_node("tools", ToolNode(langchain_tools))
                
                workflow.add_edge(START, "agent")
                workflow.add_conditional_edges("agent", tools_condition)
                workflow.add_edge("tools", "agent")

                agent = workflow.compile()
                yield agent

    except Exception as e:
        print(f"\nError: {e}")
        raise

async def run_agent_interactive():
    async with mcp_server_context() as agent:
        print("Ready. Type 'quit' to exit.")
        while True:
            user_input = input("\nUser: ")
            if user_input.lower() in ["quit", "exit"]: break
            
            inputs = {"messages": [HumanMessage(content=user_input)]}
            async for chunk in agent.astream(inputs, stream_mode="values"):
                message = chunk["messages"][-1]
                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tc in message.tool_calls:
                        print(f"Tool call: {tc['name']}({tc['args']})")
                elif message.type == "ai":
                    print(f"Agent: {message.content}")

if __name__ == "__main__":
    try:
        asyncio.run(run_agent_interactive())
    except KeyboardInterrupt:
        pass