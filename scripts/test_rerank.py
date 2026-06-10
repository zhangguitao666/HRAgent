import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.hr_assistant.utils.chroma_utils import rerank, hybrid_search

q = "绩效考核怎么评"
docs = hybrid_search(q, k=10)
print(f"Candidates: {len(docs)}")
for i, d in enumerate(docs):
    print(f"  [{i}] {d.metadata.get('source','')[-50:]} | {len(d.page_content)}c")

ranked = rerank(q, docs, top_n=3)
print(f"\nReranked (top 3):")
for i, d in enumerate(ranked):
    print(f"  [{i}] {d.metadata.get('source','')[-50:]} | {len(d.page_content)}c")
