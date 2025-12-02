4 tools in all scenarios.    
Interested in agents for on-device use cases. Results don't generalize for bigger models/toolsets.   
For this simplistic use, clearly the complexity of hierarchical agents or code mode MCP is counterproductive.  

Code mode MCP:  
[Granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models): 68% success rate; 515 seconds.  
[Qwen 2.5 14B](https://huggingface.co/collections/Qwen/qwen25): Fails, crashes, or takes too long. Testing abandoned.

Default MCP:  
[Granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models): 91% success rate; 455 seconds.  
[Qwen 2.5 14B](https://huggingface.co/collections/Qwen/qwen25): 86% success rate; 1139.41 seconds.  

Orchestrator + 2 workers:
Using [granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models).
Success rate 59%; dragged down by longer tasks.

WIP: Monitoring total token usage