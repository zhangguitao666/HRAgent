"""
干部简历查询 API — Dify 同款流水线: 参数提取 → SQL生成 → SQL校验 → DB查询 → LLM呈现
"""
import re
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.hr_assistant.config import LLM_CONFIG
from src.hr_assistant.utils.db_utils import execute_hr_query

router = APIRouter()

# ── Dify 同款 Schema（与 YML 中 context_node 完全一致）──
RESUME_SCHEMA = """## 表结构
- hi_psndoc (人员基本档案): id, org_id, dept_id, psn_name, psn_code, sex, in_work_date
- hi_psn_job (人员工作信息): psndoc_id, job_name, psn_state, is_main_job
- sys_org_ (组织): id, org_code, org_name
- sys_dept_ (部门): id, dept_code, dept_name
- sys_dictionary (字典项): dkey, dtype, dvalue

## 关联
- hi_psndoc.org_id = sys_org_.id
- hi_psndoc.dept_id = sys_dept_.id
- hi_psndoc.id = hi_psn_job.psndoc_id
- 性别: hi_psndoc.sex = sys_dictionary.dkey AND sys_dictionary.dtype = 'HRHI09'
- 在职状态: hi_psn_job.psn_state = sys_dictionary.dkey AND sys_dictionary.dtype = 'HRHI03'
- 业务常量: 在职=HRHI0301, 离职=HRHI0302, 主要职务 is_main_job='Y'"""

# ── Dify 同款 SQL 生成 Prompt ──
SQL_GENERATION_PROMPT = """你是SQL生成器。根据用户问题中的姓名，生成查询干部信息的MySQL语句。
必须使用cyj_ehr_pro库的真实表字段。
只需输出结构化JSON：{{"sql":"...","reason":"..."}}。其中reason说明查询依据。
禁止Markdown、禁止代码块、禁止解释性前后缀。"""

# ── Dify 同款结果呈现 Prompt ──
PRESENTATION_PROMPT = """你是人事数据展现助手。
将查询结果整理为Markdown表格，表格必须包含以下列：姓名、性别、员工编码、工作单位、部门、在职状态、简历链接。
链接格式：[查看简历](https://hr-pre.cyj.cn/resume/index?id={{psndoc_id}}&orgId={{org_id}})
直接输出Markdown表格，不要任何JSON包裹或解释。"""

# ── 危险关键字（与 Dify sql_guard 一致）──
FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "truncate", "create", "replace"
]


class ResumeLookupRequest(BaseModel):
    query: str  # 用户输入，如 "查张三的简历" / "张三"


def extract_and_validate_sql(llm_output: str) -> dict:
    """
    Dify 同款 SQL 校验逻辑（与 sql_guard_node 代码完全一致）：
    1. 从 LLM 输出中提取 JSON
    2. 校验必须为 SELECT
    3. 校验无危险关键字
    4. 校验无多语句
    """
    # ── Step 1: 清理 LLM 输出，提取 JSON ──
    raw = (llm_output or "").strip()
    raw = re.sub(r'^```[a-zA-Z]*\n', '', raw)
    raw = re.sub(r'```$', '', raw).strip()

    obj = {}
    try:
        obj = json.loads(raw)
    except Exception:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                pass

    sql = (obj.get("sql", "") if isinstance(obj, dict) else "").strip().rstrip(";")
    reason = (obj.get("reason", "") if isinstance(obj, dict) else "")

    # ── Step 2: 如果 JSON 提取失败，尝试正则提取 SELECT ──
    if not sql:
        m = re.search(r'(?is)select\b[\s\S]*', raw)
        if m:
            sql = m.group(0).strip()

    if not sql:
        return {
            "validated_sql": "SELECT 'SQL生成失败，请重新提问' AS error_message",
            "generated_sql": "",
            "sql_reason": reason,
            "validation_passed": False,
            "validation_message": "未能提取SQL",
        }

    s = sql.strip().rstrip(";")
    low = " " + s.lower() + " "

    # ── Step 3: 必须为 SELECT ──
    if not low.strip().startswith("select "):
        return {
            "validated_sql": "SELECT '仅允许SELECT' AS error_message",
            "generated_sql": sql,
            "sql_reason": reason,
            "validation_passed": False,
            "validation_message": "仅允许SELECT语句",
        }

    # ── Step 4: 危险关键字检查 ──
    for b in FORBIDDEN_KEYWORDS:
        if " " + b + " " in low:
            return {
                "validated_sql": "SELECT '命中危险关键字' AS error_message",
                "generated_sql": sql,
                "sql_reason": reason,
                "validation_passed": False,
                "validation_message": f"命中危险关键字: {b}",
            }

    # ── Step 5: 多语句检查 ──
    if ";" in s:
        return {
            "validated_sql": "SELECT '不允许多语句' AS error_message",
            "generated_sql": sql,
            "sql_reason": reason,
            "validation_passed": False,
            "validation_message": "不允许多语句",
        }

    return {
        "validated_sql": s,
        "generated_sql": sql,
        "sql_reason": reason,
        "validation_passed": True,
        "validation_message": "ok",
    }


def format_query_result(rows: list[dict]) -> str:
    """将数据库查询结果格式化为 Markdown 文本（模拟 Dify db_query 的 markdown 输出）"""
    if not rows:
        return "未查询到数据"

    lines = []
    # 表头
    headers = list(rows[0].keys())
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join([" --- "] * len(headers)) + "|")
    # 数据行
    for row in rows:
        vals = [str(v) if v is not None else "" for v in row.values()]
        lines.append("| " + " | ".join(vals) + " |")

    return "\n".join(lines)


async def resume_lookup_stream(query: str):
    """
    Dify 流水线完整实现：
    Step 1: 参数提取 → 从 query 获取姓名
    Step 2: SQL 生成 → LLM 根据 Schema 生成 SQL
    Step 3: SQL 校验 → 安全检查（SELECT only, 无危险关键字, 无多语句）
    Step 4: 数据库查询 → 执行校验后的 SQL
    Step 5: LLM 呈现 → 将原始结果格式化为含简历链接的 Markdown 表格
    """
    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=0.1,
    )

    # ── Step 1: 提取姓名参数 ──
    yield {"type": "progress", "step": "param_extract", "content": f"识别参数: {query}"}

    # ── Step 2: LLM 生成 SQL ──
    yield {"type": "progress", "step": "sql_generate", "content": "正在生成 SQL 查询..."}

    sql_prompt = ChatPromptTemplate.from_messages([
        ("system", SQL_GENERATION_PROMPT),
        ("human", """用户问题: {query}

表结构摘要: {schema}

要求：根据用户问题中的人名查询人员信息。
返回字段包括：id(别名psndoc_id)、org_id、dept_id、psn_name(别名姓名)、psn_code(别名员工编码)、sex(关联字典HRHI09输出中文别名性别)、sys_org_.org_name(别名工作单位)、sys_dept_.dept_name(别名部门)、hi_psn_job.psn_state(关联字典HRHI03输出中文别名在职状态)。
必须 LEFT JOIN sys_org_ ON org_id、sys_dept_ ON dept_id、hi_psn_job ON psndoc_id AND is_main_job='Y'。
查询条件使用 psn_name IN ('姓名')。
仅输出JSON对象：{{"sql":"...","reason":"..."}}"""),
    ])

    chain = sql_prompt | llm | StrOutputParser()
    llm_output = chain.invoke({"query": query, "schema": RESUME_SCHEMA})
    # 清理 think 标签
    llm_output = re.sub(r"<think>.*?</think>", "", llm_output, flags=re.DOTALL).strip()

    yield {"type": "progress", "step": "sql_generated", "content": f"SQL 原始输出: {llm_output[:200]}"}

    # ── Step 3: SQL 校验 ──
    validation = extract_and_validate_sql(llm_output)
    yield {
        "type": "progress",
        "step": "sql_validate",
        "content": f"校验结果: {validation['validation_message']}",
        "sql": validation["generated_sql"],
        "reason": validation["sql_reason"],
        "validation_passed": validation["validation_passed"],
    }

    if not validation["validation_passed"]:
        yield {"type": "error", "content": validation["validation_message"]}
        yield {"type": "done"}
        return

    # ── Step 4: 数据库查询 ──
    yield {"type": "progress", "step": "db_query", "content": f"执行 SQL: {validation['validated_sql'][:300]}"}

    try:
        rows = execute_hr_query(validation["validated_sql"])
        raw_result = format_query_result(rows)
        yield {"type": "progress", "step": "db_result", "content": f"查询到 {len(rows)} 条记录"}
    except Exception as e:
        yield {"type": "error", "content": f"数据库查询失败: {str(e)[:300]}"}
        yield {"type": "done"}
        return

    # ── Step 5: LLM 呈现结果 ──
    yield {"type": "progress", "step": "llm_present", "content": "正在整理结果..."}

    present_prompt = ChatPromptTemplate.from_messages([
        ("system", PRESENTATION_PROMPT),
        ("human", """用户问题: {query}

生成SQL: {generated_sql}

SQL校验: {validation_passed} / {validation_message}

SQL查询结果:
{raw_result}

请将查询结果整理为Markdown表格，表格必须包含以下列：姓名、性别、员工编码、工作单位、部门、在职状态、简历链接。
链接格式：[查看简历](https://hr-pre.cyj.cn/resume/index?id={{psndoc_id}}&orgId={{org_id}})
直接输出Markdown表格，不要任何JSON包裹或解释。"""),
    ])

    present_chain = present_prompt | llm | StrOutputParser()
    final_answer = present_chain.invoke({
        "query": query,
        "generated_sql": validation["generated_sql"],
        "validation_passed": validation["validation_passed"],
        "validation_message": validation["validation_message"],
        "raw_result": raw_result,
    })
    # 清理 think 标签
    final_answer = re.sub(r"<think>.*?</think>", "", final_answer, flags=re.DOTALL).strip()

    # 流式输出最终答案
    for char in final_answer:
        yield {"type": "token", "content": char}
        await asyncio.sleep(0)

    yield {"type": "done"}


@router.post("/lookup")
async def resume_lookup(req: ResumeLookupRequest):
    """干部简历查询（Dify 流水线）"""
    async def stream():
        try:
            async for chunk in resume_lookup_stream(req.query):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)[:300]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
