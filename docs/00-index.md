# LangChain 从零到实战：人力资源系统助手智能体

> **学习路径总纲** — 从零基础到完成一个可用的 HR 智能助手项目

---

## 课程概述

本课程面向 **完全零基础** 的 LangChain 学习者，通过 7 个模块逐步掌握 LangChain 核心概念，最终完成一个企业级的人力资源系统助手智能体项目。

- **学习周期**：建议 5-7 天（每天 2-3 小时）
- **前置要求**：Python 基础（会写函数、类、会用 pip）
- **最终产出**：一个基于 Streamlit 的 HR 智能助手 Web 应用

---

## 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| LLM 模型 | minimax-m2.5 (OpenAI 兼容接口) | 通过内部 API 网关调用 |
| 框架 | LangChain 0.3+ | AI 应用开发框架 |
| UI 界面 | Streamlit | Python Web 界面框架 |
| 向量数据库 | ChromaDB | 轻量级本地向量存储 |
| 嵌入模型 | text-embedding-3-small (或本地模型) | 文本转向量 |
| 结构化数据 | SQLite | 模拟 HR 数据库 |

---

## 学习路线图

```
模块1: 核心概念        模块2: 提示工程         模块3: 记忆系统
  Models           →    Prompt Templates    →    Memory
  Prompts               Output Parsers           Chat History
  Chains                结构化输出               对话上下文
     │                      │                       │
     └──────────────────────┼───────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        模块4: RAG      模块5: 智能体    模块6: 实战
        VectorStore     Agents           HR 助手
        Embeddings      Tools            完整项目
        Retrieval       Function Call    全部整合
```

---

## 模块清单

| 模块 | 文档 | 核心知识点 | 练习文件 |
|------|------|-----------|---------|
| 1 | [环境准备](01-environment.md) | Python 虚拟环境、依赖安装、API 配置 | `config.py` |
| 2 | [核心概念入门](02-core-concepts.md) | Model/Prompt/Chain 三件套 | `basics/01_hello_chain.py` |
| 3 | [提示工程与输出解析](03-prompt-engineering.md) | PromptTemplate、Few-shot、OutputParser | `basics/02_prompts.py` |
| 4 | [记忆系统](04-memory.md) | ConversationBufferMemory、ChatMessageHistory | `basics/03_memory.py` |
| 5 | [RAG 检索增强生成](05-rag.md) | Document、Embedding、VectorStore、Reranker | `basics/04_rag.py` |
| 6 | [智能体与工具](06-agents-tools.md) | Agent、Tool、Function Calling、ReAct | `basics/05_agents.py` |
| 6B | [LangGraph 编排框架](06b-langgraph.md) | State、Node、Edge、Graph 循环 | (概念篇) |
| 7 | [HR 助手实战项目](07-hr-assistant.md) | 完整项目：FAQ、简历解析、数据查询 | `hr_assistant/` |

---

## HR 助手项目功能清单

```
┌─────────────────────────────────────────────────────┐
│               HR 智能助手系统                        │
├───────────────┬──────────────┬──────────────────────┤
│  智能对话     │  文档处理     │  数据查询             │
├───────────────┼──────────────┼──────────────────────┤
│ 员工FAQ问答   │ 简历解析/筛选 │ 人事信息查询(DB)      │
│ 入职引导      │              │ 薪酬数据查询(DB)      │
│ 转正引导      │              │ 考勤数据查询(DB)      │
│ 离职引导      │              │                      │
│ 退休引导      │              │                      │
└───────────────┴──────────────┴──────────────────────┘
```

---

## 项目架构

```
LangChain/
├── docs/                          # 学习文档
│   ├── 00-index.md                # 总纲（当前文件）
│   ├── 01-environment.md          # 环境准备
│   ├── 02-core-concepts.md        # 核心概念
│   ├── 03-prompt-engineering.md   # 提示工程
│   ├── 04-memory.md               # 记忆系统
│   ├── 05-rag.md                  # RAG检索增强
│   ├── 06-agents-tools.md         # 智能体与工具
│   └── 07-hr-assistant.md         # HR助手实战
│
├── src/
│   ├── basics/                    # 学习练习代码
│   │   ├── 01_hello_chain.py
│   │   ├── 02_prompts.py
│   │   ├── 03_memory.py
│   │   ├── 04_rag.py
│   │   └── 05_agents.py
│   │
│   └── hr_assistant/              # HR助手项目
│       ├── app.py                 # 主入口（Streamlit）
│       ├── config.py              # 配置管理
│       ├── utils/
│       │   └── data_loader.py     # 数据加载工具
│       ├── tools/
│       │   ├── hr_query_tools.py  # 数据库查询工具
│       │   └── resume_tool.py     # 简历处理工具
│       ├── pages/
│       │   ├── faq_chat.py        # FAQ聊天页面
│       │   ├── resume_parser.py   # 简历解析页面
│       │   ├── onboarding.py      # 入职引导页面
│       │   ├── regularization.py  # 转正引导页面
│       │   ├── resignation.py     # 离职引导页面
│       │   ├── retirement.py      # 退休引导页面
│       │   ├── hr_info.py         # 人事信息查询
│       │   ├── salary.py          # 薪酬查询
│       │   └── attendance.py      # 考勤查询
│       └── data/
│           ├── employees.json      # 员工数据（模拟DB）
│           ├── salary.json         # 薪酬数据（模拟DB）
│           ├── attendance.json     # 考勤数据（模拟DB）
│           └── faq_knowledge/      # FAQ知识库文档
│
├── requirements.txt               # Python依赖
└── .env.example                   # 环境变量模板
```

---

## 学习建议

1. **按顺序学习**：每个模块依赖前一个模块的知识
2. **动手实践**：每学完一个模块，运行对应的练习代码
3. **理解而非记忆**：重点理解 LangChain 的"链"式设计思想
4. **遇到问题看文档**：每个文档末尾都有常见问题解答

---

## 开始学习

👉 从 [01-环境准备](01-environment.md) 开始
