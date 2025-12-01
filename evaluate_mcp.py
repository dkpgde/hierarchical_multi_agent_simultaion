import json
import time
import asyncio
import os
import requests
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from mcp_client import mcp_server_context

ANSWERS_FILE = "answers_mcp_qwen.json"
MODEL_NAME = "qwen2.5:14b"
OLLAMA_TOKENIZE_URL = "http://localhost:11434/api/tokenize"

SYSTEM_PROMPT = """You are an expert SCM Assistant. 
You have access to specific tools to find Part IDs, check stock, and calculate shipping.

CRITICAL RULES:
1. You MUST use the provided tools to get real data. DO NOT guess or hallucinate IDs.
2. Always search for the **Part ID** first using `find_part_id`.
3. To find shipping, you must first find the supplier city for that ID, then calculate shipping for that city.
4. Do not describe what you are doing. Just execute the tool calls.
"""

def count_tokens(text: str) -> int:
    try:
        response = requests.post(
            OLLAMA_TOKENIZE_URL,
            json={"model": MODEL_NAME, "prompt": str(text)}
        )
        return len(response.json().get("tokens", []))
    except:
        return len(str(text).split()) * 1.5

def load_test_cases():
    with open('test_set.json', 'r') as f: return json.load(f)

def log_debug(logs, case, actual, status, duration, input_tokens, output_tokens):
    previous_total = sum(item.get("duration_seconds", 0) for item in logs)
    total_accumulated = previous_total + duration

    entry = {
        "id": case['id'], 
        "q": case['q'], 
        "exp": case['expected'], 
        "act": actual, 
        "status": status,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "duration_seconds": round(duration, 2),
        "cumulative_time_seconds": round(total_accumulated, 2)
    }
    
    logs.append(entry)
    with open(ANSWERS_FILE, 'w') as f: json.dump(logs, f, indent=2)

async def run_evaluation():
    if os.path.exists(ANSWERS_FILE): os.remove(ANSWERS_FILE)
    cases = load_test_cases()
    logs = []
    
    print(f"Evaluating {len(cases)} cases against MCP Agent ({MODEL_NAME})...")
    
    async with mcp_server_context() as agent:
        for case in cases:
            print(f"\nRunning Q{case['id']}: {case['q']}")
            start = time.time()
            
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=case["q"])
            ]
            
            input_content = SYSTEM_PROMPT + case["q"]
            input_tokens = count_tokens(input_content)
            
            try:
                result = await agent.ainvoke({"messages": messages})
                final_msg = result["messages"][-1]
                final_out = str(final_msg.content)
                
                output_tokens = count_tokens(final_out)
                duration = time.time() - start
                
                exp = case["expected"].lower()
                status = "FAIL"
                
                if exp in final_out.lower():
                    status = "PASS"
                elif "refusal" in exp and any(x in final_out.lower() for x in ["cannot", "sorry", "scope", "unable"]):
                    status = "PASS (Refusal)"
                
                print(f"   -> {status} (Time: {duration:.2f}s)")
                log_debug(logs, case, final_out, status, duration, input_tokens, output_tokens)
                
            except Exception as e:
                print(f"   -> CRASH: {e}")
                log_debug(logs, case, str(e), "CRASH", 0, 0, 0)

    passed = len([l for l in logs if "PASS" in l["status"]])
    print("\n" + "="*50)
    print(f"Evaluation Complete. Score: {passed}/{len(cases)}")
    print(f"Detailed logs saved to {ANSWERS_FILE}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())