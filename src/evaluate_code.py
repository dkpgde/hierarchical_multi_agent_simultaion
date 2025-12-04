import json
import time
import asyncio
import os
import requests
import sys
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from mcp_client import mcp_server_context

SYSTEM_PROMPT = """You are an expert SCM Python Engineer.
Instead of calling tools one by one, you MUST write a Python script to solve the user's problem.

You have access to a tool called `execute_python_code`.
Inside this tool, the following functions are ALREADY available (do not import them):
- get_part_id(name) -> str
- get_stock_level(id) -> str
- get_supplier_location(id) -> str
- get_shipping_cost(city) -> str

STRATEGY:
1. Write a SINGLE script that chains these calls together.
2. Use variables to store results (e.g., `pid = get_part_id("Engine")`).
3. Use `print()` to output the final answer.
"""

ANSWERS_FILE = "../test/answers_code_granite.json"
MODEL_NAME = "granite4:tiny-h"

def load_test_cases():
    with open('../test/test_set.json', 'r') as f: return json.load(f)

def log_debug(logs, case, actual, status, duration, input_tokens, output_tokens, total_tokens):
    previous_total_time = sum(item.get("duration_seconds", 0) for item in logs)
    total_accumulated_time = previous_total_time + duration

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
    # --- 1. Determine Start ID ---
    start_id = 1
    if len(sys.argv) > 1:
        try:
            start_id = int(sys.argv[1])
            print(f"Resuming evaluation from Question ID: {start_id}")
        except ValueError:
            print("Invalid start ID provided. Usage: python evaluate_code.py [start_id]")
            return

    cases = load_test_cases()
    logs = []

    # --- 2. Load and Filter Existing Logs ---
    if os.path.exists(ANSWERS_FILE):
        try:
            with open(ANSWERS_FILE, 'r') as f:
                logs = json.load(f)
            print(f"Loaded {len(logs)} existing answers from {ANSWERS_FILE}")
            
            original_count = len(logs)
            logs = [l for l in logs if l['id'] < start_id]
            
            if len(logs) < original_count:
                print(f"Truncated logs to {len(logs)} entries (keeping IDs < {start_id})")
                
        except json.JSONDecodeError:
            print("Could not parse existing answers file. Starting fresh.")
            logs = []
    
    # --- 3. Filter Cases to Run ---
    cases_to_run = [c for c in cases if c['id'] >= start_id]
    
    if not cases_to_run:
        print("No questions left to evaluate based on start ID.")
        return

    print(f"Evaluating {len(cases_to_run)} cases in CODE MODE ({MODEL_NAME})...")
    
    async with mcp_server_context(mode="code") as agent:
        for case in cases_to_run:
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

                # Sum usage from all AI messages (intermediate steps + final answer)
                for msg in history:
                    if isinstance(msg, AIMessage):
                        meta = msg.usage_metadata or {}
                        calc_input_tokens += meta.get("input_tokens", 0)
                        calc_output_tokens += meta.get("output_tokens", 0)
                        calc_total_tokens += meta.get("total_tokens", 0)
                
                # Fallback if metadata is missing (e.g. older Ollama versions)
                if calc_total_tokens == 0:
                    print("Warning: usage_metadata missing. Counts may be 0.")

                final_msg = history[-1]
                final_out = str(final_msg.content)
                
                # Validation Logic
                exp = case["expected"].lower()
                status = "FAIL"
                
                if exp in final_out.lower():
                    status = "PASS"
                elif "refusal" in exp and any(x in final_out.lower() for x in ["cannot", "sorry", "scope", "unable"]):
                    status = "PASS (Refusal)"
                
                print(f"   -> {status} (Time: {duration:.2f}s | Tokens: {calc_total_tokens})")
                
                log_debug(logs, case, final_out, status, duration, calc_input_tokens, calc_output_tokens, calc_total_tokens)
                
            except Exception as e:
                print(f"   -> CRASH: {e}")
                log_debug(logs, case, str(e), "CRASH", 0, 0, 0, 0)

    passed = len([l for l in logs if "PASS" in l["status"]])
    print("\n" + "="*50)
    print(f"Code Mode Evaluation Complete. Score: {passed}/{len(logs)}")
    print(f"Detailed logs saved to {ANSWERS_FILE}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())