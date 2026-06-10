"""
简历解析 API
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import re
import json

from src.hr_assistant.config import LLM_CONFIG

router = APIRouter()


class ResumeRequest(BaseModel):
    resume_text: str
    job_requirements: str = ""


class ResumeInfo(BaseModel):
    name: str = Field(default="未知")
    years_of_experience: int = Field(default=0)
    education: str = Field(default="未知")
    skills: list[str] = Field(default_factory=list)
    current_position: str = Field(default="未知")
    expected_salary: str = Field(default="未知")
    summary: str = Field(default="")


class ResumeResponse(BaseModel):
    info: ResumeInfo
    evaluation: str = ""


@router.post("/parse", response_model=ResumeResponse)
def parse_resume(req: ResumeRequest):
    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=0.3,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """从以下简历中提取信息，以JSON格式返回：
{"name":"姓名","years_of_experience":工作年限数字,"education":"最高学历","skills":["技能1","技能2"],"current_position":"当前职位","expected_salary":"期望薪资","summary":"综合评价100字以内"}
只输出JSON，不要其他内容。"""),
        ("human", "{resume_text}"),
    ])
    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke({"resume_text": req.resume_text})

    # 清洗 <think> 标签
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = re.sub(r"```json\s*|```", "", raw).strip()

    try:
        data = json.loads(raw)
        info = ResumeInfo(**data)
    except Exception:
        info = ResumeInfo()

    evaluation = ""
    if req.job_requirements:
        eval_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是HR专家。根据以下信息评估候选人与岗位的匹配度（1-10分），从学历、经验、技能三个维度打分，并给出是否推荐面试的建议。"""),
            ("human", "岗位要求：{jd}\n\n候选人：{resume}"),
        ])
        eval_chain = eval_prompt | llm | StrOutputParser()
        raw_eval = eval_chain.invoke({"jd": req.job_requirements, "resume": json.dumps(data, ensure_ascii=False)})
        evaluation = re.sub(r"<think>.*?</think>", "", raw_eval, flags=re.DOTALL).strip()

    return ResumeResponse(info=info, evaluation=evaluation)
