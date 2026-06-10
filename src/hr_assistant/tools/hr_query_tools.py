"""
Text-to-SQL 工具 — Function Calling 双工具模式
"""
import re
import json
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.hr_assistant.config import LLM_CONFIG, HR_SQL_EXAMPLES, SALARY_SQL_EXAMPLES
from src.hr_assistant.utils.db_utils import execute_hr_query, execute_salary_query, format_query_result
from src.hr_assistant.utils.sql_logger import log_sql

HR_SCHEMA_DEEP = """
## 人事库 (cyj_ehr_pro)
hi_psndoc(人员档案): id/psn_name/sex/age/nation/polity/mobile_phone/email
hi_psn_job(任职): psndoc_id→hi_psndoc.id, org_id→sys_org_.id, dept_id→sys_dept_.id, psn_state(HRHI0301=在职/0302=离职/0303=退休), on_job_class(HRHI0209=返聘), job_name, in_duty_date, com_age
sys_org_(公司/组织): id/org_name/org_code/pid(上级组织ID)/org_level(层级)/status('Y'=有效)  ← 查下级: WHERE pid = (SELECT id FROM sys_org_ WHERE org_name='XX')
sys_dept_(部门): id/dept_name/org_id  ← 查"部门""处室""科室"用这个表
sys_dictionary(字典): dtype/dkey/dvalue
hi_psndoc_edu(教育): psndoc_id, education(HRHI13), school, is_top_edu
hi_psndoc_title(职称): psndoc_id, title_name, title_level(HRHI17), approve_date
"""

SALARY_SCHEMA_DEEP = """
## 薪酬库 (cyj_ehr_wa)
wa_person(薪酬人员): id/psn_name/wa_flag(01=在薪)/dept_id
wa_data(工资宽表): wa_person_id, salary_pay_period(YYYYMM), cost_ta(应发), cost_tr(实发), cost_pt(个税), base_salary, cost_ei2(养老个人), cost_mi2(医疗个人), cost_hf2(公积金个人)
wa_insurances_fund_month_detail(社保明细): org_name/dept_name/psn_name/psn_code, cost_hf1(公积金基数), cost_hf2(公积金合计), cost_mi2(医疗个人)
wa_pay_grant(发放): salary_pay_period, pay_date, pay_person_num
"""

FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
                       "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "LOAD"]


def _clean_output(raw: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"```sql\s*|```", "", cleaned)
    return cleaned.strip().rstrip(";")


def _validate_sql(sql: str) -> tuple[bool, str]:
    if not sql or not sql.upper().strip().startswith("SELECT"):
        return False, "非 SELECT 语句"
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(r'\b' + kw + r'\b', sql.upper()):
            return False, f"包含禁止关键字 {kw}"
    return True, ""


def _generate_sql(question: str, schema: str, examples: str) -> str:
    """调用 LLM 生成 SQL"""
    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=0,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是 MySQL 专家。根据表结构和示例生成一条 SELECT。
{schema}
## 铁律：
1. 只输出纯SELECT，禁止解释/注释
2. 禁止GROUP BY/COUNT/SUM，除非用户要统计
3. 查人用 p.psn_name='姓名'，不是LIKE
4. 默认 psn_state='HRHI0301'
5. 禁止擅自加日期/部门等用户未提的条件
{examples}"""),
        ("human", "{question}"),
    ])
    chain = prompt | llm | StrOutputParser()
    for _ in range(3):
        raw = chain.invoke({"question": question, "schema": schema, "examples": examples})
        sql = _clean_output(raw)
        if not sql:
            continue
        has_user_date = bool(re.search(r'\d{4}\s*年|\d{4}[-/]\d{1,2}', question))
        if not has_user_date:
            sql = re.sub(r"\s+AND\s+in_duty_date\s*[<>=!]+\s*'[^']*'", "", sql, flags=re.IGNORECASE)
        valid, _ = _validate_sql(sql)
        if valid:
            return sql
    return ""


@tool
def query_hr(question: str) -> str:
    """查询人事数据（员工信息、部门、组织架构、人数统计、学历、职称、考核等）。
    适用于：查某人信息、某部门有哪些人、各部门人数、学历分布、职称查询、在职统计、党员统计等。
    参数 question: 自然语言问题，如"全集团总人数""张三在哪个部门""各部门人数统计"
    """
    sql = _generate_sql(question, HR_SCHEMA_DEEP, HR_SQL_EXAMPLES)
    if not sql:
        return "SQL 生成失败，请换个说法"
    try:
        rows = execute_hr_query(sql)
        result = format_query_result(rows)
        log_sql(question, sql, result)
        return f"查询结果：\n{result}\n（SQL: {sql}）"
    except Exception as e:
        log_sql(question, sql, error=str(e)[:300])
        return f"查询出错: {str(e)[:300]}"


@tool
def query_salary(question: str) -> str:
    """查询薪酬/社保/公积金数据（工资、个税、社保缴费、公积金、发薪记录等）。
    适用于：某人某月工资明细、某月工资总额、社保公积金缴纳金额、公积金基数排名等。
    参数 question: 自然语言问题，如"杨紫2026年5月工资""公积金缴费基数最高的前10人""2026年5月实发工资总额"
    """
    sql = _generate_sql(question, SALARY_SCHEMA_DEEP, SALARY_SQL_EXAMPLES)
    if not sql:
        return "SQL 生成失败，请换个说法"
    try:
        rows = execute_salary_query(sql)
        result = format_query_result(rows)
        log_sql(question, sql, result)
        return f"查询结果：\n{result}\n（SQL: {sql}）"
    except Exception as e:
        log_sql(question, sql, error=str(e)[:300])
        return f"查询出错: {str(e)[:300]}"


@tool
def generate_hr_sql(question: str) -> str:
    """用自然语言生成人事库SQL查询语句（仅生成不执行）。"""
    sql = _generate_sql(question, HR_SCHEMA_DEEP, HR_SQL_EXAMPLES)
    return sql if sql else "生成失败"


@tool
def generate_salary_sql(question: str) -> str:
    """用自然语言生成薪酬库SQL查询语句（仅生成不执行）。"""
    sql = _generate_sql(question, SALARY_SCHEMA_DEEP, SALARY_SQL_EXAMPLES)
    return sql if sql else "生成失败"


@tool
def execute_sql(sql: str) -> str:
    """执行一条SQL查询并返回结果。自动选择人事库或薪酬库（根据SQL表名判断）。
    参数 sql: 要执行的SQL语句"""
    if "wa_" in sql.lower():
        try:
            rows = execute_salary_query(sql)
        except Exception as e:
            return f"执行出错: {str(e)[:300]}"
    else:
        try:
            rows = execute_hr_query(sql)
        except Exception as e:
            return f"执行出错: {str(e)[:300]}"
    return format_query_result(rows)
