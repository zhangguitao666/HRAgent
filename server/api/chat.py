"""
统一对话 API - Function Calling 多工具 Agent（自动识别意图：FAQ/数据查询/简历/入转调离）
"""
import re
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.hr_assistant.config import LLM_CONFIG
from src.hr_assistant.utils.chroma_utils import smart_search

router = APIRouter()

_sessions = {}

SYSTEM_PROMPT = """你是企业 HR 智能助手，**必须严格按照规则调用工具，禁止不调工具直接回答**。

## 工具选择规则（严格按优先级）：

### 第一优先级：制度政策类 → 必须调用 query_faq
以下任何问题都必须调用 query_faq：
- 公司制度、政策、规定、管理办法 → query_faq
- 年假、病假、婚假、产假、事假、调休、考勤 → query_faq
- 加班规定、出差标准、报销流程 → query_faq
- 公积金政策、社保政策、年金政策、住房政策 → query_faq
- 培训制度、绩效考核办法、奖惩制度 → query_faq
- 招聘流程、入职手续、离职规定 → query_faq
- 组织机构说明、干部管理、因私出境 → query_faq

### 第二优先级：查人简历 → 调用 lookup_resume
- 查某人简历、查看某人信息、调取某人简历 → lookup_resume
- 搜索某人、查找某干部 → lookup_resume
- 注意：和 query_hr 的区别是 lookup_resume 返回带简历链接的结果

### 第三优先级：人事数据查询 → 调用 query_hr
- 查人员信息（某人在哪个部门、学历、职称等）
- 查部门/组织人数统计、离职率等
- 查学历分布、年龄分布、性别统计等

### 第四优先级：薪酬数据查询 → 调用 query_salary
- 查某人员工工资、社保缴费
- 查某月工资总额、平均工资

### 第五优先级：简历解析 → parse_resume
### 第六优先级：入转调离流程 → lifecycle_guide

## 铁律：
1. 制度政策类问题不调 query_faq = 你的回答没有任何依据 = 你错了
2. 查某人简历必须调 lookup_resume
3. 数据查询必须先调工具，禁止猜数据
4. 不确定时优先调 query_faq
5. 简洁回答，不输出 SQL"""


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"


def _get_session_history(session_id: str) -> list:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


async def _run_agent_stream(session_id: str, question: str):
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI
    from langchain_core.tools import tool
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    from src.hr_assistant.tools.hr_query_tools import query_hr, query_salary

    # --- FAQ 工具（RAG 检索增强） ---
    @tool
    def query_faq(faq_question: str) -> str:
        """查询公司制度/政策/规定。适用于：考勤制度、请假规定、年假政策、加班规定、出差报销、五险一金政策、薪资结构说明等。
        参数 faq_question: 员工关于公司制度的自然语言问题"""
        docs = smart_search(faq_question, k=3)
        if not docs:
            return "知识库中暂无相关制度信息，建议联系 HR 部门确认。"

        context = "\n\n---\n\n".join(d.page_content for d in docs)
        llm_faq = ChatOpenAI(
            model=LLM_CONFIG["model"],
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
            temperature=0.3,
        )
        from langchain_core.output_parsers import StrOutputParser
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是公司HR智能助手。根据以下制度材料回答问题。如果材料中没有相关信息，如实告知不要编造。\n\n材料：\n{context}"),
            ("human", "{input}"),
        ])
        chain = prompt | llm_faq | StrOutputParser()
        return chain.invoke({"context": context, "input": faq_question})

    # --- 简历解析工具 ---
    @tool
    def parse_resume(resume_text: str) -> str:
        """解析简历文本，提取候选人关键信息（姓名、学历、经验、技能等）。
        参数 resume_text: 完整的简历文本内容"""
        try:
            from src.hr_assistant.tools.resume_tool import parse_resume as _resume_parse
            return _resume_parse.invoke({"resume_text": resume_text})
        except Exception as e:
            return f"简历解析失败：{str(e)}"

    # --- 入转调离工具 ---
    @tool
    def lifecycle_guide(flow_type: str, user_context: str = "") -> str:
        """引导员工办理入职/转正/离职/退休流程。
        参数 flow_type: 流程类型，onboarding(入职)/regularization(转正)/resignation(离职)/retirement(退休)
        参数 user_context: 员工当前状态或问题"""
        life_prompts = {
            "onboarding": """你是HR入职引导助手。引导新员工完成入职流程：
1. 提交入职材料（身份证、学历证、离职证明）
2. 签订劳动合同
3. 办理社保/公积金
4. 开通企业邮箱/门禁
5. 领取办公设备
请根据用户问题逐步引导，每次只给下一步建议。""",
            "regularization": """你是HR转正引导助手。引导员工完成转正流程：
1. 试用期考核评估
2. 填写转正申请表
3. 部门负责人审批
4. HR审核
5. 签订正式合同
请根据用户问题逐步引导。""",
            "resignation": """你是HR离职引导助手。引导员工完成离职流程：
1. 提交离职申请
2. 工作交接
3. 归还公司资产
4. HR办理离职手续
5. 开具离职证明
请根据用户问题逐步引导。""",
            "retirement": """你是HR退休引导助手。引导员工完成退休流程：
1. 确认退休条件
2. 整理退休材料
3. 办理社保转移
4. 领取退休金
请根据用户问题逐步引导。"""
        }
        sys_prompt = life_prompts.get(flow_type, life_prompts["onboarding"])
        llm_life = ChatOpenAI(
            model=LLM_CONFIG["model"],
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
            temperature=0.3,
        )
        from langchain_core.output_parsers import StrOutputParser
        prompt = ChatPromptTemplate.from_messages([
            ("system", sys_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm_life | StrOutputParser()
        ctx = user_context or flow_type
        return chain.invoke({"input": ctx})

    # --- 干部简历查询工具（Dify 流水线：SQL生成→校验→查询→呈现） ---
    @tool
    def lookup_resume(name: str) -> str:
        """根据姓名查询干部简历信息，生成可点击的简历查看链接。
        适用场景：查某人的简历、调取某人档案、查看某干部信息等。
        参数 name: 人员姓名，如"张三""杨幂"等"""
        import re as _re
        import json as _json
        from src.hr_assistant.utils.db_utils import execute_hr_query

        # Step 1: SQL 生成
        schema = """## 表结构
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

        llm_sql = ChatOpenAI(model=LLM_CONFIG["model"], api_key=LLM_CONFIG["api_key"],
                             base_url=LLM_CONFIG["base_url"], temperature=0.1)
        sql_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是SQL生成器。根据用户问题中的姓名，生成查询干部信息的MySQL语句。只需输出JSON：{{"sql":"...","reason":"..."}}。禁止Markdown。"""),
            ("human", """用户问题: 查{name}的简历

表结构摘要: {schema}

要求：返回字段包括：id(别名psndoc_id)、org_id、dept_id、psn_name(别名姓名)、psn_code(别名员工编码)、sex(关联字典HRHI09输出中文别名性别)、sys_org_.org_name(别名工作单位)、sys_dept_.dept_name(别名部门)、hi_psn_job.psn_state(关联字典HRHI03输出中文别名在职状态)。
必须 LEFT JOIN sys_org_ ON org_id、sys_dept_ ON dept_id、hi_psn_job ON psndoc_id AND is_main_job='Y'。
查询条件: psn_name IN ('{name}')。仅输出JSON。"""),
        ])
        raw = sql_prompt | llm_sql | StrOutputParser()
        llm_output = raw.invoke({"name": name, "schema": schema})
        llm_output = _re.sub(r"<think>.*?</think>", "", llm_output, flags=_re.DOTALL).strip()

        # Step 2: SQL 校验
        obj = {}
        raw2 = _re.sub(r'^```[a-zA-Z]*\n', '', llm_output)
        raw2 = _re.sub(r'```$', '', raw2).strip()
        try:
            obj = _json.loads(raw2)
        except Exception:
            m = _re.search(r'\{[\s\S]*\}', raw2)
            if m:
                try: obj = _json.loads(m.group(0))
                except: pass
        sql = (obj.get("sql", "") if isinstance(obj, dict) else "").strip().rstrip(";")
        if not sql:
            m = _re.search(r'(?is)select\b[\s\S]*', raw2)
            if m: sql = m.group(0).strip()
        if not sql or not sql.lower().strip().startswith("select "):
            return "SQL 生成失败，请重新输入姓名"

        # Step 3: 数据查询
        try:
            rows = execute_hr_query(sql)
            if not rows:
                return f"未找到 {name} 的信息"
        except Exception as e:
            return f"查询失败: {str(e)[:200]}"

        # Step 4: 生成 Markdown 表格
        headers = list(rows[0].keys())
        lines = []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join([" --- "] * len(headers)) + "|")
        for row in rows:
            vals = [str(v) if v is not None else "" for v in row.values()]
            lines.append("| " + " | ".join(vals) + " |")
        raw_result = "\n".join(lines)

        # Step 5: LLM 呈现
        llm_present = ChatOpenAI(model=LLM_CONFIG["model"], api_key=LLM_CONFIG["api_key"],
                                 base_url=LLM_CONFIG["base_url"], temperature=0.1)
        present_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是人事数据展现助手。将查询结果整理为Markdown表格，表格必须包含：姓名、性别、员工编码、工作单位、部门、在职状态、简历链接。链接格式：[查看简历](https://hr-pre.cyj.cn/resume/index?id={{psndoc_id}}&orgId={{org_id}})。直接输出表格。"""),
            ("human", """用户问题: 查{name}的简历

SQL查询结果:
{raw_result}

请整理为Markdown表格，简历链接格式：[查看简历](https://hr-pre.cyj.cn/resume/index?id={{psndoc_id}}&orgId={{org_id}})。"""),
        ])
        final = present_prompt | llm_present | StrOutputParser()
        answer = final.invoke({"name": name, "raw_result": raw_result})
        answer = _re.sub(r"<think>.*?</think>", "", answer, flags=_re.DOTALL).strip()
        if not answer:
            return raw_result
        return answer

    # --- 构建 Agent ---
    tools = [query_hr, query_salary, query_faq, lookup_resume, parse_resume, lifecycle_guide]

    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=0,
    )

    llm_with_tools = llm.bind_tools(tools)
    agent = create_react_agent(llm_with_tools, tools, prompt=SYSTEM_PROMPT)

    history = _get_session_history(session_id)
    input_messages = history + [("user", question)]

    thinking = []
    pending_tools = 0
    can_emit = False
    final_answer = ""
    token_buf = ""
    in_think = False

    async for event in agent.astream_events(
        {"messages": input_messages}, version="v2",
    ):
        kind = event.get("event", "")

        if kind == "on_tool_start":
            pending_tools += 1
            can_emit = False
            tool_name = event.get("name", "")
            tool_input = event.get("data", {}).get("input", {})
            desc = ""
            if tool_name == "query_faq":
                desc = tool_input.get("faq_question", "")
            elif tool_name == "parse_resume":
                desc = "解析简历内容"
            elif tool_name == "lifecycle_guide":
                desc = f"{tool_input.get('flow_type', '')}流程"
            elif tool_name in ("query_hr", "query_salary"):
                desc = tool_input.get("question", "")
            thinking.append({"type": "tool_call", "content": f"{tool_name}: {desc[:200]}"})
            yield {"type": "progress", "thinking": list(thinking)}

        if kind == "on_tool_end":
            pending_tools -= 1
            if pending_tools == 0:
                can_emit = True
            output = event.get("data", {}).get("output", "")
            if output is not None:
                output_str = output.content if hasattr(output, "content") else str(output)
                result_match = re.search(r"共 (\d+) 条记录", output_str)
                if result_match:
                    thinking.append({"type": "result", "content": f"返回 {result_match.group(1)} 条记录"})
                if "出错" in output_str or "失败" in output_str:
                    thinking.append({"type": "error", "content": output_str[:200]})
                yield {"type": "progress", "thinking": list(thinking)}

        if kind == "on_chat_model_stream" and can_emit:
            chunk = event.get("data", {}).get("chunk", {})
            if hasattr(chunk, "content") and chunk.content:
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    continue
                token_buf += chunk.content

                if "<think>" in token_buf and not in_think:
                    in_think = True
                    parts = token_buf.split("<think>", 1)
                    if parts[0].strip():
                        yield {"type": "token", "content": parts[0]}
                        final_answer += parts[0]
                    token_buf = parts[1] if len(parts) > 1 else ""

                if in_think and "</think>" in token_buf:
                    parts = token_buf.split("</think>", 1)
                    think_content = parts[0].strip()
                    if think_content:
                        thinking.append({"type": "think", "content": think_content[:300] + ("..." if len(think_content) > 300 else "")})
                        yield {"type": "progress", "thinking": list(thinking)}
                    token_buf = parts[1] if len(parts) > 1 else ""
                    in_think = False
                    if token_buf.strip():
                        yield {"type": "token", "content": token_buf}
                        final_answer += token_buf
                        token_buf = ""

                if not in_think and token_buf:
                    yield {"type": "token", "content": token_buf}
                    final_answer += token_buf
                    token_buf = ""

    if token_buf and not in_think:
        yield {"type": "token", "content": token_buf}
        final_answer += token_buf

    history.append(("user", question))
    history.append(("assistant", final_answer))
    yield {"type": "done", "thinking": thinking}


@router.post("/ask")
async def chat_ask(req: ChatRequest):
    async def stream():
        try:
            async for chunk in _run_agent_stream(req.session_id, req.question):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)[:300]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/sessions")
def list_sessions():
    return [{"id": k, "count": len(v) // 2} for k, v in _sessions.items()]
