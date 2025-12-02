import asyncio
import sys
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Annotated, TypedDict, Type, Any

from pydantic import BaseModel, Field, create_model
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_ollama import ChatOllama

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL_NAME = "qwen2.5:14B"
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
async def mcp_server_context(mode: str = "standard") -> AsyncGenerator:
    if not os.path.exists(SERVER_SCRIPT):
        raise FileNotFoundError(f"Server script not found: {SERVER_SCRIPT}")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env=env
    )

    print(f"Connecting to MCP Server ({SERVER_SCRIPT}) in {mode.upper()} mode...")
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                mcp_tools = await session.list_tools()
                langchain_tools = []

                for tool in mcp_tools.tools:
                    if mode == "standard" and tool.name == "execute_python_code":
                        continue
                        
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
                
                print(f"Loaded {len(langchain_tools)} tools.")

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

async def run_interactive(mode="standard"):
    """Interactive test mode without a system prompt"""   
    async with mcp_server_context(mode=mode) as agent:
        print(f"{mode.title()} Mode Ready. Type 'quit' to exit.")
        
        while True:
            user_input = input(f"\n({mode}) User: ")
            if user_input.lower() in ["quit", "exit"]: break
            
            messages = [
                HumanMessage(content=user_input)
            ]
            
            print("Thinking", end="", flush=True)
            
            async for chunk in agent.astream({"messages": messages}, stream_mode="values"):
                message = chunk["messages"][-1]
                
                if hasattr(message, "tool_calls") and message.tool_calls:
                    print() 
                    for tc in message.tool_calls:
                        if tc['name'] == 'execute_python_code':
                            print(f" Generating Code")
                        else:
                            print(f"Tool call: {tc['name']}({tc['args']})")
                            
                elif message.type == "ai" and not message.tool_calls:
                    print(f"\rAgent: {message.content}")

if __name__ == "__main__":
    try:
        print("Select Mode:")
        print("1. Standard (Chain of Thought / Step-by-Step Tools)")
        print("2. Code Mode (Write & Execute Python Scripts)")
        choice = input("Choice (1/2): ").strip()
        
        mode = "code" if choice == "2" else "standard"
        asyncio.run(run_interactive(mode))
    except KeyboardInterrupt:
        pass