"""
数据查询 API - Function Calling 双工具 Agent（SSE流式 + 会话记忆）
"""
import re
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.hr_assistant.config import LLM_CONFIG

router = APIRouter()

_sessions = {}


class QueryRequest(BaseModel):
    question: str
    session_id: str = "default"


SYSTEM_PROMPT = """你是企业 HR 数据助手。**所有数据查询必须调用工具**。

## 工具选择规则：
- 人事问题（查人/部门/人数/学历/职称/考核等）→ 调用 query_hr
- 薪酬问题（工资/社保/公积金/个税/医保等）→ 调用 query_salary
- 不确定时优先调用 query_hr

## 回答规则：
1. **禁止用"知识库中没有"来回答**，必须先调工具
2. 只有工具返回空数据时才说"未查到"
3. 简洁自然，不输出 SQL 和原始表格
4. 结果超过20条时告知用户已截断"""


def _get_session_history(session_id: str) -> list:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


async def _run_agent_stream(session_id: str, question: str):
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI
    from src.hr_assistant.tools.hr_query_tools import query_hr, query_salary

    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=0,
    )

    llm_with_tools = llm.bind_tools([query_hr, query_salary])
    agent = create_react_agent(llm_with_tools, [query_hr, query_salary], prompt=SYSTEM_PROMPT)

    history = _get_session_history(session_id)
    input_messages = history + [("user", question)]

    thinking = []
    pending_tools = 0
    can_emit = False
    final_answer = ""
    token_buf = ""        # think 标签缓冲区
    in_think = False      # 是否在 think 块内

    async for event in agent.astream_events(
        {"messages": input_messages}, version="v2",
    ):
        kind = event.get("event", "")

        if kind == "on_tool_start":
            pending_tools += 1
            can_emit = False
            tool_name = event.get("name", "")
            tool_input = event.get("data", {}).get("input", {})
            q = tool_input.get("question", "")
            thinking.append({"type": "tool_call", "content": f"{tool_name}: {q}"})
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

                # 检测 <think> 开始 → 收集think内容
                if "<think>" in token_buf and not in_think:
                    in_think = True
                    parts = token_buf.split("<think>", 1)
                    if parts[0].strip():
                        yield {"type": "token", "content": parts[0]}
                        final_answer += parts[0]
                    token_buf = parts[1] if len(parts) > 1 else ""

                # 检测 </think> 结束 → 把think内容展示为思考步骤
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
async def ask_query(req: QueryRequest):
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
