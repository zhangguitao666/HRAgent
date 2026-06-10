# 模块3：提示工程与输出解析

> **目标**：掌握 PromptTemplate 高级用法，Few-shot 提示，结构化输出解析（JSON、Pydantic）

---

## 3.1 为什么提示工程重要？

相同的 LLM，不同的 prompt，结果天差地别：

```python
# 烂 prompt
"帮我处理一下这份简历"  # → LLM 不知道你要做什么

# 好 prompt
"从以下简历中提取：姓名、工作年限、技能列表。以JSON格式返回。"  # → 明确、结构化
```

Prompt 工程就是**用自然语言写"程序"**，控制 LLM 的输出。

---

## 3.2 PromptTemplate 详解

### 3.2.1 from_template() - 简单模板

```python
from langchain_core.prompts import PromptTemplate

# 普通字符串模板
template = PromptTemplate.from_template(
    "为以下产品写一句广告语：{product}"
)
print(template.invoke({"product": "智能手表"}).text)
# → "为以下产品写一句广告语：智能手表"
```

### 3.2.2 ChatPromptTemplate - 消息模板（最常用）

```python
from langchain_core.prompts import ChatPromptTemplate

# 一次定义多个角色的消息
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}，名字叫{name}。回答风格：{style}。"),
    ("human", "{user_input}"),
    # ("ai", "好的我来回答"),    # 也可以预设AI的回应
])

# 所有的 {xxx} 变量都在 invoke 时传入
messages = prompt.invoke({
    "role": "HR专员",
    "name": "小助手",
    "style": "专业、友善",
    "user_input": "我想了解年假政策"
})

print(messages)
# [
#   SystemMessage(content="你是一个HR专员，名字叫小助手。回答风格：专业、友善。"),
#   HumanMessage(content="我想了解年假政策"),
# ]
```

### 3.2.3 MessagesPlaceholder - 动态消息列表

当你有**变长的对话历史**时，用 `MessagesPlaceholder`：

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个HR助手。"),
    MessagesPlaceholder(variable_name="chat_history"),  # 这里插入历史对话
    ("human", "{user_input}"),
])
```

---

## 3.3 Few-Shot 提示：给 LLM 看例子

Few-shot = 在 prompt 里放几个输入→输出的示例，让 LLM "学会"怎么做。

```python
from langchain_core.prompts import FewShotChatMessagePromptTemplate, ChatPromptTemplate

# 第一步：准备示例
examples = [
    {"input": "PTO", "output": "Paid Time Off（带薪休假）"},
    {"input": "JD", "output": "Job Description（岗位说明书）"},
    {"input": "OKR", "output": "Objectives and Key Results（目标与关键成果）"},
]

# 第二步：创建示例模板
example_prompt = ChatPromptTemplate.from_messages([
    ("human", "{input}"),
    ("ai", "{output}"),
])

# 第三步：创建 Few-Shot 模板
few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=examples,
    example_prompt=example_prompt,
)

# 第四步：组合到完整 prompt 中
final_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个HR术语解释器。参考以下例子回答问题："),
    few_shot_prompt,
    ("human", "请解释：{term}"),
])

chain = final_prompt | llm | StrOutputParser()
print(chain.invoke({"term": "KPI"}))
# → "Key Performance Indicator（关键绩效指标）"
```

---

## 3.4 输出解析器（Output Parser）

LLM 返回的是文本，但程序需要结构化数据。Parser 把文本变成 Python 对象。

### 3.4.1 StrOutputParser - 纯文本

```python
from langchain_core.output_parsers import StrOutputParser

parser = StrOutputParser()
# "你好！有什么可以帮助你的？\n"  →  "你好！有什么可以帮助你的？"
```

### 3.4.2 JsonOutputParser - JSON 解析

```python
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# 定义期望的数据结构
class PersonInfo(BaseModel):
    name: str = Field(description="姓名")
    age: int = Field(description="年龄")
    skills: list[str] = Field(description="技能列表")

# 创建解析器
parser = JsonOutputParser(pydantic_object=PersonInfo)

# 把格式说明注入 prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "从用户输入中提取个人信息。\n{format_instructions}"),
    ("human", "{input}"),
])

# 关键：用 parser.get_format_instructions() 告诉 LLM 怎么输出
prompt_with_format = prompt.partial(
    format_instructions=parser.get_format_instructions()
)

chain = prompt_with_format | llm | parser

result = chain.invoke({"input": "我叫张三，今年28岁，会Python和Java"})
print(result)
# {'name': '张三', 'age': 28, 'skills': ['Python', 'Java']}
print(type(result))  # <class 'dict'>
```

### 3.4.3 PydanticOutputParser - 直接出 Python 对象

```python
from langchain_core.output_parsers import PydanticOutputParser

parser = PydanticOutputParser(pydantic_object=PersonInfo)

chain = prompt_with_format | llm | parser

result = chain.invoke({"input": "我叫李四，35岁，会Go和Rust"})
print(result.name)    # 李四
print(result.age)     # 35
print(result.skills)  # ['Go', 'Rust']
print(type(result))   # <class '__main__.PersonInfo'>
```

---

## 3.5 进阶：with_structured_output（推荐）

LangChain 0.2+ 提供了更简洁的方式：

```python
# 不用 parser，直接让模型输出结构化数据
structured_llm = llm.with_structured_output(PersonInfo)

# 直接用，不需要 prompt 格式说明
prompt = ChatPromptTemplate.from_messages([
    ("system", "从用户输入中提取个人信息。"),
    ("human", "{input}"),
])

chain = prompt | structured_llm

result = chain.invoke({"input": "我叫王五，30岁，熟练掌握C++和Python"})
print(result)  # PersonInfo(name='王五', age=30, skills=['C++', 'Python'])
```

> `with_structured_output()` 是**首推方式**，它利用了 LLM 原生 Function Calling 能力，比 Parser 方式更可靠。

---

## 3.6 练习：HR 简历提取器

```python
"""
练习：用结构化输出从简历文本中提取关键信息
"""
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

class ResumeInfo(BaseModel):
    name: str = Field(description="姓名")
    years_of_experience: int = Field(description="工作年限")
    education: str = Field(description="最高学历")
    skills: list[str] = Field(description="技能列表，至少列出3个")
    current_position: str = Field(description="当前/最近职位")

llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
)

structured_llm = llm.with_structured_output(ResumeInfo)

prompt = ChatPromptTemplate.from_messages([
    ("system", "从以下简历文本中提取关键信息。如果信息缺失，填入合理的默认值。"),
    ("human", "{resume_text}"),
])

chain = prompt | structured_llm

# 测试
sample_resume = """
张伟，男，32岁。
2015年毕业于北京大学计算机科学专业，硕士学位。
2015-2018 在腾讯担任后端开发工程师。
2018-至今 在字节跳动担任高级后端工程师，主要负责推荐系统开发。
精通Python、Go，熟悉Kubernetes和Docker。
"""

result = chain.invoke({"resume_text": sample_resume})
print(result.model_dump())
# {
#   'name': '张伟',
#   'years_of_experience': 9,
#   'education': '硕士',
#   'skills': ['Python', 'Go', 'Kubernetes', 'Docker'],
#   'current_position': '高级后端工程师'
# }
```

---

## 3.7 提示工程最佳实践

| 技巧 | 说明 | 示例 |
|------|------|------|
| 角色设定 | 告诉LLM它是谁 | "你是一个资深的HR总监" |
| 明确输出格式 | 指定格式避免发散 | "以JSON格式返回" |
| 分步指令 | 复杂任务拆成步骤 | "第一步...第二步..." |
| Few-shot | 给2-3个示例 | "例如输入X输出Y" |
| 防幻觉 | 允许说不知道 | "如果信息不足，填入'未知'" |
| 长度控制 | 限制回答长度 | "50字以内回答" |

---

## 小结

- `ChatPromptTemplate` 是构造动态 prompt 的核心工具
- `FewShotChatMessagePromptTemplate` 通过示例引导 LLM 行为
- `with_structured_output()` 是最简洁可靠的结构化输出方式
- 好的 prompt = 具体角色 + 明确格式 + 示例引导

👉 下一模块：[记忆系统](04-memory.md)
