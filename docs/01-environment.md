# 模块1：环境准备

> **目标**：完成 Python 虚拟环境配置，安装 LangChain 全家桶，验证 API 连通性

---

## 1.1 什么是 LangChain？

LangChain 是一个用于构建 **LLM（大语言模型）驱动应用** 的 Python 框架。它的核心思想是：

```
你 → 写 Prompt → 调 LLM → 拿到结果
```
升级为：
```
你 → 组合多个组件（链） → 自动推理 → 调用工具 → 返回结构化结果
```

**打个比方**：如果没有 LangChain，你就像徒手搭积木；有了 LangChain，你就像有了乐高套件，有标准化的组件和连接方式。

---

## 1.2 创建虚拟环境

```powershell
# 1. 进入项目目录
cd D:\DevHub\LangChain

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境（Windows PowerShell）
.\venv\Scripts\Activate.ps1

# 如果报错"无法加载文件"，先执行：
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 4. 确认激活成功（命令行前出现 (venv)）
# (venv) D:\DevHub\LangChain>
```

> **为什么用虚拟环境？** 避免不同项目的依赖版本冲突。就像给每个项目一个独立的工具箱。

---

## 1.3 安装依赖

```powershell
# 安装所有依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 验证安装
pip list | findstr langchain
# 应该看到：
# langchain             0.3.x
# langchain-community   0.3.x
# langchain-openai      0.2.x
```

**各包的作用说明**：

| 包名 | 作用 | 类比 |
|------|-----|------|
| `langchain` | 核心框架，定义 Chain、Agent、Tool 等抽象 | 乐高的基础积木 |
| `langchain-community` | 社区贡献的集成（向量库、文档加载器等） | 乐高的特殊零件 |
| `langchain-openai` | OpenAI 模型的统一接口封装 | 电动马达配件 |
| `streamlit` | 快速构建 Web UI 界面 | 展示台 |
| `chromadb` | 轻量级向量数据库（存储知识库） | 资料库 |
| `tiktoken` | OpenAI 的 token 计数器 | 尺子 |

---

## 1.4 配置 API 连接

LangChain 的模型调用架构：

```
你的代码 → LangChain 抽象层 → langchain-openai 适配器 → HTTP请求 → 模型服务
```

创建 `src/hr_assistant/config.py`：

```python
"""
HR 助手项目 - 全局配置
"""

import os

# ========== LLM 配置 ==========
LLM_CONFIG = {
    "model": "minimax-m2.5",                    # 模型名称
    "api_key": "<your-llm-api-key>",
    "base_url": "http://your-llm-host:3000/v1", # API 地址
    "temperature": 0.7,                           # 创造性参数 (0=严谨, 1=创意)
    "max_tokens": 2048,                           # 单次回复最大长度
}

# ========== 核心概念解释 ==========
# temperature: 控制回答的随机性
#   0.1 → 非常确定，答案几乎固定（适合数学/事实查询）
#   0.7 → 中等创造性（适合对话/写作）
#   1.0 → 很有创意但可能胡说八道

# base_url: 你的 API 服务地址
# OpenAI 官方是 https://api.openai.com/v1
# 你用的是内部代理 http://your-llm-host:3000/v1

# model: LLM 模型标识
# 由你的 API 服务提供方决定
# 常见的有 gpt-4o, gpt-3.5-turbo, minimax-m2.5 等
```

---

## 1.5 验证 API 连通性

创建测试文件 `src/basics/01_test_api.py`：

```python
"""
API 连通性测试
验证你的 LLM 服务是否可用
"""

from langchain_openai import ChatOpenAI

# 1. 创建模型实例
llm = ChatOpenAI(
    model="minimax-m2.5",
    api_key="<your-llm-api-key>",
    base_url="http://your-llm-host:3000/v1",
    temperature=0.7,
)

# 2. 发送一条消息
response = llm.invoke("用一句话介绍你自己")

# 3. 查看结果
print("=" * 50)
print("API 连通性测试")
print("=" * 50)
print(f"问题: 用一句话介绍你自己")
print(f"回答: {response.content}")
print(f"Token 消耗: {response.response_metadata}")
print("=" * 50)
print("测试通过!")
```

运行：
```powershell
python src\basics\01_test_api.py
```

**预期输出**：
```
==================================================
API 连通性测试
==================================================
问题: 用一句话介绍你自己
回答: 我是 MiniMax-M2.5，一个由 MiniMax 开发的大语言模型...
Token 消耗: {...}
==================================================
测试通过!
```

---

## 1.6 理解关键概念

### ChatOpenAI 是什么？

```python
llm = ChatOpenAI(model="minimax-m2.5", ...)
```

`ChatOpenAI` 是 LangChain 中的一个**模型包装器**。它把不同 LLM 服务商的 API 统一成相同的调用方式：

```python
# 不管底层是 OpenAI、DeepSeek 还是 MiniMax
# 调用方式都一样
response = llm.invoke("你好")
```

### invoke() 方法

`invoke()` 是 LangChain 最核心的方法。**所有** LangChain 组件（Model、Chain、Agent...）都用它来执行：

```python
model.invoke("问题")       # 调用模型
chain.invoke({"key": "val"})  # 执行链
agent.invoke({"input": "..."})  # 执行智能体
```

> 记住 `invoke()` = 执行/调用，这个概念贯穿 LangChain 始终。

### 流式输出 vs 非流式输出

```python
# 非流式：等全部生成完再返回
response = llm.invoke("你好")
# → 等待 3 秒 → "你好！有什么可以帮助你的？"

# 流式：一个字一个字地返回（像 ChatGPT 打字效果）
for chunk in llm.stream("你好"):
    print(chunk.content, end="", flush=True)
# → 你→好→！→有→什→么→可→以...
```

---

## 1.7 常见问题

### Q: 报错 `ConnectionError`？
**A**: 检查 `base_url` 是否正确，确保 `http://10.225.252.109:3000` 可以访问。

### Q: 报错 `AuthenticationError`？
**A**: 检查 `api_key` 是否正确。

### Q: 报错 `Model not found`？
**A**: 检查 `model` 参数名称是否正确（`minimax-m2.5`）。

### Q: 为什么用 `langchain-openai` 而不是原生 requests？
**A**: LangChain 的 `ChatOpenAI` 封装了重试、token计数、流式输出、结构化输出等功能，比自己写 HTTP 请求强大得多。

---

## 小结

完成本模块后，你已具备：
- Python 虚拟环境
- LangChain 全家桶
- 与 LLM API 联通的能力
- 理解了 `ChatOpenAI`、`invoke()`、`temperature` 等核心概念

👉 下一模块：[核心概念入门](02-core-concepts.md)
