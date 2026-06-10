# 模块7：HR 助手实战项目

> **目标**：综合运用所有 LangChain 知识，构建完整的人力资源系统助手智能体

---

## 7.1 项目总览

```
┌──────────────────────────────────────────────────────────┐
│                 HR 智能助手 (Streamlit Web)                │
├──────────────┬──────────────┬──────────────┬──────────────┤
│  FAQ 问答    │  简历解析     │  入转调离     │  数据查询     │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ RAG 知识库   │ 结构化提取    │ 流程引导      │ 工具调用      │
│ + 记忆系统   │ + 匹配评估    │ 记忆系统      │ Agent 自主    │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 7.2 项目架构解析

### 分层设计

```
app.py (主入口/UI层)
    │
    ├─→ tools/ (工具层)
    │   ├── hr_query_tools.py    # 数据库查询工具
    │   └── resume_tool.py       # 简历处理工具
    │
    ├─→ utils/ (工具层)
    │   └── data_loader.py       # 数据加载
    │
    └─→ data/ (数据层)
        ├── employees.json        # 员工数据
        ├── salary.json           # 薪酬数据
        ├── attendance.json       # 考勤数据
        └── company_policy.txt    # 公司制度知识库
```

### 使用的 LangChain 能力

| 功能模块 | 使用的 LangChain 技术 |
|---------|---------------------|
| FAQ 问答 | ChatPromptTemplate + RAG + Memory |
| 简历解析 | `with_structured_output()` + Pydantic |
| 入转调离 | RunnableWithMessageHistory |
| 数据查询 | `@tool` + Agent 自动推理 |

---

## 7.3 启动项目

### 运行步骤

```powershell
# 1. 确保已在项目根目录并激活虚拟环境
cd D:\DevHub\LangChain
.\venv\Scripts\Activate.ps1

# 2. 安装依赖（含 streamlit）
pip install streamlit pandas -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 启动应用
streamlit run src\hr_assistant\app.py

# 浏览器自动打开 http://localhost:8501
```

### Streamlit 启动后界面

```
┌─────────────────────────────────────┐
│ 👔 HR 智能助手                       │
│─────────────────────────────────────│
│ ◉ 💬 FAQ 智能问答                    │
│ ○ 📄 简历解析                        │
│ ○ 🚪 入转调离                       │
│ ○ 📊 数据查询                       │
│─────────────────────────────────────│
│ Powered by LangChain + minimax-m2.5 │
└─────────────────────────────────────┘
```

---

## 7.4 功能模块详解

### 7.4.1 FAQ 智能问答（RAG 模式）

**技术栈**：RAG + Memory

```
用户提问 "年假怎么算？"
        │
        ▼
   ChatPromptTemplate（注入公司制度文档）
        │
        ▼
   LLM 基于文档生成回答
        │
        ▼
   Memory 记录对话（下次记得你问过什么）
```

**核心代码**：
```python
system_prompt = f"""你是公司HR智能助手。
以下是公司制度资料，严格基于此回答：
---
{policy_text}
---"""

chain = create_chat_chain(system_prompt)  # 带记忆的对话链
response = chain.invoke({"input": "年假怎么算？"})
```

### 7.4.2 简历解析（结构化输出模式）

**技术栈**：`with_structured_output()` + Pydantic

```
简历文本 ──→ ChatPromptTemplate ──→ Structured LLM ──→ ResumeInfo 对象
                                                          │
                                    {name, age, skills,   │
                                     education, summary...}│
                                                          ▼
                                                  岗位匹配评估
```

**核心代码**：
```python
class ResumeInfo(BaseModel):
    name: str
    years_of_experience: int
    skills: list[str]
    # ...

structured_llm = llm.with_structured_output(ResumeInfo)
result = chain.invoke({"resume_text": "..."})
# result = ResumeInfo(name='张三', years_of_experience=5, ...)
```

### 7.4.3 入转调离（流程引导模式）

**技术栈**：Memory + System Prompt 注入流程知识

```
用户选择 "入职引导"
        │
        ▼
   System Prompt = 入职流程知识
        │
        ▼
   对话中逐步引导用户完成入职手续
        │
        ▼
   Memory 记录对话上下文
```

### 7.4.4 数据查询（Agent 工具调用模式）

**技术栈**：`@tool` + Agent 自动推理

```
用户输入 "技术部有哪些人？"
        │
        ▼
   Agent 推理 → 调用 get_department_employees("技术部")
        │
        ▼
   返回结果展示 + 表格可视化
```

---

## 7.5 关键代码流

### FAQ 对话的完整数据流

```python
# 1. 加载公司制度文档
policy_text = load_policy()  # 从 company_policy.txt 读取

# 2. 构建 system prompt（知识注入）
system_prompt = f"""
你是HR助手。基于以下资料回答：
---
{policy_text}
---
"""

# 3. 创建带记忆的链
llm = ChatOpenAI(model="minimax-m2.5", ...)
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="history"),  # 对话历史
    ("human", "{input}"),
])

chain = RunnableWithMessageHistory(
    prompt | llm,
    get_session_history,       # 管理对话历史
    input_messages_key="input",
    history_messages_key="history",
)

# 4. 对话
response = chain.invoke(
    {"input": "年假怎么申请？"},
    config={"configurable": {"session_id": "user_123"}}
)
```

### Agent 查询的数据流

```python
# 1. 定义工具
@tool
def query_employee_info(query_text: str) -> str:
    """查询员工信息"""
    # 从 JSON 文件查询
    ...

# 2. 创建 Agent
agent = create_react_agent(llm, [query_employee_info, ...])

# 3. 用户用自然语言查询，Agent 自动选择工具
response = agent.invoke({
    "messages": [("user", "张三在哪个部门？")]
})
```

---

## 7.6 代码文件索引

| 文件 | 说明 |
|------|------|
| `app.py` | Streamlit 主应用，含全部页面逻辑 |
| `config.py` | LLM API 配置 |
| `tools/hr_query_tools.py` | 5个数据查询 Tool |
| `tools/resume_tool.py` | 简历解析 Tool |
| `utils/data_loader.py` | JSON 文件读取 |
| `data/employees.json` | 12条模拟员工数据 |
| `data/salary.json` | 6条薪酬记录 |
| `data/attendance.json` | 12条考勤记录 |
| `data/company_policy.txt` | 公司制度知识库 |

---

## 7.7 扩展方向

学完本项目后，你可以继续：

1. **接入真实数据库**：把 JSON 替换为 SQLite/MySQL
2. **知识库升级**：支持 PDF/Docx 导入，自动建立向量库
3. **多 Agent 协作**：招聘 Agent + 培训 Agent + 薪酬 Agent
4. **权限控制**：员工只能查自己，HR 可以查全部
5. **部署上线**：用 Docker + Nginx 部署到服务器

---

## 小结

恭喜！你已完成从零基础到完整 HR 助手项目的全部学习路径。

回顾学到的核心知识：
- Model/Prompt/Chain 三件套
- LCEL 管道语法
- 结构化输出 with_structured_output()
- 记忆系统 RunnableWithMessageHistory
- RAG 检索增强生成
- Agent 与 Tool 定义

👉 最终模块：[总结与回顾](08-summary.md)
