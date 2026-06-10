# 模块6：智能体与工具

> **目标**：理解 Agent 运作原理，掌握 Tool 定义和 Function Calling 机制，实现能"行动"的 AI

---

## 6.1 什么是 Agent？

之前的 Chain 是固定的流水线：A → B → C。Agent 不同——它能**自主决策**下一步做什么。

```
用户："帮我查一下张三的年假还剩几天，然后帮他申请"

Agent 思考：我需要先查张三的年假余额 → 调用"年假查询"工具
         → 拿到结果3天 → 可以申请 → 调用"年假申请"工具
         → 申请成功 → 把结果告诉用户
```

**Agent = LLM + 工具 + 决策循环**

```
      ┌──────────┐
      │  用户输入  │
      └────┬─────┘
           ▼
    ┌──────────────┐     ┌───────────────┐
    │   LLM 推理    │────▶│ 调用工具Tool1   │
    │  (Agent大脑)  │     └───────┬───────┘
    └──────┬───────┘             │ 结果
           │              ┌──────▼───────┐
           │              │ 调用工具Tool2   │
           │              └──────┬───────┘
           │◀────────────────────┘
           ▼
    ┌──────────────┐
    │  生成最终回答  │
    └──────────────┘
```

---

## 6.2 Tool（工具）：Agent 的手和脚

Tool 就是一个**被 Agent 调用的 Python 函数**。定义方法是用 `@tool` 装饰器：

```python
from langchain_core.tools import tool

@tool
def search_employee(name: str) -> str:
    """根据姓名查询员工信息。

    Args:
        name: 员工姓名
    """
    # 这里是模拟数据，生产环境应该查数据库
    employees = {
        "张三": "工号EMP001，技术部，高级工程师，2020年入职",
        "李四": "工号EMP002，市场部，市场经理，2019年入职",
    }
    return employees.get(name, f"未找到员工：{name}")

@tool
def get_leave_balance(employee_id: str) -> str:
    """查询员工的年假余额。

    Args:
        employee_id: 员工工号，如 EMP001
    """
    leave_data = {
        "EMP001": "年假余额：8天，已用2天",
        "EMP002": "年假余额：12天，已用3天",
    }
    return leave_data.get(employee_id, "未找到该员工的假期信息")
```

**定义 Tool 的要点**：
1. 函数名 = 工具名（Agent 会通过名字来调用）
2. **docstring 非常重要**——Agent 通过它理解工具的用途
3. 参数类型注解让 Agent 知道要传什么参数

---

## 6.3 创建 Agent

LangChain 使用 `create_react_agent` + `AgentExecutor` 来创建 Agent：

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
    temperature=0,
)

# 把工具列表给 Agent
tools = [search_employee, get_leave_balance]

# 创建 Agent（LangGraph 方式，推荐）
agent_executor = create_react_agent(llm, tools)

# 运行 Agent
response = agent_executor.invoke({
    "messages": [("user", "张三的年假还有几天？")]
})

# 获取最终回答
final_message = response["messages"][-1]
print(final_message.content)
```

---

## 6.4 Agent 的推理过程（ReAct 模式）

ReAct = **Re**asoning + **Act**ion（推理+行动）

Agent 内部是这样运作的：

```
第1步：LLM推理 → "用户想知道张三的年假。我先查张三的信息"
        行动 → 调用 search_employee("张三")
        结果 → "工号EMP001，技术部..."

第2步：LLM推理 → "张三的工号是EMP001，现在查年假"
        行动 → 调用 get_leave_balance("EMP001")
        结果 → "年假余额：8天，已用2天"

第3步：LLM推理 → "信息足够了，生成最终回答"
        回答 → "张三（工号EMP001）目前年假余额为8天，已使用2天。"
```

这个过程是**自动循环**的，直到 Agent 认为可以给出最终答案。

---

## 6.5 使用 OpenAI 原生 Function Calling

如果你的模型支持 Function Calling（minimax-m2.5 应该支持），可以这样用：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
)

# 直接绑定工具到 LLM
llm_with_tools = llm.bind_tools(tools)

# LLM 会自动决定是否调用工具
response = llm_with_tools.invoke("张三的年假余额是多少？")

# 查看 LLM 是否决定调用工具
if response.tool_calls:
    for tool_call in response.tool_calls:
        print(f"调用工具: {tool_call['name']}")
        print(f"参数: {tool_call['args']}")
```

---

## 6.6 练习：HR 查询 Agent

创建 `src/basics/05_agents.py`：

```python
"""
HR 查询 Agent - 演示工具调用和多步推理
"""
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

CONFIG = {
    "model": "minimax-m2.5",
    "api_key": "<your-llm-api-key>",
    "base_url": "http://your-llm-host:3000/v1",
}

# ============================================================
# 定义工具
# ============================================================
@tool
def search_employee(name: str) -> str:
    """根据姓名查询员工信息，返回工号、部门、职位。"""
    employees = {
        "张三": "工号EMP001，技术部，高级工程师，2020年入职",
        "李四": "工号EMP002，市场部，市场经理，2019年入职",
        "王五": "工号EMP003，人力资源部，HR总监，2018年入职",
    }
    return employees.get(name, f"未找到员工：{name}")

@tool
def get_leave_balance(employee_id: str) -> str:
    """查询员工的年假余额，需要提供工号。"""
    data = {
        "EMP001": "年假余额8天，已用2天",
        "EMP002": "年假余额12天，已用3天",
        "EMP003": "年假余额15天，已用5天",
    }
    return data.get(employee_id, "未找到假期信息")

@tool
def get_salary_grade(employee_id: str) -> str:
    """查询员工的薪酬级别，需要提供工号。"""
    data = {
        "EMP001": "P7级，月薪范围25K-35K",
        "EMP002": "M2级，月薪范围30K-40K",
        "EMP003": "M3级，月薪范围40K-55K",
    }
    return data.get(employee_id, "未找到薪酬信息")

# ============================================================
# 创建 Agent
# ============================================================
llm = ChatOpenAI(**CONFIG, temperature=0)
tools = [search_employee, get_leave_balance, get_salary_grade]
agent = create_react_agent(llm, tools)

# ============================================================
# 测试
# ============================================================
def ask(question):
    print(f"\n{'='*50}")
    print(f"用户: {question}")
    response = agent.invoke({"messages": [("user", question)]})
    answer = response["messages"][-1].content
    print(f"AI: {answer}")

ask("张三的年假还有几天？")
ask("王五的薪酬是什么级别？")
ask("李四的工号是什么？他年假有多少天？")  # 需要两步：先查工号，再查年假
```

---

## 6.7 工具设计原则

| 原则 | 说明 |
|------|-----|
| 单一职责 | 一个工具只做一件事 |
| 描述清晰 | docstring 要详细说明功能、参数、返回值 |
| 参数简单 | 参数类型用基础类型（str, int, float），不用复杂对象 |
| 返回字符串 | 工具返回纯文本，Agent 才能理解 |
| 处理异常 | 查不到数据时返回友好提示，不抛异常 |

---

## 6.8 Agent 类型详解

LangChain 中有多种 Agent 类型，它们的本质区别在于**如何与 LLM 交互、如何描述工具、如何解析 LLM 的输出**。

---

### 6.8.1 ReAct Agent（推荐首选）

**全称**：Reasoning + Acting（推理 + 行动）

**创建方式**：
```python
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(llm, tools)
```

**内部机制**：

ReAct Agent 通过一套固定的 System Prompt 模板，告诉 LLM 按照特定格式来"思考"和"行动"：

```
System Prompt 模板（简化版）：
---
你可以使用以下工具：
{tool_descriptions}

请按以下格式回答：
Thought: 分析当前情况，决定是否需要使用工具
Action: 工具名称
Action Input: 工具参数（JSON格式）
Observation: (工具返回结果)
... (上述步骤可以重复多次)
Thought: 我现在有足够的信息来回答用户
Final Answer: 最终回答
---
```

**关键特点**：
- **纯 Prompt 驱动**：不依赖模型的 Function Calling API，靠 prompt 指令引导模型按格式输出
- **推理过程全透明**：你能看到每一步的 Thought → Action → Observation
- **工具描述是文本**：工具的定义被转成文字说明嵌入 system prompt
- **输出需解析**：需要正则等方式解析 LLM 输出中的 Action/Action Input 字段

**适用场景**：
- 模型**不支持**原生 Function Calling（如一些开源模型、旧模型）
- 需要**调试/观察** Agent 的推理过程
- 想让 Agent 在采取行动前进行**显式思考**

**优缺点**：
| 优点 | 缺点 |
|------|------|
| 不依赖模型 API 特性，兼容性最强 | 输出格式偶尔不符合要求（解析失败） |
| 思考过程完全可见，方便调试 | prompt 占用 tokens 较多 |
| 可以强制 Agent 先思考再行动 | 比 Function Calling 慢（多次生成） |

---

### 6.8.2 OpenAI Tools Agent（Function Calling Agent）

**创建方式**：
```python
# 方式1：langchain 传统 API
from langchain.agents import create_openai_tools_agent
agent = create_openai_tools_agent(llm, tools, prompt)

# 方式2：直接 bind（LangChain 0.3+ 推荐）
llm_with_tools = llm.bind_tools(tools)
```

**内部机制**：

利用 OpenAI/兼容接口的 **原生 Function Calling** 能力。LLM 不是在文本中"写出"工具调用，而是通过 API 的 `tool_calls` 字段返回结构化的调用指令：

```json
// LLM 返回的 response 中包含：
{
  "content": null,
  "tool_calls": [
    {
      "name": "search_employee",
      "arguments": {"name": "张三"}
    }
  ]
}
```

然后在 Agent 引擎中执行实际的函数调用，把结果传回 LLM。

**关键特点**：
- **结构化调用**：工具调用通过 API 的 `tool_calls` 字段传递，不会出现解析错误
- **并行调用**：LLM 可以同时发起多个工具调用（"同时查张三和李四的信息"）
- **模型必须支持**：要求底层 LLM 提供 Function Calling / Tools API

**适用场景**：
- 使用 OpenAI 系列模型（GPT-4o、GPT-3.5-turbo 等）
- 使用**兼容 OpenAI API** 的模型（DeepSeek、MiniMax、Qwen 等）
- 需要**并行工具调用**提升效率
- 生产环境追求稳定性和准确性

**优缺点**：
| 优点 | 缺点 |
|------|------|
| 调用准确性最高，不会格式错误 | 依赖模型 API，不兼容所有模型 |
| 支持并行工具调用 | 思考过程不透明（黑盒） |
| tokens 消耗更少（工具定义是结构化的） | 某些兼容接口可能实现不完整 |

---

### 6.8.3 Structured Chat Agent

**创建方式**：
```python
from langchain.agents import create_structured_chat_agent
agent = create_structured_chat_agent(llm, tools, prompt)
```

**内部机制**：

支持**多输入参数的复杂工具**，使用 JSON 格式来传递参数：

```
Action:
```
{
  "action": "search_employee",
  "action_input": {"name": "张三"}
}
```
```

与 ReAct 的区别：ReAct 的工具输入是简单的 key=value 格式，Structured Chat 支持嵌套 JSON 对象作为工具参数。

**适用场景**：
- 工具参数是**复杂嵌套结构**（如 `{"filters": {"dept": "技术部", "level": "P7"}}`）
- 需要**结构化对话管理**（不是简单的单轮调用）

**优缺点**：
| 优点 | 缺点 |
|------|------|
| 支持复杂参数结构 | 配置更复杂 |
| 输出更结构化 | 社区使用较少，文档不丰富 |

---

### 6.8.4 四种 Agent 深度对比

```
┌──────────────────────────────────────────────────────────────┐
│                     调用方式对比                              │
├──────────────┬──────────────┬───────────────┬────────────────┤
│   ReAct      │  OpenAI Tools│  Structured   │  bind_tools()  │
│              │  Agent       │  Chat         │                │
├──────────────┼──────────────┼───────────────┼────────────────┤
│ LLM输出文本  │ API结构化返回│ LLM输出JSON   │ API结构化返回   │
│ 正则解析     │ tool_calls   │ 解析          │ tool_calls     │
│ 不支持并行   │ 支持并行     │ 不支持并行     │ 支持并行       │
│ 任何模型     │ 仅支持FC模型 │ 任何模型      │ 仅支持FC模型    │
└──────────────┴──────────────┴───────────────┴────────────────┘
```

| 维度 | ReAct Agent | OpenAI Tools Agent | Structured Chat | bind_tools() |
|------|-------------|-------------------|-----------------|--------------|
| **底层机制** | Prompt 模板引导 | 原生 Function Calling API | Prompt + JSON Schema | Function Calling API |
| **工具描述方式** | 纯文本嵌入 prompt | 结构化 JSON Schema | 纯文本嵌入 prompt | 结构化 JSON Schema |
| **调用准确性** | 中（偶尔格式错误） | **高**（API 保证） | 中（JSON 解析可能失败） | **高**（API 保证） |
| **并行工具调用** | 不支持 | **支持** | 不支持 | **支持** |
| **推理可见性** | **完全可见**（Thought/Action/Observation） | 不可见（黑盒） | 半可见 | 不可见 |
| **Token 消耗** | 高（prompt 模板+tools 描述） | **低**（结构化传输） | 高（prompt 模板+tools 描述） | **低**（结构化传输） |
| **模型兼容性** | **所有模型** | 仅支持 FC 的模型 | **所有模型** | 仅支持 FC 的模型 |
| **来源** | langgraph | langchain.agents | langchain.agents | langchain_core |
| **官方推荐度** | **当前首选**（V1 推荐） | 稳定可用 | 特定场景 | 简洁直接 |

---

### 6.8.5 选型决策流程图

```
你的模型支持 Function Calling 吗？
        │
    ┌───┴───┐
    │  YES   │                │  NO    │
    └───┬───┘                └───┬───┘
        │                        │
    需要推理过程可见吗？         → create_react_agent()
        │                        （唯一选择，兼容所有模型）
    ┌───┴───┐
    │  YES   │        │  NO    │
    └───┬───┘        └───┬───┘
        │                 │
  create_react_agent()   llm.bind_tools()
  （既能FC又可见过程）     或 create_openai_tools_agent()
                          （最简洁准确）
```

---

### 6.8.6 实战建议

| 场景 | 推荐 Agent | 原因 |
|------|-----------|------|
| 你的 minimax-m2.5 项目 | `create_react_agent()` | 模型返回 `<think>` 标签会影响 FC 的结构化解析 |
| 纯 OpenAI GPT-4o | `llm.bind_tools()` 或 `create_openai_tools_agent()` | 原生支持最好 |
| 本地开源模型（Qwen/Llama） | `create_react_agent()` | 不一定支持 FC |
| 需要并行查多个数据源 | `llm.bind_tools()` | OpenAI Tools 支持并行调用 |
| 调试/学习阶段 | `create_react_agent()` | 能看到完整推理过程 |
| 生产环境（追求稳定性） | Funcion Calling 系 | 调用准确性最高 |

> **对本项目的最优选择**：继续使用 `create_react_agent()`。因为 minimax-m2.5 在 structured output 时输出 `<think>` 标签，可能导致 Function Calling 的 JSON 解析不稳定，ReAct 模式更加健壮。

---

## 小结

- Agent = LLM（大脑） + Tools（手脚） + 决策循环
- `@tool` 装饰器把普通函数变成 Agent 可以调用的工具
- docstring 是 Agent 理解工具的关键
- `create_react_agent()` 是官方推荐的 Agent 创建方式
- Agent 会自动多步推理，直到得出最终答案

👉 下一模块：[HR 助手实战项目](07-hr-assistant.md)
