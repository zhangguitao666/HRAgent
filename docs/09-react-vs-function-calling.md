# ReAct Agent vs Function Calling：原理、区别与实践

> 本文深入解释两种 Agent 调用机制的底层原理，以及它们与 `create_react_agent` 的关系。

---

## 一、先分清三个概念

很多人的困惑源于这三个词混用。先定义清楚：

| 概念 | 是什么 | 类比 |
|------|--------|------|
| **ReAct** | 一种**推理范式**（Reasoning + Acting），论文提出 | 方法论 |
| **Function Calling** | 一种**API 机制**，LLM 服务商提供的接口能力 | 通信协议 |
| **create_react_agent** | LangGraph 提供的一个**调度引擎**（图循环） | 执行器 |

三者关系：**调度引擎 (`create_react_agent`) + 通信协议 (FC 或 Prompt) = 可用的 Agent**。

---

## 二、ReAct 模式（Prompt 驱动）

### 原理

不给 LLM 任何特化 API，纯粹靠**一段文字指令**告诉它"按格式输出"。

```
System Prompt（简化）:
"""
你可以使用以下工具：
- query_hr: 查询人事数据，参数 question

回答格式：
Thought: 你的分析
Action: query_hr
Action Input: {"question": "各部门人数统计"}
Observation: 工具返回的结果
...（Thought/Action/Observation 可重复）
Final Answer: 最终回答
"""
```

### LLM 的响应内容（纯文本）

```
Thought: 用户想要各部门人数统计，这是一个数据查询问题，我需要调用 query_hr。

Action: query_hr
Action Input: {"question": "各部门人数统计"}
```

然后 Agent 引擎（`create_react_agent`）**用正则解析**这段文本，提取 `Action` 和 `Action Input`，找到对应函数执行。

### 数据流

```
  LLM 输出一串文字
  "Thought:... Action: query_hr Action Input: {...}"
        │
        ▼
  create_react_agent 用正则
  re.search(r"Action:\s*(.+?)\n")
  提取 → "query_hr"
        │
        ▼
  执行 Python 函数 query_hr(...)
        │
        ▼
  把结果拼成 "Observation: 共190条记录"
  追加到 messages，再发给 LLM
        │
        ▼
  LLM 看到 Observation，生成 Final Answer
```

### 特点

| 优点 | 缺点 |
|------|------|
| 任何模型都能用（纯文本协议） | 格式偶尔出错，需要重试 |
| 思考过程完全可见 | 正则解析脆弱 |
| 不依赖 API 特性 | Prompt 占用大量 token |

---

## 三、Function Calling 模式（API 驱动）

### 原理

LLM 服务商的 API 支持一个特殊参数 `tools`，你把函数签名以 **JSON Schema** 格式传给 API。LLM **不用文本写出调用**，而是在响应结构体里返回 `tool_calls` 字段。

### 实际发给 API 的请求

```json
{
  "model": "minimax-m2.5",
  "messages": [
    {"role": "user", "content": "各部门人数统计"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "query_hr",
        "description": "查询人事数据（员工信息、部门、组织架构...）",
        "parameters": {
          "type": "object",
          "properties": {
            "question": {
              "type": "string",
              "description": "自然语言问题"
            }
          },
          "required": ["question"]
        }
      }
    }
  ]
}
```

### LLM 的响应（结构化，不是文本）

```json
{
  "choices": [{
    "message": {
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "query_hr",
          "arguments": "{\"question\": \"各部门人数统计\"}"
        }
      }]
    }
  }]
}
```

注意：`tool_calls` 是 API 响应里的**独立字段**，不是 content 里的文字。

### 数据流

```
  请求 API（带 tools 参数）
        │
        ▼
  LLM 返回
  message.tool_calls = [{name: "query_hr", arguments: {question: "..."}}]
  message.content = null
        │
        ▼
  create_react_agent 读取 tool_calls
  不需要正则解析，直接 dict 取值
        │
        ▼
  执行 query_hr(...)
        │
        ▼
  把结果拼成 ToolMessage
  追加到 messages，再发给 LLM
        │
        ▼
  LLM 返回 content = "各部门人数如下..."
```

### 特点

| 优点 | 缺点 |
|------|------|
| 调用准确性 100%（结构化保证） | 依赖模型 API，不兼容所有模型 |
| 不依赖正则解析 | 思考过程不可见（黑盒） |
| 节省 token（工具以 JSON Schema 传递） | 某些模型实现不完整 |
| 支持**并行调用** | 调试困难 |

---

## 四、核心区别对照

```
                    ReAct (Prompt 驱动)              Function Calling (API 驱动)
                    ────────────────────              ──────────────────────────
工具通知方式          在 System Prompt 里写文字          API 的 tools 参数（JSON Schema）

LLM 输出格式         纯文本                            结构化 tool_calls 字段
                    "Action: query_hr"               {name: "query_hr", arguments: {...}}

如何解析             正则表达式 re.search()           直接 dict 取值（不需解析）

调用准确率           约 90%（偶尔格式错误）            约 99.9%（API 保证结构）

思考过程             可见（Thought 文本输出）          不可见（模型内部完成）

并行调用             不支持                           支持

模型要求             任何模型                         仅支持 FC API 的模型

token 消耗           高（工具描述写 prompt 里）         低（工具以 JSON 传）

minimax-m2.5 兼容    可用（已验证）                    可能有问题（之前 structured output 失败）

项目当前使用         之前                               现在
```

---

## 五、`create_react_agent` 的角色

**它是调度引擎，不是推理模式**。无论用 ReAct 还是 FC，`create_react_agent` 都做同一件事：

```
while True:
    msg = llm.invoke(messages)      # 让 LLM 推理下一步

    if msg 包含 tool_calls:          # FC 模式
        for tc in msg.tool_calls:
            result = tools[tc.name](tc.args)  # 执行工具
            messages.append(ToolMessage(result))

    elif msg 内容匹配 "Action:..."   # ReAct 模式
        action, args = parse(msg.content)    # 正则解析
        result = tools[action](args)
        messages.append(ObservationMessage(result))

    else:
        return msg.content           # 最终回答，结束
```

**所以在项目中**：

```python
# == ReAct 模式 ==
agent = create_react_agent(llm, [query_database])
# LLM 用文本格式输出工具调用 → Agent 正则解析

# == FC 模式（当前） ==
agent = create_react_agent(llm.bind_tools([query_hr, query_salary]), [query_hr, query_salary])
# LLM 用 tool_calls 输出工具调用 → Agent 直接取值
```

两次传入工具列表的原因：

| 传参位置 | 作用 |
|---------|------|
| `llm.bind_tools([...])` | 把工具转成 JSON Schema，**作为 LLM API 请求的 tools 参数**发出去——让 LLM 知道有哪些能力 |
| `create_react_agent(..., [...])` | 告诉 Agent 引擎**LLM 返回的 tool_calls 对应哪个 Python 函数**——让引擎知道怎么执行 |

必须一致，否则 LLM 说要调用 `query_hr` 但 Agent 引擎找不到这个函数。

---

## 六、FC 在本项目中的实际好处

### 1. 自动选库——不用关键词路由

```python
# 旧：需要 _is_salary() 关键词判断
if "工资" in question:
    db = "薪酬库"
else:
    db = "人事库"

# 新：LLM 自己根据函数描述选择
# query_hr: "查询人事数据（员工信息、部门...）"
# query_salary: "查询薪酬/社保/公积金数据..."
# LLM 看问题语义 → 自己决定调哪个
```

### 2. 删掉了 40 行 `<think>` 过滤代码

ReAct 模式下 LLM 在 content 里输出思考，需要用 `token_buffer` 逐一检测 `><think>`。FC 模式下 `tool_calls` 在独立字段，content 里不会出现 `<think>`。

### 3. 可并行调两库

```json
// FC 允许一次返回多个 tool_calls
{
  "tool_calls": [
    {"name": "query_hr", "arguments": {"question": "全公司人数"}},
    {"name": "query_salary", "arguments": {"question": "总薪酬支出"}}
  ]
}
```

---

## 七、什么时候用哪种？

| 场景 | 推荐 |
|------|------|
| 模型支持 FC API（GPT-4o / DeepSeek / 部分 minimax 兼容） | Function Calling |
| 开源本地模型（Qwen / Llama） | ReAct（Prompt 兼容性最广） |
| 需要调试 Agent 推理过程 | ReAct（Thought 可见） |
| 生产环境追求稳定性 | Function Calling |
| 工具很多（10+）需要并行 | Function Calling |
