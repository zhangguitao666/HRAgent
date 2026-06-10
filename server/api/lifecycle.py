"""
入转调离流程引导 API
"""
from fastapi import APIRouter
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.hr_assistant.config import LLM_CONFIG

router = APIRouter()

FLOW_PROMPTS = {
    "onboarding": """你是公司入职引导助手。新员工入职步骤：
1. 提交入职材料（身份证、学历证书、离职证明）
2. 签订劳动合同
3. 办理工牌和门禁
4. 开通企业邮箱和内部系统账号
5. 领取办公设备
6. 参加新员工培训
请根据员工问题提供详细的入职指引。""",

    "regularization": """你是公司转正引导助手。转正流程：
1. 试用期结束前2周，HR发起转正评估
2. 员工提交转正申请和自我评估
3. 部门主管进行绩效评估
4. HR审核并确认转正
试用期3-6个月，转正后享受全部福利。请根据员工问题提供转正指引。""",

    "resignation": """你是公司离职引导助手。离职流程：
1. 正式员工提前30天提交书面离职申请
2. 部门主管审批
3. HR面谈并确认
4. 工作交接（文档、项目、设备）
5. 财务结算（工资、报销、补偿金）
6. 社保和公积金转移
7. 归还公司物品
请根据员工问题提供离职指引。""",

    "retirement": """你是公司退休引导助手。退休政策：
- 男性60岁，女性干部55岁，女性工人50岁退休
- 提前3个月办理退休手续
流程：申请→HR审核→社保局审批→领取退休证→发放退休补贴。
请根据员工问题提供退休指引。""",
}


class LifecycleRequest(BaseModel):
    flow_type: str  # onboarding / regularization / resignation / retirement
    message: str


class LifecycleResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=LifecycleResponse)
def lifecycle_chat(req: LifecycleRequest):
    system_prompt = FLOW_PROMPTS.get(req.flow_type, FLOW_PROMPTS["onboarding"])

    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=LLM_CONFIG["temperature"],
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])
    chain = prompt | llm | StrOutputParser()
    reply = chain.invoke({"input": req.message})
    return LifecycleResponse(reply=reply)
