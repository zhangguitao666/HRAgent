"""
会话测试 — 验证意图识别、知识库召回、回答准确性
"""
import os
import sys
import json
import time
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from src.hr_assistant.utils.chroma_utils import search

API = "http://localhost:8001/api/chat/ask"

def ask(question, session="test_session"):
    """同步调用流式 API，收集完整回答"""
    r = requests.post(API, json={"question": question, "session_id": session}, stream=True)
    answer = ""
    thinking = []
    for line in r.iter_lines():
        if not line:
            continue
        try:
            line = line.decode("utf-8")
        except:
            continue
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if data.get("type") == "token":
                answer += data.get("content", "")
            elif data.get("type") == "progress":
                thinking = data.get("thinking", [])
            elif data.get("type") == "done":
                thinking = data.get("thinking", [])
    return answer.strip(), thinking


def clean(s):
    return re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()


KB_TESTS = [
    # (query, expected_keywords, category)
    ("出差住宿费标准是多少",       ["500元", "350元", "一线"],    "出差休假"),
    ("年假有多少天",               ["5天", "10天", "15天", "年假"], "出差休假"),
    ("公积金缴存比例",             ["公积金", "比例", "%", "缴存"], "公积金"),
    ("员工绩效考核怎么评",         ["绩效", "考核", "评分", "等级"], "绩效考核"),
    ("企业年金怎么缴纳",           ["年金", "缴纳", "比例"],        "企业年金"),
    ("因私出境需要什么手续",       ["出境", "审批", "申请"],        "因私出境"),
    ("招聘流程是怎样的",           ["招聘", "面试", "录用", "调配"], "招聘调配"),
    ("干部选拔怎么监督",           ["干部", "监督", "责任"],         "干部督查"),
    ("组织机构是如何设置的",       ["组织", "机构", "部门", "管理"], "组织机构"),
    ("住房保障有哪些",             ["住房", "保障", "公积金"],        "住房保障"),
    ("教育培训有什么规定",         ["培训", "教育", "预算"],         "教育培训"),
    ("病假工资怎么发",             ["病假", "80%", "证明"],          "出差休假"),
]

DB_TESTS = [
    ("全集团在职有多少人",          "人事"),
    ("查询杨紫的工资",              "薪酬"),
]

print("=" * 60)
print("HR 智能助手 — 会话测试")
print("=" * 60)

results = []
passed = 0
failed = 0

def record(tag, question, status, answer_preview, detail=""):
    results.append({"tag": tag, "question": question, "status": status, "answer": answer_preview, "detail": detail})
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{icon}] {tag} | {question}")
    if status == "FAIL":
        print(f"        → {detail}")

# ---------- 知识库测试 ----------
print("\n[1] 知识库 FAQ 测试 (12 项)")
print("-" * 40)

for question, keywords, category in KB_TESTS:
    try:
        answer, thinking = ask(question)
        answer_clean = clean(answer)
        
        # 检查意图识别：工具调用应包含 query_faq
        tool_names = [t.get("content", "") for t in thinking if t.get("type") == "tool_call"]
        is_faq_tool = any("query_faq" in tn for tn in tool_names)
        
        # 检查 KB 语义召回是否命中
        docs = search(question, k=3)
        has_docs = len(docs) > 0
        
        # 检查回答是否含有关键词
        kw_hit = sum(1 for kw in keywords if kw in answer_clean)
        
        if is_faq_tool and has_docs and kw_hit >= 1:
            record(category, question, "PASS", answer_clean[:100])
            passed += 1
        else:
            reasons = []
            if not is_faq_tool: reasons.append("未调用query_faq")
            if not has_docs: reasons.append("KB未召回到内容")
            if kw_hit == 0: reasons.append(f"回答不含关键词{keywords[:3]}")
            record(category, question, "FAIL", answer_clean[:100], "; ".join(reasons))
            failed += 1
    except Exception as e:
        record(category, question, "FAIL", str(e)[:100], f"异常: {str(e)[:200]}")
        failed += 1

# ---------- 数据库意图测试 ----------
print("\n[2] 数据库意图路由测试 (2 项)")
print("-" * 40)

for question, expected_db in DB_TESTS:
    try:
        answer, thinking = ask(question)
        answer_clean = clean(answer)
        
        tool_names = [t.get("content", "") for t in thinking if t.get("type") == "tool_call"]
        if expected_db == "人事":
            is_correct = any("query_hr" in tn for tn in tool_names)
        else:
            is_correct = any("query_salary" in tn for tn in tool_names)
        
        # 至少收到了回答
        has_answer = len(answer_clean) > 10
        
        if is_correct and has_answer:
            record("数据路由", question, "PASS", answer_clean[:100])
            passed += 1
        else:
            reasons = []
            if not is_correct: reasons.append(f"未路由到{expected_db}库")
            if not has_answer: reasons.append("未收到有效回答")
            record("数据路由", question, "FAIL", answer_clean[:100], "; ".join(reasons))
            failed += 1
    except Exception as e:
        record("数据路由", question, "FAIL", str(e)[:100], f"异常: {str(e)[:200]}")
        failed += 1

# ---------- 结果汇总 ----------
total = passed + failed
rate = (passed / total * 100) if total > 0 else 0
print(f"\n{'='*60}")
print(f"总计: {total} 项 | 通过: {passed} | 失败: {failed} | 通过率: {rate:.1f}%")
print(f"{'='*60}")

# 输出详细报告
print("\n详细结果:")
for r in results:
    tag = f"[{r['tag']}]" if r['status'] == 'PASS' else f"[{r['tag']}] FAIL"
    print(f"  {r['status']:4s} {tag:20s} {r['question']}")
    if r['status'] == 'FAIL':
        print(f"         {r['detail']}")
        print(f"         A: {r['answer'][:150]}")

# 保存报告
report = {
    "summary": {"total": total, "passed": passed, "failed": failed, "rate": f"{rate:.1f}%"},
    "categories": {
        "KB_test": {"count": len(KB_TESTS), "passed": sum(1 for r in results if "KB" not in r['tag'] and r['status'] == 'PASS') if False else sum(1 for r in results[:-2] if r['status'] == 'PASS')},
        "DB_route": {"count": len(DB_TESTS), "passed": sum(1 for r in results[-2:] if r['status'] == 'PASS')},
    },
    "details": results,
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
}

report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "kb-test-report.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"# 知识库会话测试报告\n\n")
    f.write(f"**测试时间**: {report['timestamp']}\n\n")
    f.write(f"**测试环境**: minimax-m2.5, BGE-M3+ChromaDB (101 chunks, 10 docs)\n\n")
    f.write(f"## 测试结果\n\n")
    f.write(f"| 维度 | 总计 | 通过 | 失败 | 通过率 |\n")
    f.write(f"|------|------|------|------|--------|\n")
    f.write(f"| 总计 | {total} | {passed} | {failed} | {rate:.1f}% |\n\n")
    f.write(f"## 知识库 FAQ 测试\n\n")
    f.write(f"| # | 问题 | 结果 | 回答摘要 |\n")
    f.write(f"|---|------|------|----------|\n")
    for i, r in enumerate(results[:-2], 1):
        status = "✅" if r['status'] == 'PASS' else "❌"
        f.write(f"| {i} | {r['question']} | {status} | {r['answer'][:80]}... |\n")
    f.write(f"\n## 数据库意图路由测试\n\n")
    f.write(f"| # | 问题 | 结果 | 回答摘要 |\n")
    f.write(f"|---|------|------|----------|\n")
    for i, r in enumerate(results[-2:], len(results)-1):
        status = "✅" if r['status'] == 'PASS' else "❌"
        f.write(f"| {i} | {r['question']} | {status} | {r['answer'][:80]}... |\n")
    f.write(f"\n## 失败详情\n\n")
    for r in results:
        if r['status'] == 'FAIL':
            f.write(f"- **{r['question']}**: {r['detail']}\n")

print(f"\n报告已保存: {report_path}")
