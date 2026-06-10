"""
FAQ 智能问答 API
"""
from fastapi import APIRouter
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from src.hr_assistant.config import LLM_CONFIG
from src.hr_assistant.utils import load_policy

router = APIRouter()

_sessions = {}

policy_text = load_policy()

SYSTEM_PROMPT = f"""你是公司HR智能助手，热情专业地回答员工问题。
以下是公司制度资料，请严格基于此回答：
---
{policy_text}
---
如果资料中没有相关信息，请如实告知，不要编造。"""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
def faq_chat(req: ChatRequest):
    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=LLM_CONFIG["temperature"],
    )

    # 无状态模式：每次注入知识库全文作为上下文
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    chain = prompt | llm | StrOutputParser()
    reply = chain.invoke({"input": req.message})
    return ChatResponse(reply=reply)
