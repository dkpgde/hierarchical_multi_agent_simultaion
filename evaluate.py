import json
import logging
import os
import time  # Added import
import pytest

from agent_graph import run_hierarchical_agent
from benchmark import count_tokens

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Eval")

ANSWERS_FILE = "answers_orchestration.json"

def load_test_cases():
    with open('test_set.json', 'r') as f: return json.load(f)

def log_debug(case, actual, status, output_tokens=0, duration=0.0, msg=""):
    """Writes down the answers with timing metrics"""
    logs = []
    if os.path.exists(ANSWERS_FILE):
        try:
            with open(ANSWERS_FILE, 'r') as f: logs = json.load(f)
        except: pass
    
    # Calculate total time so far (sum of previous durations + current)
    previous_total = sum(item.get("duration_seconds", 0) for item in logs)
    total_accumulated = previous_total + duration

    entry = {
        "id": case['id'], 
        "q": case['q'], 
        "exp": case['expected'], 
        "act": actual, 
        "status": status,
        "output_tokens": output_tokens,
        "duration_seconds": round(duration, 2),        # Specific time per question
        "cumulative_time_seconds": round(total_accumulated, 2), # Total time running count
        "err": msg
    }
    
    logs.append(entry)
    with open(ANSWERS_FILE, 'w') as f: json.dump(logs, f, indent=2)

@pytest.fixture(scope="session", autouse=True)
def clear_log():
    if os.path.exists(ANSWERS_FILE): os.remove(ANSWERS_FILE)

@pytest.mark.parametrize("case", load_test_cases())
def test_supervisor_agent(case):
    """Main test code"""
    print(f"\nRunning Q{case['id']}: {case['q']}")
    
    final_out = ""
    out_tokens = 0
    start_time = time.time() # Start timer
    
    try:
        final_out, history = run_hierarchical_agent(case["q"])
        out_tokens = count_tokens(final_out) 
    except Exception as e:
        duration = time.time() - start_time
        log_debug(case, str(e), "CRASH", 0, duration, str(e))
        pytest.fail(f"Agent Crashed: {e}")

    duration = time.time() - start_time # End timer
    exp = case["expected"].lower()
    
    if exp in final_out.lower():
        log_debug(case, final_out, "PASS", out_tokens, duration)
    else:
        msg = f"Missing keyword '{exp}'"
        log_debug(case, final_out, "FAIL", out_tokens, duration, msg)
        pytest.fail(msg)