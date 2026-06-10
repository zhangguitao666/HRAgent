# 模块6B：LangGraph — Agent 编排框架

> **目标**：理解 LangGraph 是什么，它与 LangChain Chain 的本质区别，以及为什么它是构建 Agent 的推荐方式

---

## 什么是 LangGraph？

**LangGraph = 用图（Graph）来编排 AI 工作流的框架**。

LangChain 的 Chain 是**线性管道**：`A → B → C → D`，只能一路走到头。但现实中的 AI 应用需要**循环、分支、条件跳转**，比如 Agent 的 Think→Act→Observe 循环就不是一条直线。

```
LangChain Chain（线性）                LangGraph（图，支持循环+分支）
                                       
  A → B → C → D                             ┌─────┐
  只能往前走                                  │ START│
                                              └──┬──┘
                                                 ▼
                                            ┌─────────┐
                                      ┌─────│ Agent   │◀──────┐
                                      │     └────┬────┘       │
                                      │          │            │
                                      │     ┌────▼────┐       │
                                      │     │ 判断     │       │
                                      │     └─┬───┬───┘       │
                                      │  继续调│   │可以回答了  │
                                      │   工具  │   │          │
                                      │     ┌───▼─┐ │          │
                                      │     │ Tool │ │          │
                                      │     └──┬──┘ │          │
                                      │        │    │          │
                                      └────────┘    │          │
                                                    ▼          │
                                              ┌──────────┐     │
                                              │   END    │     │
                                              └──────────┘     │
                                                        
                                        支持：循环、条件分支、人机交互暂停
```

---

## LangGraph 的四大核心概念

### 1. State（状态）

State 是贯穿整个图流转的**共享数据容器**，每一步都能读写它。

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph

# 定义 State 结构
class AgentState(TypedDict):
    messages: list       # 对话消息列表
    tool_results: dict   # 工具调用结果
    iteration: int       # 当前循环次数
```

Agent 执行过程中，每轮循环都会更新这个 State。就像"记事本"在整个工作流中传递，每个节点在上面写东西，下个节点接着看。

### 2. Node（节点）

Node 是图中的**执行单元**——一段处理逻辑。每个 Node 是一个函数：

```python
# 两个节点：一个负责推理，一个负责执行工具
def call_model(state: AgentState) -> dict:
    """调用 LLM 推理"""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def call_tool(state: AgentState) -> dict:
    """执行工具调用"""
    last_msg = state["messages"][-1]
    result = execute_tool(last_msg.tool_calls[0])
    return {"tool_results": result}
```

### 3. Edge（边）

Edge 是节点之间的**连接线**，决定执行流程。有两种：

```python
# 普通边：无条件跳转 A → B
graph.add_edge("call_model", "call_tool")

# 条件边：根据状态决定跳转方向
def should_continue(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if last_msg.tool_calls:
        return "call_tool"     # 有工具调用 → 继续
    return "__end__"           # 没有 → 结束
```

### 4. Graph（图）

把节点和边组合起来，就是 Graph：

```python
from langgraph.graph import StateGraph

builder = StateGraph(AgentState)

# 添加节点
builder.add_node("call_model", call_model)
builder.add_node("call_tool", call_tool)

# 添加边
builder.set_entry_point("call_model")        # 入口
builder.add_conditional_edges("call_model", should_continue)  # 条件跳转
builder.add_edge("call_tool", "call_model")  # 回到 call_model（循环）

graph = builder.compile()  # 编译成可执行的图
```

---

## LangGraph vs LangChain Chain：本质区别

| 维度 | LangChain Chain | LangGraph |
|------|----------------|-----------|
| **结构** | 线性管道 `A\|B\|C` | 有向图（节点+边） |
| **循环** | 不支持 | **支持循环** |
| **条件分支** | 只能用 `RunnableBranch`（笨重） | **原生条件边** |
| **状态管理** | 每步独立，隐式传递 | **显式 State**，贯穿全流程 |
| **暂停/恢复** | 不支持 | 支持 Human-in-the-loop（人机交互暂停） |
| **调试** | 黑盒 | 每一步的 State 都可查看 |
| **适用场景** | 简单问答、翻译、摘要 | Agent、复杂多步推理、工作流编排 |
| **复杂度** | 极简 | 需要理解 Node/Edge/State |

**一句话总结**：Chain 是**直行道**，Graph 是**立交桥**。

---

## 你已经在用 LangGraph 了

项目中这行代码：

```python
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(llm, tools)
```

`create_react_agent` 内部就是构建了一个下面这样的图：

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         ▼
                   ┌──────────┐
              ┌───→│ call_model│─────┐
              │    │ (LLM推理) │     │
              │    └──────────┘     │
              │                    ▼
              │             ┌────────────┐
              │             │ 条件判断     │
              │             │ has_tool?   │
              │             └──┬──────┬──┘
              │           no   │      │ yes
              │                ▼      ▼
              │          ┌──────┐  ┌──────────┐
              │          │ END  │  │ call_tool│
              │          └──────┘  │ (执行工具) │
              │                    └────┬─────┘
              │                         │
              └─────────────────────────┘
```

这就是 Agent 循环的本质：**LLM 推理 → 需要工具？→ 调工具拿结果 → 回到推理 → 够了？→ 结束**。

`create_react_agent` 帮你省去了手写这些 Node、Edge、State 的代码，但它底层就是 LangGraph 图。

---

## 什么时候该自己写图而不是用 create_react_agent？

| 场景 | 建议 |
|------|------|
| 标准 Agent（调工具、回答问题） | `create_react_agent()` 够用 |
| 多个 Agent 协作（招聘Agent→初筛→面试Agent） | 自己用 LangGraph 写 |
| 需要人类审批才能继续（调工具前等HR确认） | 自己写，加 interrupt |
| 复杂工作流（查库→调API→写报告→发送邮件） | 自己写 |
| 需要并行多个步骤 | 自己写 |

---

## 高级示例：带 Human-in-the-loop 的 Agent

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

# 编译图时传入 checkpointer，实现暂停/恢复
memory = MemorySaver()
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["call_tool"],  # 调用工具前暂停，等人确认
)

# 第一次执行被暂停
config = {"configurable": {"thread_id": "1"}}
result = graph.invoke({"messages": [("user", "帮我查张三的年假")]}, config)
# → 暂停在 call_tool 之前，返回当前 State

# 人类确认后继续执行
graph.invoke(None, config)  # 传入 None 表示继续
```

---

## 小结

- **LangGraph** 是用**图**来编排 AI 工作流的框架，支持循环、分支、暂停
- **State** 是共享数据容器，**Node** 是执行单元，**Edge** 是跳转规则
- `create_react_agent()` 底层就是一个预编译好的 LangGraph 图
- 简单 Agent 用它就够了，复杂多 Agent 协作才需要自己写图
- 它是 LangChain 生态的下一代编排引擎，官方主推

---

## 附：深入理解 LangGraph

### LangGraph 的定位

LangGraph 是 LangChain 团队出的**有状态工作流编排框架**。它把 AI 应用的执行流程从"一根水管"变成"一张路网"。

```
LangChain Chain（水管）          LangGraph（路网）
   A → B → C → D                   ┌─────┐
   只能往前走                       │  A  │
   不能回头                         └──┬──┘
   不能分叉                            │
   不能循环              ┌─────────────┼─────────────┐
                         ▼             ▼             ▼
                      ┌─────┐      ┌─────┐      ┌─────┐
                      │  B  │      │  C  │      │  D  │
                      └──┬──┘      └──┬──┘      └─────┘
                         │            │
                         └─────┬──────┘
                               ▼
                           ┌──────┐
                           │ 判断  │
                           └──┬─┬─┘
                         true │ │ false
                         ┌────┘ └────┐
                         ▼           ▼
                       ┌─────┐    ┌─────┐
                       │回 B │    │ END │
                       └─────┘    └─────┘
                      支持：循环、分支、并行、暂停恢复
```

### 四核心概念

#### 1. State（状态）

**State 是一个共享笔记本，所有节点读写同一个 TypedDict 对象。**

```python
class AgentState(TypedDict):
    messages: list       # 对话历史
    tools_called: int    # 调了几次工具
    final_answer: str    # 最终回答
```

类比：你去政府办事，手里拿着一张流转单，每个窗口在你单子上盖章签字，下个窗口看到前面的记录就知道该做什么。这张流转单就是 State。

#### 2. Node（节点）

每个节点是一个纯函数——接收 State，返回 State 的部分更新。

```python
def call_llm(state: AgentState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}  # 只返回新增的消息

def call_tool(state: AgentState) -> dict:
    result = tool(state["messages"][-1])
    return {"messages": [ToolMessage(result)]}
```

#### 3. Edge（边）

节点之间的箭头，决定流程往哪走。两种类型：

```python
# 普通边：无条件跳转
graph.add_edge("A", "B")

# 条件边：根据 State 动态决定走哪条路
def should_continue(state):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "call_tool"  # 有工具要调 → 循环回去
    return "__end__"         # 可以结束了

graph.add_conditional_edges("call_llm", should_continue, {
    "call_tool": "call_tool",
    "__end__": END
})
```

#### 4. Graph（图）

把节点和边组装起来，编译成可执行的图：

```python
builder = StateGraph(AgentState)
builder.add_node("call_llm", call_llm)
builder.add_node("call_tool", call_tool)
builder.set_entry_point("call_llm")
builder.add_conditional_edges("call_llm", should_continue)
builder.add_edge("call_tool", "call_llm")  # 回到 LLM → 形成循环
graph = builder.compile()
```

### 状态机是什么

**状态机** = 一个系统，有有限种"状态"，在事件触发下按规则切换状态。

```
一盏灯的开关就是一个状态机：

   [关] ──按──→ [开] ──按──→ [关]
     ↑                        │
     └──────── 按 ────────────┘
     
   状态：关、开（2种）
   事件：按开关
   规则：每按一次，状态翻转
```

**在 LangGraph 里，Agent 就是一个状态机**：

```
   [推理中] ──LLM返回tool_call──→ [执行工具] ──工具完成──→ [推理中]
       │                                                     │
       └── LLM返回content ──→ [结束]
       
   状态：推理中、执行工具、结束（3种）
   事件：LLM 的返回内容、工具的执行结果
   规则：有 tool_call → 执行工具，没 tool_call → 结束
```

**State 的本质就是快照**：每走一步，State 就更新一次：

```
t=0: {messages: ["你好"], step: 0}
t=1: {messages: ["你好", "你好！"], step: 1}
t=2: {messages: ["你好", "你好！", "查张三"], step: 2}
```

下个节点看到的是最新的 State。这就是"有状态"——系统记得之前发生了什么，不会被重置。

### 项目中 LangGraph 的实际用法

```python
# server/api/query.py 的流式执行
async for event in agent.astream_events(
    {"messages": input_messages}, version="v2",
):
    # 每个事件都是状态机的一次状态变化
    if kind == "on_tool_start":    # 进入工具调用
        pending_tools += 1
        can_emit = False           # 暂停回答输出
        yield progress
    
    if kind == "on_tool_end":      # 工具执行完
        pending_tools -= 1
        if pending_tools == 0:
            can_emit = True        # 恢复回答输出
        yield progress
    
    if kind == "on_chat_model_stream" and can_emit:
        yield token  # 逐字推送最终回答
```

`pending_tools` 就是状态机的状态变量——控制 `can_emit` 的值，从而控制输出行为。这就是 LangGraph 比 Chain 强大的地方。

### 与 Chain 的本质区别

| | Chain | LangGraph |
|------|-------|-----------|
| 结构 | 线性管道 A→B→C | 有向图，节点+边 |
| 循环 | 不支持 | 原生支持 |
| 条件 | `RunnableBranch`（笨重） | 条件边（原生） |
| 状态 | 隐式，每步独立 | 显式 State 对象 |
| 暂停恢复 | 不支持 | 支持 Human-in-the-loop |

> Chain 是**直行道**，LangGraph 是**立交桥 + 红绿灯**。

👉 返回：[Agents & Tools](06-agents-tools.md) | 下一模块：[HR 助手实战](07-hr-assistant.md)
