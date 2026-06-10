"""
HR 智能助手 - Streamlit 主页面
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from src.hr_assistant.config import LLM_CONFIG
from src.hr_assistant.utils import load_policy

st.set_page_config(
    page_title="HR 智能助手",
    page_icon="👔",
    layout="wide",
)

st.sidebar.title("👔 HR 智能助手")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "选择功能",
    ["💬 FAQ 智能问答", "📄 简历解析", "🚪 入转调离", "📊 数据查询"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Powered by LangChain + minimax-m2.5")


def create_chat_chain(system_prompt: str):
    """创建带记忆的对话链"""
    llm = ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=LLM_CONFIG["temperature"],
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    store = {}

    def get_history(session_id: str):
        if session_id not in store:
            store[session_id] = InMemoryChatMessageHistory()
        return store[session_id]

    return RunnableWithMessageHistory(
        prompt | llm,
        get_history,
        input_messages_key="input",
        history_messages_key="history",
    )


if page == "💬 FAQ 智能问答":
    st.title("💬 HR FAQ 智能问答")
    st.markdown("有什么关于公司制度的问题？尽管问我！")

    policy_text = load_policy()
    system_prompt = f"""你是公司HR智能助手，热情专业地回答员工问题。

以下是公司制度资料，请严格基于此回答：
---
{policy_text}
---

如果资料中没有相关信息，请如实告知，不要编造。"""

    if "faq_chain" not in st.session_state:
        st.session_state.faq_chain = create_chat_chain(system_prompt)
        st.session_state.faq_messages = []
        st.session_state.faq_session = "faq_session"

    if st.button("清空对话"):
        st.session_state.faq_messages = []
        st.rerun()

    for msg in st.session_state.faq_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if user_input := st.chat_input("请输入你的问题..."):
        st.session_state.faq_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response = st.session_state.faq_chain.invoke(
                    {"input": user_input},
                    config={"configurable": {"session_id": st.session_state.faq_session}}
                )
                st.write(response.content)
        st.session_state.faq_messages.append({"role": "assistant", "content": response.content})


elif page == "📄 简历解析":
    from src.hr_assistant.tools.resume_tool import parse_resume

    st.title("📄 简历智能解析")
    st.markdown("粘贴简历文本，AI 自动提取关键信息并进行评估")

    col1, col2 = st.columns(2)

    with col1:
        resume_text = st.text_area(
            "简历内容",
            height=300,
            placeholder="请在此粘贴简历全文...",
        )

        jd_text = st.text_area(
            "岗位要求（可选，用于匹配评估）",
            height=150,
            placeholder="粘贴招聘 JD...",
        )

        parse_btn = st.button("🔍 解析简历", type="primary", use_container_width=True)

    with col2:
        if parse_btn and resume_text:
            with st.spinner("AI 正在解析简历..."):
                result = parse_resume.invoke({"resume_text": resume_text})
            st.success("解析完成")
            st.markdown(result)

            if jd_text:
                st.markdown("---")
                st.subheader("📋 岗位匹配评估")
                with st.spinner("正在评估匹配度..."):
                    llm = ChatOpenAI(
                        model=LLM_CONFIG["model"],
                        api_key=LLM_CONFIG["api_key"],
                        base_url=LLM_CONFIG["base_url"],
                        temperature=0.3,
                    )
                    from src.hr_assistant.tools.resume_tool import get_screening_prompt
                    eval_prompt = get_screening_prompt(jd_text, result)
                    evaluation = llm.invoke(eval_prompt)
                    st.markdown(evaluation.content)


elif page == "🚪 入转调离":
    st.title("🚪 员工入转调离指引")

    flow_type = st.selectbox(
        "选择流程类型",
        ["入职引导", "转正引导", "离职引导", "退休引导"],
    )

    if "flow_chain" not in st.session_state:
        st.session_state.flow_chain = None

    flow_prompts = {
        "入职引导": """你是公司入职引导助手。新员工入职需要完成以下步骤：
1. 提交入职材料（身份证、学历证书、离职证明等）
2. 签订劳动合同
3. 办理工牌和门禁
4. 开通企业邮箱和内部系统账号
5. 领取办公设备
6. 参加新员工培训
请根据员工的问题，提供详细的入职指引。""",

        "转正引导": """你是公司转正引导助手。试用期转正流程：
1. 试用期结束前2周，HR发起转正评估
2. 员工提交转正申请和自我评估
3. 部门主管进行绩效评估
4. HR审核并确认转正
5. 签订正式劳动合同
试用期3-6个月，转正后享受全部福利。请根据员工问题提供转正指引。""",

        "离职引导": """你是公司离职引导助手。员工离职流程：
1. 正式员工提前30天提交书面离职申请
2. 部门主管审批
3. HR面谈并确认
4. 工作交接（文档、项目、设备等）
5. 财务结算（工资、报销、补偿金等）
6. 社保和公积金转移
7. 归还公司物品
请根据员工问题提供离职指引。""",

        "退休引导": """你是公司退休引导助手。退休政策：
- 男性60岁，女性干部55岁，女性工人50岁退休
- 提前3个月办理退休手续
- 公司提供一次性退休补贴
退休流程：
1. 符合条件的员工申请退休
2. HR审核档案材料
3. 社保局办理退休审批
4. 领取退休证
5. 公司发放退休补贴
请根据员工问题提供退休指引。""",
    }

    if flow_type:
        prompt = flow_prompts[flow_type]
        if (st.session_state.flow_chain is None
                or st.session_state.get("current_flow") != flow_type):
            st.session_state.flow_chain = create_chat_chain(prompt)
            st.session_state.flow_messages = []
            st.session_state.flow_session = f"flow_{flow_type}"
            st.session_state.current_flow = flow_type

        if st.button("重新开始引导"):
            st.session_state.flow_messages = []
            st.rerun()

        for msg in st.session_state.get("flow_messages", []):
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if user_input := st.chat_input("请输入你的问题..."):
            msgs = st.session_state.get("flow_messages", [])
            msgs.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)

            with st.chat_message("assistant"):
                with st.spinner("思考中..."):
                    response = st.session_state.flow_chain.invoke(
                        {"input": user_input},
                        config={"configurable": {"session_id": st.session_state.flow_session}}
                    )
                    st.write(response.content)
            msgs.append({"role": "assistant", "content": response.content})
            st.session_state.flow_messages = msgs


elif page == "📊 数据查询":
    import re
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI
    from src.hr_assistant.tools.hr_query_tools import query_database

    st.title("📊 HR 数据智能查询")
    st.markdown("直连真实数据库，用自然语言查询人事、薪酬、社保等数据")

    # 初始化 Agent
    if "data_agent" not in st.session_state:
        agent_llm = ChatOpenAI(
            model=LLM_CONFIG["model"],
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
            temperature=0,
        )
        st.session_state.data_agent = create_react_agent(agent_llm, [query_database])
        st.session_state.data_messages = []

    with st.expander("💡 试试这些（取自已验证的测试用例）"):
        st.markdown("""
**人事统计：** "目前在职多少人" | "各部门人数" | "男女各多少人"
**人员查询：** "刘星在哪个部门" | "职称为高级工程师的员工"
**薪酬查询：** "2026年5月实发工资总额" | "杨紫近6个月工资变化"
**社保公积金：** "公积金缴费基数最高的前10人"
**综合：** "各学历人数分布" | "今年入职了多少人"
        """)

    if st.button("清空对话"):
        st.session_state.data_messages = []
        st.rerun()

    for msg in st.session_state.data_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if user_input := st.chat_input("输入查询，例如：目前在职多少人？"):
        st.session_state.data_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Agent 正在推理并生成 SQL..."):
                response = st.session_state.data_agent.invoke(
                    {"messages": [("user", user_input)]}
                )
                messages = response["messages"]

                final_answer = ""
                thinking_parts = []

                for msg in messages:
                    # Agent 调用工具（含 tool_calls 的 AIMessage）
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            args = tc.get("args", {})
                            question = args.get("question", "")
                            thinking_parts.append(f"Agent 决定调用 **query_database** 工具\n> 查询：{question}")

                    # 工具返回结果（ToolMessage）
                    if hasattr(msg, "name") and msg.name == "query_database":
                        content = msg.content if hasattr(msg, "content") else str(msg)
                        # 提取 SQL
                        sql_match = re.search(r"SQL:\s*(.+?)(?:\n\n|\n共|\n(?=[A-Z]))", content, re.DOTALL)
                        if sql_match:
                            thinking_parts.append(f"执行 SQL：\n```sql\n{sql_match.group(1).strip()}\n```")
                        # 提取结果概要
                        result_match = re.search(r"共 (\d+) 条记录", content)
                        if result_match:
                            thinking_parts.append(f"返回 {result_match.group(1)} 条记录")
                        # 如果是错误
                        if "出错" in content or "失败" in content:
                            err_match = re.search(r"(查询出错:.+)", content)
                            if err_match:
                                thinking_parts.append(f"⚠️ {err_match.group(1)[:200]}")

                    # 最终回答（AIMessage 无 tool_calls）
                    if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls") and msg.content.strip():
                        final_answer = msg.content

                # 展示思考过程（折叠、弱化显示）
                if thinking_parts:
                    with st.expander("🔍 查看执行过程", expanded=False):
                        for part in thinking_parts:
                            st.caption(part)

                # 展示正式回答（主要区域）
                if final_answer:
                    st.markdown(f"### 回答\n\n{final_answer}")
                    st.divider()

        st.session_state.data_messages.append({"role": "assistant", "content": final_answer})
