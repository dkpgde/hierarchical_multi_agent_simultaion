4 tools in all scenarios.    
Interested in agents for on-device use cases. Results don't generalize for bigger models/toolsets.   
For this simplistic use, clearly the complexity of hierarchical agents or code mode MCP is counterproductive.  

Code mode MCP:  
[Granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models): 68% success rate; 515 seconds; 38k tokens.  

Default MCP:  
[Granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models): 91% success rate; 439 seconds; 46k tokens. 
[Qwen 2.5 14B](https://huggingface.co/collections/Qwen/qwen25): 84% success rate; 1216 seconds; 59k tokens.  

Orchestrator + 2 workers:
Using [granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models).
Success rate 59%; dragged down by longer tasks.

