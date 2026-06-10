"""
简历处理工具 - 简历解析和信息提取
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.hr_assistant.config import LLM_CONFIG


class ResumeInfo(BaseModel):
    name: str = Field(description="姓名")
    age: int = Field(description="年龄")
    education: str = Field(description="最高学历")
    school: str = Field(description="毕业院校")
    years_of_experience: int = Field(description="工作年限")
    skills: list[str] = Field(description="核心技能列表")
    current_position: str = Field(description="当前/最近职位")
    expected_position: str = Field(description="期望职位")
    expected_salary: str = Field(description="期望薪资")
    summary: str = Field(description="候选人综合评估总结，100字以内")


@tool
def parse_resume(resume_text: str) -> str:
    """解析简历文本，提取候选人的关键信息。
    输入为完整的简历文本内容。
    返回结构化的候选人信息，包括姓名、学历、工作经验、技能、期望薪资等。
    """
    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=0.3,
    )

    structured_llm = llm.with_structured_output(ResumeInfo)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是专业的HR简历筛选专家。从以下简历中提取关键信息。
对于缺失的信息，根据上下文合理推断或填入"未知"。
summary 字段需给出对候选人的综合评价。"""),
        ("human", "{resume_text}"),
    ])

    chain = prompt | structured_llm

    try:
        result = chain.invoke({"resume_text": resume_text})
        output = f"""
候选人信息提取结果：
━━━━━━━━━━━━━━━━━━━━━━
姓名：{result.name}
年龄：{result.age}岁
学历：{result.education}
毕业院校：{result.school}
工作年限：{result.years_of_experience}年
当前职位：{result.current_position}
期望职位：{result.expected_position}
期望薪资：{result.expected_salary}
核心技能：{', '.join(result.skills)}

综合评估：
{result.summary}
━━━━━━━━━━━━━━━━━━━━━━
"""
        return output.strip()
    except Exception as e:
        return f"简历解析失败：{str(e)}"


def get_screening_prompt(job_requirements: str, resume_info: str) -> str:
    """生成简历筛选评估 prompt"""
    return f"""请根据以下岗位要求，对候选人进行匹配度评估。

【岗位要求】：
{job_requirements}

【候选人信息】：
{resume_info}

请从以下维度评估（1-10分）：
1. 学历匹配度
2. 工作经验匹配度
3. 技能匹配度
4. 综合推荐度

并给出是否推荐面试的建议（推荐面试 / 保留 / 不推荐）。
"""
