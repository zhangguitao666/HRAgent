import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.hr_assistant.config import RERANKER_CONFIG
from openai import OpenAI

client = OpenAI(
    api_key=RERANKER_CONFIG["api_key"],
    base_url=RERANKER_CONFIG["base_url"],
)

q = "绩效考核怎么评"
docs = ["绩效考核管理办法总则", "员工培训教育管理办法", "出差休假管理办法"]

r = client.embeddings.create(
    model=RERANKER_CONFIG["model"],
    input=[q] + docs,
)

# Dump raw response
print(type(r))
print(dir(r))
print(r.model_dump() if hasattr(r, 'model_dump') else "no model_dump")
print("---")
if hasattr(r, 'data'):
    for i, d in enumerate(r.data):
        print(f"[{i}] index={d.index if hasattr(d,'index') else '?'}, ", end="")
        if hasattr(d, 'relevance_score'):
            print(f"score={d.relevance_score}", end="")
        print()
        if hasattr(d, 'model_extra'):
            print(f"     extra={d.model_extra}")
