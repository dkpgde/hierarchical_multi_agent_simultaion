4 tools in all scenarios.    

Default MCP:  
[Granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models): 77.3% success rate; 455 seconds; 157 avg tokens per question.
[Qwen 2.5 14B](https://huggingface.co/collections/Qwen/qwen25): 84.1% success rate; 1139.41 seconds; 159 avg tokens per question.  

Orchestrator + 2 workers:
Using [granite4:tiny-h by IBM](https://huggingface.co/collections/ibm-granite/granite-40-language-models).
Success rate 59%; dragged down by longer tasks.


WIP: Benchmarking traiditional MCP vs code mode MCP.