# LangGraph 多智能体编排教程

> 从单 Agent 到多 Agent 协作，渐进式掌握 LangGraph 编排能力  
> **每个代码块都有逐行注释，解释函数作用和设计意图**

---

## 一、基础回顾：State、Node、Edge、Graph

### 1.1 四个核心概念

LangGraph 本质上是一个 **有向图状态机**。你需要定义四样东西：

| 概念 | 代码 | 作用 |
|------|------|------|
| **State** | `TypedDict` | 图中流通的数据结构，所有节点共享 |
| **Node** | 一个函数 `(state) → dict` | 执行具体逻辑：调用 LLM、执行工具、做判断 |
| **Edge** | `add_edge` / `add_conditional_edges` | 决定"下一步去哪"：固定走 or 条件判断 |
| **Graph** | `StateGraph(State)` | 把节点和边拼成图，`.compile()` 后变成可执行 App |

### 1.2 最简示例：三个节点串行

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# ═══════════════════════════════════════════════════════════
# 1. 定义 State —— 这是图中所有节点共享的"内存空间"
# ═══════════════════════════════════════════════════════════
# TypedDict 和普通 dict 的区别：
#   - 普通 dict: 可以随便加 key，运行时才发现拼写错误
#   - TypedDict: 预先声明有哪些 key，IDE 可以自动补全和检查
# 
# 每个节点函数接收 State，返回 State 中需要更新的字段（dict 格式）
# LangGraph 会自动合并返回值到全局 State 中
class MyState(TypedDict):
    input_text: str      # 用户输入
    processed: str       # 处理后的结果
    step_count: int      # 记录经过了几步


# ═══════════════════════════════════════════════════════════
# 2. 定义 Node —— 每个 Node 是一个处理函数
# ═══════════════════════════════════════════════════════════
# Node 函数约定：
#   参数: state (当前全局 State 的快照)
#   返回: dict (只包含你要更新的字段，不需要返回全部字段)
#   LangGraph 会自动用返回值更新全局 State

def uppercase_node(state: MyState) -> dict:
    """Node1: 把输入的文本转成大写"""
    # state["input_text"] — 从 State 中读取输入
    # .upper() — Python 内置，转大写
    result = state["input_text"].upper()
    # 返回值只需要包含要更新的字段，不必返回整个 State
    # LangGraph 内部做的是 state.update({"processed": result})
    print(f"[Node1] 大写处理: {result}")
    return {"processed": result}


def count_node(state: MyState) -> dict:
    """Node2: 计算已处理的文本长度"""
    # state["processed"] — 读取上一个节点写入的数据
    # 这就是 State 的核心价值：节点间通过 State 传递数据
    length = len(state["processed"])
    print(f"[Node2] 长度: {length}")
    # 返回多个字段的更新
    return {"step_count": state["step_count"] + 1}


def summary_node(state: MyState) -> dict:
    """Node3: 输出总结"""
    # 通过 State 拿到前面所有节点的结果
    text = state["processed"]
    count = state["step_count"]
    print(f"[Node3] 总结: 处理了 '{text}' (长度{len(text)})，共{count}步")


# ═══════════════════════════════════════════════════════════
# 3. 构建 Graph —— 把节点和边拼接起来
# ═══════════════════════════════════════════════════════════

# 创建图对象，绑定 State 类型
graph = StateGraph(MyState)

# add_node(name, function) — 注册节点
#   name: 节点的唯一标识（字符串），后续用这个名字引用它
#   function: 节点函数（接收 state，返回 dict）
graph.add_node("step1", uppercase_node)
graph.add_node("step2", count_node)
graph.add_node("step3", summary_node)

# add_edge(from, to) — 添加"固定边"（无条件流转）
#   START: LangGraph 内置的起点，表示从这里开始
#   END:   LangGraph 内置的终点，表示图到此结束
graph.add_edge(START, "step1")   # 从起点 → step1
graph.add_edge("step1", "step2") # step1 完成后 → step2
graph.add_edge("step2", "step3") # step2 完成后 → step3
graph.add_edge("step3", END)     # step3 完成后 → 结束

# 执行流: START → step1 → step2 → step3 → END

# compile() — 把图定义"编译"成可执行的 App
#   编译时会做：检查节点连通性、验证 Edge 引用的节点是否存在
app = graph.compile()

# invoke(initial_state) — 执行图，传入初始 State
#   initial_state 必须包含 State TypedDict 中定义的所有字段
result = app.invoke({"input_text": "hello langgraph", "processed": "", "step_count": 0})
print(f"最终结果: {result}")
```

### 1.3 条件边：让图能"判断"

前面是固定的串行链。Agent 需要循环（think → tool → answer），这靠**条件边**实现。

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END

class CounterState(TypedDict):
    count: int
    message: str


def increment(state: CounterState) -> dict:
    """每次调用 count+1"""
    new_count = state["count"] + 1
    print(f"[加1] count: {state['count']} → {new_count}")
    return {"count": new_count, "message": f"第{new_count}次"}


def double(state: CounterState) -> dict:
    """每次调用 count*2"""
    new_count = state["count"] * 2
    print(f"[翻倍] count: {state['count']} → {new_count}")
    return {"count": new_count, "message": "翻倍了"}


# ═══════════════════════════════════════════════════════════
# 条件路由函数 —— 这是 Agent 能"做决策"的核心机制
# ═══════════════════════════════════════════════════════════
# 函数签名: (state) → str
#   返回的字符串必须是某个已注册节点的 name，或者是 END
#   LangGraph 根据这个返回值决定下一步去哪个节点

def route_by_count(state: CounterState) -> Literal["加一节点", "翻倍节点", END]:
    """
    根据 count 的值决定下一步:
    - count < 3: 继续加1
    - count == 3: 翻倍
    - count >= 6: 结束
    """
    c = state["count"]
    if c >= 6:
        print(f"[路由] count={c} >= 6, 结束")
        return END      # 返回 END 表示不再执行任何节点
    elif c == 3:
        print(f"[路由] count={c} == 3, 翻倍")
        return "翻倍节点"
    else:
        print(f"[路由] count={c} < 3, 继续加1")
        return "加一节点"


graph = StateGraph(CounterState)
graph.add_node("加一节点", increment)
graph.add_node("翻倍节点", double)

# add_conditional_edges(source, router, path_map) — 条件边
#   source:   从哪个节点出发
#   router:   判断函数 (state) → 字符串
#   path_map: 字典，把 router 返回值映射到目标节点
#             格式: {返回字符串: 目标节点名}
graph.add_edge(START, "加一节点")
graph.add_conditional_edges(
    "加一节点",          # 从 increment 出发
    route_by_count,      # 用这个函数判断
    {                    # 映射表
        "加一节点": "加一节点",  # 返回"加一节点" → 回到 increment（循环！）
        "翻倍节点": "翻倍节点",  # 返回"翻倍节点" → 去 double
        END: END,              # 返回 END → 终止
    }
)
graph.add_edge("翻倍节点", "加一节点")  # double 后回到 increment 继续判断

app = graph.compile()
result = app.invoke({"count": 0, "message": ""})
# 执行流: START→加一→加一→加一(c=3)→路由→翻倍(c=6)→路由→END
```

---

## 二、从 FC Agent 到手写 Agent

你的项目用 `create_react_agent` 一步搞定，但你不知道里面怎么工作的。现在我们拆开看。

### 2.1 先定义两个最简单的工具

```python
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI

# ═══════════════════════════════════════════════════════════
# @tool 装饰器: 把一个普通 Python 函数变成 LangChain 的 Tool
# ═══════════════════════════════════════════════════════════
# 装饰器做了什么：
#   1. 读取函数的 docstring，自动生成为 Tool 的描述(description)
#   2. 读取函数的参数类型注解，自动生成 input_schema
#   3. 包装一个 .invoke() 方法，让 LLM 可以通过 Function Calling 调用
#
# 这相当于你在 chat.py 里写的 @tool 包装的 query_hr、query_faq 等

@tool
def search_hr(query: str) -> str:
    """查询公司 HR 系统的数据。
    适用: 查人数、查部门、查员工信息、学历统计等。
    参数 query: 自然语言问题"""
    # 模拟数据库查询结果
    return "查询结果: 全集团共有 1365 名在职员工"


@tool
def search_policy(query: str) -> str:
    """查询公司制度/政策/规定。
    适用: 年假、病假、加班、公积金、培训、绩效考核等政策问题。
    参数 query: 自然语言问题"""
    # 模拟知识库检索结果
    return "制度查询结果: 公司年假政策——入职满1年享5天，满3年10天，满10年15天"


# 收集所有工具到一个列表
tools = [search_hr, search_policy]

# 创建 LLM 实例
llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="sk-xxx",
    base_url="http://your-llm-host:3000/v1",
    temperature=0,
)
```

### 2.2 手写 ReAct Agent（拆开 create_react_agent）

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import ToolMessage, HumanMessage

# ═══════════════════════════════════════════════════════════
# Annotated[list, add_messages] — 特殊的 State 合并策略
# ═══════════════════════════════════════════════════════════
# 普通 State 更新是"覆盖"： state["messages"] = [...] 会丢掉旧数据
# add_messages 是"追加"：新消息追加到消息列表末尾
# 这对于对话 Agent 至关重要：每轮对话的消息都要保留
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def call_llm(state: AgentState) -> dict:
    """
    Agent 的"大脑"——LLM 思考节点
    
    职责：接收当前消息历史，让 LLM 决定下一步
    - 如果 LLM 认为需要查数据 → 返回 tool_calls（告诉系统去调工具）
    - 如果 LLM 认为可以直接回答 → 返回普通文本（不调工具）
    
    这就是 Function Calling 机制：LLM 不直接执行工具，而是"请求"执行
    """
    # llm.bind_tools(tools) — 告诉 LLM 有哪些工具可用
    #   LLM 会根据用户的问话 + 工具的描述(description)，自动判断该调哪个
    #   返回的 response 可能包含 .tool_calls 属性
    llm_with_tools = llm.bind_tools(tools)

    # llm.invoke(messages) — 调用 LLM
    #   state["messages"] 包含所有历史消息（用户提问 + 助手回答 + 工具结果）
    response = llm_with_tools.invoke(state["messages"])

    # 返回格式: {"messages": [response]}
    #   add_messages 合并策略会把新 response 追加到消息列表末尾
    return {"messages": [response]}


def execute_tools_node(state: AgentState) -> dict:
    """
    工具执行节点 —— Agent 的"手脚"
    
    职责：检查 LLM 上一步是否请求了工具调用，如果是就执行
    这就是把 LLM 的"意图"变成"行动"的地方
    """
    # state["messages"][-1] — 最后一条消息，通常是 LLM 的思考结果
    last_msg = state["messages"][-1]

    # hasattr(last_msg, "tool_calls") — 检查 LLM 是否请求了工具调用
    #   tool_calls 是一个列表，LLM 可能同时请求调用多个工具
    if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
        return {"messages": []}

    results = []
    for tc in last_msg.tool_calls:
        # tc 的结构: {"name": "search_hr", "args": {"query": "全集团多少人"}, "id": "call_xxx"}
        tool_name = tc["name"]      # LLM 决定要调哪个工具
        tool_args = tc["args"]      # LLM 生成的工具参数
        tool_call_id = tc["id"]     # 唯一 ID，用于关联"请求"和"结果"

        print(f"[工具执行] 调用 {tool_name}({tool_args})")

        # 找到对应的工具函数
        tool_func = next(t for t in tools if t.name == tool_name)

        # tool_func.invoke(tool_args) — 执行工具
        #   这里才是真正查数据库、查知识库
        output = tool_func.invoke(tool_args)

        # ToolMessage — 把工具执行结果封装成 LLM 能理解的格式
        #   role="tool": 告诉 LLM 这是一条工具返回结果
        #   tool_call_id: 让 LLM 知道这个结果对应哪个请求
        #   content: 工具的输出内容（字符串）
        results.append(ToolMessage(content=str(output), tool_call_id=tool_call_id))

    # 返回工具结果，add_messages 会把它们追加到消息列表
    return {"messages": results}


def should_continue(state: AgentState) -> str:
    """
    路由判断 —— 决定 Agent 循环是否继续
    
    这是 Agent 循环的心脏：
    - 如果 LLM 请求了工具 → 去 "tools" 节点执行工具，然后回到 LLM
    - 如果 LLM 直接给出了回答 → 去 END，停止循环
    
    这就形成了经典的 "Think → Act → Observe → Think" 循环
    """
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"     # 有工具请求 → 去执行工具
    return END             # 无工具请求 → LLM 已经给出最终答案，结束


# ═══════════════════════════════════════════════════════════
# 组装 Graph
# ═══════════════════════════════════════════════════════════
graph = StateGraph(AgentState)

graph.add_node("llm", call_llm)          # 思考节点
graph.add_node("tools", execute_tools_node)  # 执行节点

graph.add_edge(START, "llm")             # 一开始就进入 LLM 思考

# 条件边: LLM 思考后 → 判断 → 去 tools 或 END
graph.add_conditional_edges(
    "llm",
    should_continue,
    {"tools": "tools", END: END},
)

graph.add_edge("tools", "llm")           # 工具执行完 → 回到 LLM 继续思考

agent_app = graph.compile()

# ═══════════════════════════════════════════════════════════
# 执行 Agent
# ═══════════════════════════════════════════════════════════
# HumanMessage(role="user") — 用户消息
#   封装成 LangChain 的 Message 对象，而不是纯字符串
#   这样 State 中的 messages 列表保持类型一致
result = agent_app.invoke({
    "messages": [HumanMessage(content="全集团有多少在职员工？")]
})

# 最终回答在最后一条消息中
print(result["messages"][-1].content)
# 输出类似: "查询结果显示，全集团共有1365名在职员工"
```

**这就是 `create_react_agent` 的全部秘密。** 展开后只有 3 个节点 + 2 条边 + 1 个条件路由。

---

## 三、模式一：条件路由多 Agent

"不同的问题去不同的 Agent"，Agent 之间不需要协作。

```
            ┌─────────────┐
            │  Router 节点  │ ← 快速分类，不调 LLM
            └─┬──┬──┬──┬──┘
              │  │  │  │
         ┌────▼┐ ┌▼──▼┐ ┌▼─────┐
         │ DB  │ │ KB  │ │ Ops  │  ← 每个 Agent 互不干扰
         │Agent│ │Agent│ │Agent │
         └────┬┘ └──┬──┘ └──┬──┘
              │      │       │
              └──────┴───────┘
                     ▼
                   END
```

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage

class MultiState(TypedDict):
    messages: Annotated[list, add_messages]
    domain: str         # 路由目标: "db" / "kb" / "ops"


# ═══════════════════════════════════════════════════════════
# 1. Router — 用关键词快速分类，不调 LLM（又快又便宜）
# ═══════════════════════════════════════════════════════════
def router_node(state: MultiState) -> dict:
    """
    用关键词匹配判断用户意图，决定派给哪个 Agent。

    为什么不用 LLM 做路由？
    - LLM 路由 ≈ 0.5-2s 延迟 + token 成本
    - 关键词路由 ≈ <1ms + 零成本
    - 对于 HR 场景，关键词足够精确

    只有当关键词无法判断时，才用 LLM 路由
    """
    query = state["messages"][-1].content  # 拿到用户最后一条消息

    # 关键词 → 域 映射表
    if any(kw in query for kw in ["多少人", "部门", "学历", "员工", "统计"]):
        domain = "db"       # 数据库查询
    elif any(kw in query for kw in ["年假", "加班", "公积金", "制度", "政策", "规定"]):
        domain = "kb"       # 知识库制度
    elif any(kw in query for kw in ["简历", "入职", "离职", "转正", "退休"]):
        domain = "ops"      # 简历解析/流程引导
    else:
        # 关键词没命中 → 用 LLM 做兜底分类
        resp = llm.invoke([
            ("system", "将问题分类为 db/kb/ops，只输出一个词"),
            ("user", query)
        ])
        domain = resp.content.strip()

    print(f"[Router] 分到 {domain} 域")
    return {"domain": domain}


# ═══════════════════════════════════════════════════════════
# 2. Worker Agents — 三个独立的 Agent，各自绑定自己的工具
# ═══════════════════════════════════════════════════════════

def db_agent_node(state: MultiState) -> dict:
    """
    数据库查询 Agent
    工具: search_hr (人事查询) + 也可以在这里加 search_salary (薪酬查询)
    """
    # 单独绑定数据库相关的工具
    # 注意: 这个 Agent 看不到 kb 相关的工具，避免"串台"
    llm_db = llm.bind_tools([search_hr])
    response = llm_db.invoke([
        ("system", "你是HR数据库查询专家，用 search_hr 工具查数据。回答简洁。"),
        *state["messages"],
    ])

    # 如果 LLM 请求了工具，执行它
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_outputs = []
        for tc in response.tool_calls:
            tool = next(t for t in [search_hr] if t.name == tc["name"])
            result = tool.invoke(tc["args"])
            tool_outputs.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        return {"messages": [response] + tool_outputs}

    return {"messages": [response]}


def kb_agent_node(state: MultiState) -> dict:
    """
    知识库问答 Agent
    工具: search_policy (制度检索)
    """
    llm_kb = llm.bind_tools([search_policy])
    response = llm_kb.invoke([
        ("system", "你是HR制度问答专家，用 search_policy 工具查制度。回答简洁。"),
        *state["messages"],
    ])

    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_outputs = []
        for tc in response.tool_calls:
            tool = next(t for t in [search_policy] if t.name == tc["name"])
            result = tool.invoke(tc["args"])
            tool_outputs.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        return {"messages": [response] + tool_outputs}

    return {"messages": [response]}


def ops_agent_node(state: MultiState) -> dict:
    """简历/流程 Agent（没有具体工具，直接让 LLM 回答）"""
    response = llm.invoke([
        ("system", "你是HR简历解析和流程引导专家。引导用户完成入职/转正/离职流程。"),
        *state["messages"],
    ])
    return {"messages": [response]}


# ═══════════════════════════════════════════════════════════
# 3. 路由函数
# ═══════════════════════════════════════════════════════════
def domain_router(state: MultiState) -> Literal["db", "kb", "ops"]:
    """
    把 domain 字段映射到对应的节点名。
    这个函数可以被 conditional_edges 直接用。
    """
    return state["domain"]


# ═══════════════════════════════════════════════════════════
# 4. 构建图
# ═══════════════════════════════════════════════════════════
graph = StateGraph(MultiState)

graph.add_node("router", router_node)
graph.add_node("db", db_agent_node)
graph.add_node("kb", kb_agent_node)
graph.add_node("ops", ops_agent_node)

graph.add_edge(START, "router")

# 条件边：根据 domain 字段的值，分发到对应的 Agent
graph.add_conditional_edges(
    "router",        # 从 router 节点出发
    domain_router,   # 用 domain_router 函数决定去哪
    {                # 返回值 → 目标节点的映射
        "db": "db",
        "kb": "kb",
        "ops": "ops",
    },
)

# 三个 Agent 完成后都直接到 END
graph.add_edge("db", END)
graph.add_edge("kb", END)
graph.add_edge("ops", END)

multi_app = graph.compile()
```

---

## 四、模式二：Supervisor 监督者（最推荐）

**架构图**：

```
START
  │
  ▼
┌────────────────────────────────────┐
│         Supervisor 节点             │
│  "已查了数据库，还需查制度，派给KB"   │
│  或者 "任务完成，输出 FINISH"       │
└──────┬──────────┬──────────┬──────┘
       │          │          │
  ┌────▼──┐  ┌───▼───┐  ┌──▼─────┐
  │ DB    │  │ KB    │  │ Ops    │   ← Worker Agents
  │ Agent │  │ Agent │  │ Agent  │
  └────┬──┘  └───┬───┘  └──┬─────┘
       │          │          │
       └──────────┴──────────┘
                  │
            回到 Supervisor（循环！）
```

**核心区别**：Worker 结束后不是去 END，而是**回到 Supervisor 继续判断**。

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, ToolMessage

# ═══════════════════════════════════════════════════════════
# State 定义
# ═══════════════════════════════════════════════════════════
class SupervisorState(TypedDict):
    # messages 存储完整的对话历史（用户问题 + 各 Agent 输出 + 工具结果）
    messages: Annotated[list, add_messages]
    # next_agent — Supervisor 每次决策后写入，告诉图下一步去哪
    next_agent: str


# ═══════════════════════════════════════════════════════════
# Worker Agent 工厂函数
# ═══════════════════════════════════════════════════════════
# 三个 Worker 结构相同，只是 system_prompt 和 tools 不同
# 用工厂函数避免重复代码

def make_worker(
    name: str,                          # Agent 名称（日志用）
    system_prompt: str,                 # 这个 Agent 的 System Prompt
    available_tools: list,              # 这个 Agent 绑定的工具
    llm_instance: ChatOpenAI,           # LLM 实例
):
    """
    创建一个 Worker Agent 节点函数。

    每个 Worker 的职责:
    1. 读取全局 messages（包含之前所有 Agent 的对话）
    2. 用 bind_tools 绑定自己的专属工具
    3. 调用 LLM，如果需要调工具就执行
    4. 把结果写回 messages

    Worker 不关心"我该不该干活"——那是 Supervisor 的判断
    Worker 只关心"把给我的任务做好"
    """

    def worker_node(state: SupervisorState) -> dict:
        # 1. 绑定这个 Agent 专属的工具
        #    db_agent 只能看到 search_hr
        #    kb_agent 只能看到 search_policy
        #    这就是"职责隔离"：避免 Agent 乱调其他领域的工具
        llm_with_tools = llm_instance.bind_tools(available_tools)

        # 2. 调用 LLM
        #    state["messages"] 包含了完整的对话历史
        #    包括 Supervisor 的指令、之前 Worker 的输出等
        response = llm_with_tools.invoke([
            ("system", system_prompt),
            *state["messages"],
        ])

        # 3. 检查 LLM 是否请求了工具调用
        if not hasattr(response, "tool_calls") or not response.tool_calls:
            # 没有工具调用 → 直接返回 LLM 的文本回答
            return {"messages": [response]}

        # 4. 执行工具调用
        tool_results = []
        for tc in response.tool_calls:
            # 在 available_tools 中按 name 匹配工具函数
            tool_func = next(t for t in available_tools if t.name == tc["name"])
            print(f"  [{name}] 调用工具: {tc['name']}({tc['args']})")
            output = tool_func.invoke(tc["args"])
            # 把工具输出包装成 ToolMessage，让 LLM 能理解
            tool_results.append(ToolMessage(
                content=str(output),
                tool_call_id=tc["id"],
            ))

        # 返回 LLM 响应 + 工具执行结果
        return {"messages": [response] + tool_results}

    return worker_node


# ═══════════════════════════════════════════════════════════
# Supervisor 节点 — 整个系统的"大脑"
# ═══════════════════════════════════════════════════════════
def supervisor_node(state: SupervisorState) -> dict:
    """
    中央调度员。每次被调用时：
    1. 查看当前的 messages（包括所有 Worker 的输出）
    2. 决策：还需要哪个 Agent 干活？还是已经可以回答了？
    3. 输出 next_agent 字段，告诉图下一步去哪

    关键设计：Supervisor 本身不回答问题，它只做调度
    """

    # System Prompt 是 Supervisor 的核心
    # 明确告诉 LLM 它的角色、可选 Agent、决策规则
    system_msg = (
        "你是 HR 多智能体系统的中央调度员。"
        "你有三个 Worker Agent 可以调用：\n"
        "\n"
        "1. db_agent — 查询人事/薪酬数据库（人数、员工信息、工资等）\n"
        "2. kb_agent — 查询公司制度/政策（年假、加班、公积金等）\n"
        "3. ops_agent — 简历解析、入转调离流程引导\n"
        "\n"
        "决策规则（严格遵守！）：\n"
        "- 如果用户问题需要查数据 → 回答 'next: db_agent'\n"
        "- 如果用户问题需要查制度 → 回答 'next: kb_agent'\n"
        "- 如果用户问题关于简历/流程 → 回答 'next: ops_agent'\n"
        "- 如果一个问题需要多个 Agent（如查工资+告知公积金政策），"
        "  先选一个 Agent，等它完成后你会再次被调用，届时选下一个\n"
        "- 当所有需要的信息都收集齐了 → 回答 'next: FINISH'\n"
        "- 如果不知道选哪个 → 回答 'next: FINISH'\n"
        "\n"
        "你只能输出 'next: db_agent' / 'next: kb_agent' / 'next: ops_agent' / 'next: FINISH' 之一。"
        "不要输出其他内容。"
    )

    # 只给 Supervisor 最新几条消息（节省 token）
    # 不需要给 Supervisor 绑定工具 — 它不执行工具，只做决策
    response = llm.invoke([
        ("system", system_msg),
        *state["messages"][-10:],  # 只取最近10条，避免 token 溢出
    ])

    # 解析 LLM 的输出
    decision = response.content.strip()
    print(f"[Supervisor] 决策: {decision}")

    # 提取 "next: xxx" 中的目标
    for target in ["db_agent", "kb_agent", "ops_agent", "FINISH"]:
        if target in decision:
            return {"next_agent": target, "messages": [response]}

    # 解析失败 → 默认 FINISH
    return {"next_agent": "FINISH", "messages": [response]}


# ═══════════════════════════════════════════════════════════
# 构建 Supervisor 图
# ═══════════════════════════════════════════════════════════
def build_supervisor_graph(llm_instance):
    graph = StateGraph(SupervisorState)

    # 注册 Supervisor 和三个 Worker
    graph.add_node("supervisor", supervisor_node)

    graph.add_node("db_agent", make_worker(
        name="db_agent",
        system_prompt="你是HR数据库查询专家。用 search_hr 工具查数据，回答简洁专业。",
        available_tools=[search_hr],
        llm_instance=llm_instance,
    ))

    graph.add_node("kb_agent", make_worker(
        name="kb_agent",
        system_prompt="你是HR制度问答专家。用 search_policy 工具查制度，回答简洁专业。",
        available_tools=[search_policy],
        llm_instance=llm_instance,
    ))

    graph.add_node("ops_agent", make_worker(
        name="ops_agent",
        system_prompt="你是HR流程引导和简历解析专家。引导用户完成相关流程。",
        available_tools=[],  # ops_agent 没有工具，纯 LLM 对话
        llm_instance=llm_instance,
    ))

    # ── 定义 edge 流转 ──

    # 开始 → Supervisor
    graph.add_edge(START, "supervisor")

    # Supervisor → 条件路由（根据 next_agent 字段决定去向）
    def supervisor_router(state: SupervisorState) -> str:
        """把 next_agent 字段映射为实际的边"""
        target = state["next_agent"]
        if target == "FINISH":
            return END
        return target  # "db_agent" / "kb_agent" / "ops_agent"

    graph.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "db_agent": "db_agent",
            "kb_agent": "kb_agent",
            "ops_agent": "ops_agent",
            END: END,
        },
    )

    # 三个 Worker 完成后 → 回到 Supervisor（核心！）
    # 这就是为什么 Supervisor 能串行调度多个 Worker
    graph.add_edge("db_agent", "supervisor")
    graph.add_edge("kb_agent", "supervisor")
    graph.add_edge("ops_agent", "supervisor")

    return graph.compile()


supervisor_app = build_supervisor_graph(llm)

# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

# 用例1: 简单问题（只需一个 Agent）
result = supervisor_app.invoke({
    "messages": [HumanMessage(content="公司年假有多少天？")],
    "next_agent": "",
})
print(f"最终回答: {result['messages'][-1].content}")
# 预期流程: Supervisor→kb_agent→Supervisor→FINISH
# 预期回答: "公司年假入职满1年享5天，满3年10天，满10年15天"

# 用例2: 复杂问题（需要两个 Agent 串行）
result = supervisor_app.invoke({
    "messages": [HumanMessage(content="查全集团有多少人，然后告诉我公积金政策")],
    "next_agent": "",
})
# 预期流程:
#   Supervisor → "next: db_agent"
#   db_agent → "1365人" 
#   Supervisor → "next: kb_agent"  (因为还要查制度)
#   kb_agent → 公积金政策
#   Supervisor → "next: FINISH"
print(f"最终回答: {result['messages'][-1].content}")
```

---

## 五、模式三：Agent as Tool 交接

上一个模式要求 Supervisor 调度。如果你想**让 Agent 自己决定把任务交给谁**，用这个模式。

```python
# ═══════════════════════════════════════════════════════════
# 定义"交接"工具 — 这是模式的核心
# ═══════════════════════════════════════════════════════════
# 把"转交"包装成 Tool
# 主 Agent 通过调用这些 Tool 来主动交接任务
# 这和 Function Calling 完全一致：LLM 决定调 transfer_to_xxx

@tool
def transfer_to_db():
    """当你需要查询人事/薪酬数据库时调用此工具，转交给数据库专家"""
    # 返回值不重要，系统通过 tool_calls 中的 name 判断
    return "已转交数据库专家"


@tool  
def transfer_to_kb():
    """当你需要查询公司制度/政策/规定时调用此工具，转交给知识库专家"""
    return "已转交知识库专家"


@tool
def finish_task():
    """当你已经完成了用户的请求，准备好输出最终答案时调用"""
    return "任务完成"


# ═══════════════════════════════════════════════════════════
# 主 Agent — 自己决定要不要交接、交接给谁
# ═══════════════════════════════════════════════════════════
MAIN_PROMPT = """你是HR助手的主Agent。你可以：
1. 直接回答简单问题
2. 调用 transfer_to_db 把数据库查询转给专家
3. 调用 transfer_to_kb 把制度政策查询转给专家
4. 调用 finish_task 表示任务完成

如果问题涉及数据查询，必须先 transfer_to_db。"""


def main_agent_node(state: SupervisorState) -> dict:
    """
    主 Agent:
    - 绑定 transfer 工具 + finish_task
    - 如果调用了 transfer，图系统会把它路由到对应的 Worker
    - 如果调用了 finish_task，结束
    """
    llm_main = llm.bind_tools([transfer_to_db, transfer_to_kb, finish_task])
    response = llm_main.invoke([
        ("system", MAIN_PROMPT),
        *state["messages"],
    ])

    # 如果有工具调用，返回让图路由
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_name = response.tool_calls[0]["name"]
        if tool_name == "transfer_to_db":
            print("[Main Agent] 主动转交给 db_agent")
            return {"messages": [response], "next_agent": "db_agent"}
        elif tool_name == "transfer_to_kb":
            print("[Main Agent] 主动转交给 kb_agent")
            return {"messages": [response], "next_agent": "kb_agent"}
        elif tool_name == "finish_task":
            print("[Main Agent] 任务完成")
            return {"messages": [response], "next_agent": "FINISH"}

    return {"messages": [response], "next_agent": "FINISH"}


def build_handoff_graph(llm_instance):
    graph = StateGraph(SupervisorState)

    graph.add_node("main", main_agent_node)
    graph.add_node("db_agent", make_worker("db", "你是数据库专家", [search_hr], llm_instance))
    graph.add_node("kb_agent", make_worker("kb", "你是制度专家", [search_policy], llm_instance))

    graph.add_edge(START, "main")

    # Worker 完成后回到 main Agent 继续
    graph.add_edge("db_agent", "main")
    graph.add_edge("kb_agent", "main")

    # main 的条件路由
    def main_router(state):
        return state["next_agent"] if state["next_agent"] != "FINISH" else END

    graph.add_conditional_edges("main", main_router, {
        "db_agent": "db_agent",
        "kb_agent": "kb_agent",
        END: END,
    })

    return graph.compile()
```

---

## 六、四种模式决策指南

```
你的场景是什么？
│
├── 问题类型固定，Agent 之间不需要协作
│   → 模式一：条件路由
│   特点: 简单、快速、可预测
│
├── 问题涉及多个领域，需要串行执行多个 Agent
│   → 模式二：Supervisor（推荐）
│   特点: 集中调度、串行协作、可解释
│
├── Agent 之间需要灵活"转交"
│   → 模式三：Agent as Tool
│   特点: 去中心化、Agent 自主决策
│
└── 组织有多个团队，每个团队有内部的 Agent
    → 层级 Supervisor（Supervisor 的嵌套版）
    特点: 复杂、适合大型系统
```

**你的项目最适合：Supervisor 模式。**

原因：
- ✅ DB 和 KB 领域明确分离
- ✅ 确实存在跨领域问题（"查张三工资+告知公积金政策"）
- ✅ Supervisor 可解释、易调试
- ✅ 从单 Agent 迁移改动可控
