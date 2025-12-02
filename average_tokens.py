import json
import os

DATA_FILE = 'answers_code_granite.json'   

def calculate_average_tokens(filepath: str) -> float:
    if not os.path.exists(filepath):
        print(f"Error: File not found at '{filepath}'")
        return 0.0

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{filepath}'. Ensure the file is valid JSON.")
        return 0.0
    except Exception as e:
        print(f"An unexpected error occurred while reading the file: {e}")
        return 0.0

    if not isinstance(data, list):
        print(f"Error: Expected a JSON list/array, but found type {type(data)}.")
        return 0.0
        
    total_sum = 0.0
    count = 0
    
    for item in data:
        if isinstance(item, dict) and 'total_tokens' in item:
            try:
                total_sum += float(item['total_tokens'])
                count += 1
            except ValueError:
                print(f"'total_tokens' value '{item['total_tokens']}' is not a valid number. Skipping this entry.")
                
    if count == 0:
        print("No valid 'total_tokens' entries found to calculate an average.")
        return 0.0
    
    average = total_sum / count
    return average

if __name__ == "__main__":   
    avg = calculate_average_tokens(DATA_FILE)
    
    if avg > 0.0:
        print(f"\n--- Analysis Results ---")
        print(f"The average of total_tokens is: {avg:.2f}")
        print(f"------------------------\n")