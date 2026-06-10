# 模块2：LangChain 核心概念入门

> **目标**：掌握 LangChain 的"三件套"——Model、Prompt、Chain，理解 LCEL 表达式语言

---

## 2.1 LangChain 的设计哲学

LangChain 的一切都围绕一个核心思想：**把 LLM 调用变成可组合的"链"**。

```
传统方式（每次都手动拼接）:
  构造prompt → 调用API → 解析结果 → 用结果做下一步 → 再构造prompt → ...

LangChain 方式（声明式链）:
  chain = prompt | model | parser
  result = chain.invoke(...)
```

就像 Shell 管道：`cat file | grep keyword | sort`，LangChain 用 `|` 把 AI 组件串成管道。

---

## 2.2 第一个 Chain：Hello World

创建 `src/basics/01_hello_chain.py`：

```python
"""
LangChain 核心概念演示：Model、Prompt、Chain
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ============================================================
# 第一步：创建模型 (Model)
# ============================================================
llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
    temperature=0.7,
)

# ============================================================
# 第二步：定义提示模板 (Prompt Template)
# ============================================================
# {language} 和 {topic} 是占位符，运行时会被替换
prompt = ChatPromptTemplate.from_template(
    "请用{language}语言，写一首关于{topic}的短诗，4行以内。"
)

# ============================================================
# 第三步：绑定输出解析器 (Parser)
# ============================================================
# StrOutputParser 就是把 LLM 返回的对象转换为纯文本字符串
parser = StrOutputParser()

# ============================================================
# 第四步：用 LCEL 管道连成链 (Chain)
# ============================================================
# 这就是 LangChain 的核心魔法：用 | 串联组件
chain = prompt | llm | parser

# ============================================================
# 第五步：执行链
# ============================================================
result = chain.invoke({
    "language": "中文",
    "topic": "编程"
})

print("=" * 50)
print("Chain 执行结果：")
print(result)
print("=" * 50)
```

运行：
```powershell
python src\basics\01_hello_chain.py
```

---

## 2.3 深入理解三个组件

### 2.3.1 Model（模型）

Model 就是 LLM。LangChain 中有两种模型类型：

```python
# 对话模型（Chat Model）：支持多轮对话
from langchain_openai import ChatOpenAI
chat_model = ChatOpenAI(model="minimax-m2.5", ...)

# 补全模型（LLM）：纯文本补全（GPT-3.5 以前用）
from langchain_openai import OpenAI
llm_model = OpenAI(model="gpt-3.5-turbo-instruct", ...)

# 发送消息给对话模型
from langchain_core.messages import HumanMessage, SystemMessage
response = chat_model.invoke([
    SystemMessage(content="你是一个诗人"),
    HumanMessage(content="写一首诗"),
])
```

> 几乎所有现代 LLM 都用 Chat Model，LLM 类型基本不用了。

### 2.3.2 Prompt Template（提示模板）

**为什么需要模板？** 因为真实的 AI 应用不是写死的 prompt，而是要根据用户输入动态生成 prompt。

```python
from langchain_core.prompts import ChatPromptTemplate

# 方式1: from_template() - 简单模板
template = ChatPromptTemplate.from_template(
    "将以下文本翻译成{language}：\n{text}"
)

# 方式2: from_messages() - 多消息模板（最常用）
template = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}专家。"),
    ("human", "{user_input}"),
])

# 模板变量通过 invoke() 传入
prompt_value = template.invoke({
    "role": "人力资源",
    "user_input": "员工试用期转正需要哪些材料？"
})

# prompt_value 是一个 ChatPromptValue，可以直接传给模型
```

### 2.3.3 Output Parser（输出解析器）

LLM 返回的是自由文本，但你的程序需要结构化数据。Parser 就是做这个转换的：

```python
# StrOutputParser: 最简单的，提取纯文本
from langchain_core.output_parsers import StrOutputParser
parser = StrOutputParser()

# 后面会学到更复杂的：
# JsonOutputParser: 提取 JSON
# PydanticOutputParser: 提取为 Pydantic 对象
# CommaSeparatedListOutputParser: 提取为列表
```

---

## 2.4 LCEL：LangChain 表达式语言

LCEL（LangChain Expression Language）是 LangChain 的"胶水语言"，核心符号是 `|`（管道符）。

### 基本语法

```python
# | 的左边输出会成为右边的输入
chain = component_a | component_b | component_c

# 等价于：
# 1. output_a = component_a.invoke(input)
# 2. output_b = component_b.invoke(output_a)
# 3. result  = component_c.invoke(output_b)
```

### 数据流示意图

```
input ──→ [PromptTemplate] ──→ [ChatModel] ──→ [OutputParser] ──→ result
           占位符替换            调用LLM          提取纯文本
```

### Runnable 协议

所有 LangChain 组件都遵守 **Runnable 协议**，这意味着它们都有：

```python
component.invoke(input)       # 同步执行，返回完整结果
component.stream(input)       # 流式执行，逐步返回
component.batch([a, b, c])    # 批量执行，并行处理
```

### RunnableParallel：并行执行

```python
from langchain_core.runnables import RunnableParallel

# 同时做两件事：写故事 + 写提纲
chain = RunnableParallel(
    story=story_chain,    # 生成故事
    outline=outline_chain, # 生成提纲
)
result = chain.invoke({"topic": "AI"})
# result = {"story": "...", "outline": "..."}
```

---

## 2.5 练习：多语言翻译链

```python
"""
练习：创建一个支持多语言、多风格翻译的链
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业翻译，翻译风格：{style}。只输出翻译结果，不要解释。"),
    ("human", "请将以下内容翻译成{language}：\n\n{text}"),
])

chain = prompt | llm | StrOutputParser()

# 测试
tests = [
    {"style": "正式商务", "language": "英文", "text": "我们公司致力于为员工提供最佳的工作体验。"},
    {"style": "口语化", "language": "日文", "text": "明天的会议推迟到下午三点。"},
]

for t in tests:
    result = chain.invoke(t)
    print(f"风格: {t['style']} | 目标语言: {t['language']}")
    print(f"结果: {result}")
    print("-" * 40)
```

---

## 2.6 核心概念速查表

| 概念 | 作用 | 类比 |
|------|-----|------|
| `ChatOpenAI` | 封装 LLM API 调用 | 引擎 |
| `ChatPromptTemplate` | 动态构造 prompt | 模具 |
| `StrOutputParser` | 提取纯文本结果 | 过滤器 |
| `chain = a \| b \| c` | 串联组件 | 流水线 |
| `chain.invoke()` | 执行链 | 开关 |
| `chain.stream()` | 流式执行 | 实时传输 |

---

## 小结

学完本模块，你已掌握：
- `Model` + `Prompt Template` + `Parser` 三件套
- LCEL 管道 `|` 串联组件
- `RunnableParallel` 并行执行
- 动态 prompt 构造

> **核心心智模型**：LangChain 应用 = 用 `|` 把组件串成流水线

👉 下一模块：[提示工程与输出解析](03-prompt-engineering.md)
