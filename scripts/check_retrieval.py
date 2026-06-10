import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.hr_assistant.utils.chroma_utils import hybrid_search as search

queries = [
    "公积金缴存比例",
    "出差住宿费标准",
    "年假政策",
    "员工招聘流程",
    "绩效考核怎么评",
    "因私出境手续",
]

for q in queries:
    print(f"\nQ: {q}")
    docs = search(q, k=3)
    for i, d in enumerate(docs):
        src = d.metadata.get("source", "")
        print(f"  [{i}] {src[-60:]} | {len(d.page_content)} chars")
        print(f"      {d.page_content[:120].replace(chr(10),' ')}")
