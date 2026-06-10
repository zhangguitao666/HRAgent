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

### 第二优先级：人事数据查询 → 调用 query_hr
- 查人员信息（某人在哪个部门、学历、职称等）
- 查部门/组织人数统计、离职率等
- 查学历分布、年龄分布、性别统计等

### 第三优先级：薪酬数据查询 → 调用 query_salary
- 查某人员工工资、社保缴费
- 查某月工资总额、平均工资
- 查个税、公积金缴存金额

### 第四优先级：简历 → parse_resume
### 第五优先级：入转调离流程 → lifecycle_guide

## 铁律：
1. 制度政策类问题不调 query_faq = 你的回答没有任何依据 = 你错了
2. 数据查询必须先调工具，禁止猜数据
3. 不确定时优先调 query_faq
4. 简洁回答，不输出 SQL"""


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

    # --- 构建 Agent ---
    tools = [query_hr, query_salary, query_faq, parse_resume, lifecycle_guide]

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
