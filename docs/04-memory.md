# 模块4：记忆系统

> **目标**：理解 LLM 的无状态本质，掌握 LangChain 的 Memory 机制实现多轮对话

---

## 4.1 LLM 是"金鱼脑"

重要事实：**LLM 每次调用都是独立的，它不记得上次跟你说了什么。**

```python
# 第一次对话
llm.invoke("我叫张三")
# → "你好张三！"  ← 知道了你的名字

# 第二次对话（没有记忆的话）
llm.invoke("我叫什么名字？")
# → "我不知道你的名字"  ← 全忘了！
```

**解决方案**：每次请求都把历史对话带到 prompt 里。

```
第1轮: [Human: 我叫张三, AI: 你好张三]
第2轮: [Human: 我叫张三, AI: 你好张三, Human: 我叫什么名字？]
                                     ↑ 之前的对话作为上下文
```

这就是 LangChain Memory 做的事：**管理对话历史**。

---

## 4.2 ChatMessageHistory：记忆的底层

```python
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

# 创建一段对话历史
history = InMemoryChatMessageHistory()

history.add_message(HumanMessage(content="你好，我是新员工"))
history.add_message(AIMessage(content="你好！欢迎加入公司，有什么可以帮你的？"))
history.add_message(HumanMessage(content="年假怎么算？"))
history.add_message(AIMessage(content="入职满1年享有5天年假..."))

# 读取历史
for msg in history.messages:
    print(f"[{msg.type}] {msg.content}")

# 输出：
# [human] 你好，我是新员工
# [ai] 你好！欢迎加入公司，有什么可以帮你的？
# [human] 年假怎么算？
# [ai] 入职满1年享有5天年假...
```

**消息类型**：
| 类型 | 用途 |
|------|------|
| `HumanMessage` | 用户说的话 |
| `AIMessage` | AI 的回复 |
| `SystemMessage` | 系统指令（角色设定） |
| `ToolMessage` | 工具调用的返回结果 |

---

## 4.3 RunnableWithMessageHistory：自动记忆

LangChain 提供了自动管理历史的包装器：

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
)

# 关键：prompt 中要有 MessagesPlaceholder 放历史消息
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个HR助手，热情专业地回答员工问题。"),
    MessagesPlaceholder(variable_name="history"),  # ← 历史消息插这里
    ("human", "{input}"),
])

chain = prompt | llm

# ============================================================
# 管理"会话" —— 不同的 session_id 有独立的记忆
# ============================================================
store = {}  # 内存存储，生产环境应换成 Redis/数据库

def get_session_history(session_id: str):
    """根据 session_id 获取或创建对应的对话历史"""
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

chain_with_memory = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",      # 用户输入所在的 key
    history_messages_key="history",  # 历史消息在 prompt 中的 key
)

# ============================================================
# 多轮对话测试
# ============================================================
session = "employee_001"

# 第一轮
resp1 = chain_with_memory.invoke(
    {"input": "我叫张三，工号EMP001"},
    config={"configurable": {"session_id": session}}
)
print(f"AI: {resp1.content}")

# 第二轮（AI 应该记得名字）
resp2 = chain_with_memory.invoke(
    {"input": "刚才我说我叫什么？"},
    config={"configurable": {"session_id": session}}
)
print(f"AI: {resp2.content}")

# 可以看到 store 中的对话历史
print(f"\n对话历史条目数: {len(store[session].messages)}")
```

---

## 4.4 记忆的类型选择

| 记忆类型 | 特点 | 适用场景 |
|---------|------|---------|
| `InMemoryChatMessageHistory` | 存内存，进程重启就没了 | 原型/测试 |
| `ConversationBufferMemory` | 保留**全部**历史 | 短对话 |
| `ConversationSummaryMemory` | 只保留**摘要** | 长对话 |
| `ConversationBufferWindowMemory` | 只保留最近**K轮** | 有限上下文 |
| `RunnableWithMessageHistory` | 官方推荐，按 session 隔离 | 生产环境 |

> LangChain 0.3 推荐用 `RunnableWithMessageHistory`，老 API 的 `ConversationBufferMemory` 等已弃用。

---

## 4.5 对话摘要（处理长对话）

当对话变长，可能超出 LLM 的上下文窗口（比如 4096 tokens）。解决方案：**自动摘要**。

```python
from langchain_core.messages import SystemMessage, trim_messages

# trim_messages 自动裁剪超出限制的历史消息
trimmer = trim_messages(
    max_tokens=2000,           # 历史消息上限（tokens）
    strategy="last",           # 保留最后的消息
    token_counter=llm,         # 用 LLM 自身的 tokenizer 计数
    include_system=True,       # 始终保留 system prompt
)

# 应用 trimmer
chain_with_trim = prompt | trimmer | llm
```

---

## 4.6 练习：带记忆的 HR 对话助手

```python
"""
练习：带记忆的 HR 对话助手
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
    temperature=0.7,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是HR小助手，热情专业。{extra_context}"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

store = {}

def get_history(session_id):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

chain_with_memory = RunnableWithMessageHistory(
    prompt | llm,
    get_history,
    input_messages_key="input",
    history_messages_key="history",
)

def chat(session_id, message, context=""):
    response = chain_with_memory.invoke(
        {"input": message, "extra_context": context},
        config={"configurable": {"session_id": session_id}}
    )
    return response.content
```

---

## 4.7 记忆系统核心要点

```
                    ┌──────────────────┐
                    │  RunnableWith    │
                    │  MessageHistory  │ ← 自动注入和保存历史
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    InMemoryHistory    SQLHistory    RedisHistory
      (开发测试)        (持久化)       (高性能)
```

**记忆系统的核心就是三件事**：
1. **存储**对话历史（内存/数据库/Redis）
2. **注入**历史到 prompt（`MessagesPlaceholder`）
3. **裁剪**超长的历史（`trim_messages`）

---

## 小结

- LLM 本身不记忆，需要你帮它"记住"
- `RunnableWithMessageHistory` 是官方推荐方式
- 按 `session_id` 隔离不同用户的对话
- 长对话需要 `trim_messages` 裁剪

👉 下一模块：[RAG 检索增强生成](05-rag.md)
