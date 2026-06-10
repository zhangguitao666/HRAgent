import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.hr_assistant.config import RERANKER_CONFIG
import requests

url = RERANKER_CONFIG["base_url"]
key = RERANKER_CONFIG["api_key"]
model = RERANKER_CONFIG["model"]

q = "绩效考核怎么评"
docs = ["绩效考核管理办法总则", "员工培训教育管理办法", "出差休假管理办法"]

# Try different API paths
paths = ["/v1/rerank", "/rerank", "/v1/embeddings", ""]
for path in paths:
    full_url = url.rstrip("/") + path
    try:
        r = requests.post(
            full_url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "query": q, "documents": docs},
            timeout=10,
        )
        print(f"[{path}] status={r.status_code}")
        if r.status_code == 200:
            print(f"  body: {r.text[:500]}")
        else:
            print(f"  error: {r.text[:200]}")
    except Exception as e:
        print(f"[{path}] error: {e}")
