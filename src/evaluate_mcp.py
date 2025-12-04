import json
import time
import asyncio
import os
# requests is no longer needed for token counting
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from mcp_client import mcp_server_context

ANSWERS_FILE = "../test/answers_mcp_qwen.json"
MODEL_NAME = "qwen2.5:14B"

# REVISED SYSTEM PROMPT
SYSTEM_PROMPT = """You are an expert SCM Assistant. 
You have access to specific tools to find Part IDs, check stock, and calculate shipping.

CRITICAL RULES:
1. You MUST use the provided tools to get real data. DO NOT guess or hallucinate IDs.
2. Always search for the **Part ID** first using `find_part_id`.
3. To find shipping, you must first find the supplier city for that ID, then calculate shipping for that city.
4. Do not describe what you are doing. Just execute the tool calls.
"""

def load_test_cases():
    with open('../test/test_set.json', 'r') as f: return json.load(f)

def log_debug(logs, case, actual, status, duration, input_tokens, output_tokens, total_tokens):
    # Calculate Cumulative Time
    previous_total_time = sum(item.get("duration_seconds", 0) for item in logs)
    total_accumulated_time = previous_total_time + duration

    # Calculate Cumulative Tokens
    previous_total_tokens = sum(item.get("total_tokens", 0) for item in logs)
    total_accumulated_tokens = previous_total_tokens + total_tokens

    entry = {
        "id": case['id'], 
        "q": case['q'], 
        "exp": case['expected'], 
        "act": actual, 
        "status": status,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cumulative_total_tokens": total_accumulated_tokens, # New field
        "duration_seconds": round(duration, 2),
        "cumulative_time_seconds": round(total_accumulated_time, 2)
    }
    
    logs.append(entry)
    with open(ANSWERS_FILE, 'w') as f: json.dump(logs, f, indent=2)

async def run_evaluation():
    if os.path.exists(ANSWERS_FILE): os.remove(ANSWERS_FILE)
    cases = load_test_cases()
    logs = []
    
    print(f"Evaluating {len(cases)} cases against MCP Agent ({MODEL_NAME})...")
    
    # Default is mode="standard"
    async with mcp_server_context(mode="standard") as agent:
        for case in cases:
            print(f"\nRunning Q{case['id']}: {case['q']}")
            start = time.time()
            
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=case["q"])
            ]
            
            try:
                # Agent invoke
                result = await agent.ainvoke({"messages": messages})
                duration = time.time() - start

                # --- Token Counting Logic (Metadata Based) ---
                history = result["messages"]
                
                calc_input_tokens = 0
                calc_output_tokens = 0
                calc_total_tokens = 0

                # Sum usage from all AI messages (intermediate tool calls + final answer)
                for msg in history:
                    if isinstance(msg, AIMessage):
                        meta = msg.usage_metadata or {}
                        calc_input_tokens += meta.get("input_tokens", 0)
                        calc_output_tokens += meta.get("output_tokens", 0)
                        calc_total_tokens += meta.get("total_tokens", 0)
                
                if calc_total_tokens == 0:
                    print("Warning: usage_metadata missing. Counts may be 0.")

                final_msg = history[-1]
                final_out = str(final_msg.content)
                
                # Validation Logic
                exp = case["expected"].lower()
                status = "FAIL"
                
                if exp in final_out.lower():
                    status = "PASS"
                
                print(f"   -> {status} (Time: {duration:.2f}s | Tokens: {calc_total_tokens})")
                
                log_debug(
                    logs, 
                    case, 
                    final_out, 
                    status, 
                    duration, 
                    calc_input_tokens, 
                    calc_output_tokens, 
                    calc_total_tokens
                )
                
            except Exception as e:
                print(f"   -> CRASH: {e}")
                log_debug(logs, case, str(e), "CRASH", 0, 0, 0, 0)

    passed = len([l for l in logs if "PASS" in l["status"]])
    print("\n" + "="*50)
    print(f"Evaluation Complete. Score: {passed}/{len(cases)}")
    print(f"Detailed logs saved to {ANSWERS_FILE}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())