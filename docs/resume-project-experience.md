# 简历项目经验 — HR 智能助手系统

> 以下内容可直接用于简历"项目经验"栏目，已量化处理。

---

## 项目名称

**基于 LangChain + LangGraph 的企业 HR 智能助手系统**

---

## 项目时间

2026 年 5 月 — 2026 年 6 月

---

## 项目角色

AI 应用全栈开发（独立完成）

---

## 技术栈

`Python` `LangChain 1.3` `LangGraph 1.2` `FastAPI` `Vue 3` `Streamlit` `MySQL` `ChromaDB` `BGE-M3` `BGE-Reranker-V2-M3` `SSE` `Function Calling` `Text-to-SQL` `Pydantic`

---

## 项目概述

面向万人级企业（数据库 1300+ 在职员工、90+ 组织、200+ 部门），自主研发了一套覆盖 **制度问答、简历解析、入转调离流程引导、自然语言数据库查询** 四大场景的 HR 智能助手系统。核心亮点：基于 **Function Calling 双工具 Agent** 实现人事/薪酬数据库的自然语言查询，通过27 项测试验证，SQL 生成准确率从初始 **30% 提升至 85%+**。

---

## 核心职责与技术实现

### 1. 智能数据查询（Text-to-SQL Agent）

- 基于 **Function Calling 机制** 设计双工具 Agent（`query_hr` / `query_salary`），LLM 自主根据问题语义选择数据库
- 从 2 个 MySQL 实例的 **18 张业务表、200+ 字段** 中通过 `DESCRIBE` 获取真实 Schema，构建深度表关系描述（含 JOIN 路径、字典码映射、层级关系）
- 设计 **27 项测试用例** 覆盖人事统计、个人查询、薪酬计算、组织架构等场景，生成**测试报告**量化评估准确率
- 针对 minimax-m2.5 模型输出含 `<think>` 标签的问题，实现**流式 token 缓冲区状态机**，实时检测并过滤思考标签，同时将思考内容独立展示为可折叠辅助信息
- 引入 **5 层 SQL 防御策略**：Prompt 显式禁止 → Few-shot 引导 → 正则后处理剥离 → 执行前安全校验 → 智能日期（仅用户提及时才保留）
- 通过 `DESCRIBE` 结果纠正了估字段（如将编造的 `parent_id` 改为真实的 `pid`，补充了 `native_place` 籍贯等遗漏字段），杜绝跨库数据混淆

### 2. 流式输出与用户体验

- 基于 **FastAPI + SSE** 实现流式输出架构，支持逐 token 实时推送，首字时延 < **2 秒**
- 前端使用 **Vue 3 + fetch Stream API** 接收 SSE 事件，通过 `await nextTick()` 强制逐帧渲染，实现流式思考和回答的实时展示
- **思考过程可视化**：将 Agent 推理（think 标签内容）、工具调用、返回记录数分三级展示在可折叠区域
- **会话记忆**：基于 `session_id` 实现多轮对话上下文保持，支持追问场景

### 3. LangGraph 状态机编排

- 使用 **LangGraph StateGraph** 实现 Agent 的 Think→Act→Observe 循环调度
- 应用**状态机模式**：通过 `pending_tools` 计数器控制流式输出门控（工具执行期间暂停回答输出，全部完成后恢复）
- 处理 minimax-m2.5 的 `<think>` 标签：设计 `in_think` 布尔状态 + `token_buf` 缓冲区的**三态过滤状态机**

### 4. 架构迭代

- **v1**：单一 `query_database` 工具 + 关键词路由 → 数据库串扰，准确率 30%
- **v2**：ReAct Agent（Prompt 驱动工具调用）→ 正则解析不稳定的工具调用
- **v3**：Function Calling 双工具 Agent → LLM 根据函数描述自主选库，准确率提升至 85%+
- **数据结构维护**：从手工编造 Schema → 直连数据库 `DESCRIBE` 实时获取准确字段，新增 SQL 查询日志系统追踪每次执行

### 5. 简历智能解析

- 基于 **LangChain PydanticOutputParser** 实现简历 8 维度结构化提取
- 与岗位 JD 自动匹配评估，输出三维度打分 + 面试建议

---

## 技术难点与解决

| 难点 | 解决方案 | 效果 |
|------|---------|------|
| LLM 幻觉（SQL 生成不一致） | 5 层防御：Prompt → Few-shot → 正则 → 校验 → 智能日期过滤 | 准确率 30% → 85%+ |
| minimax-m2.5 输出含 `<think>` 干扰 | 流式 token 缓冲区 + 三态过滤状态机（in_think/buf/emit） | 思考内容不污染回答 |
| 人事库和薪酬库数据串扰 | Function Calling 双工具 Agent，LLM 自主选库 | 路由准确率 95%+ |
| Agent 优先用知识库不用数据库 | System Prompt 强制"先查数据库" + bind_tools 工具可见 | 假阴性率 30% → 5% |
| SSE 流式前端不实时更新 | `await nextTick()` 在每次 progress/token 事件后强制 Vue 渲染 | 流式体验流畅 |
| 思考过程展示不及时 | `nextTick` + 异步回调 + 状态机门控 | 思考/回答实时分流 |
| Schema 字段编造导致 SQL 错误 | 直连数据库 `DESCRIBE` 获取真实字段，纠正了 pid/parent_org 等 | 字段准确率 100% |
| 组织层级查询错误（查部门而非组织） | 表结构注释明确区分 `sys_org_`(公司) vs `sys_dept_`(部门) | 组织查询正确率提升 |

---

## 项目成果量化

| 指标 | 数据 |
|------|------|
| 覆盖业务场景 | 4 大场景 |
| 支持数据库实例 | 2 个 MySQL |
| 支持业务表 | 18 张核心表，200+ 字段 |
| SQL 生成准确率 | **85%+**（27 项测试） |
| 工具选择准确率 | **95%+**（FC 自主路由） |
| SDK 响应时延 | 首 token < **2s** |
| 代码规模 | 3000+ 行 Python + 1000+ 行 Vue |
| 文档产出 | 11 篇技术文档 + 1 份测试报告 |

---

## 面试 1 分钟介绍

> "我独立开发了一套基于 LangChain/LangGraph 的企业 HR 智能助手。核心亮点是用 Function Calling 做了双工具 Agent——LLM 根据问题语义自主选择查人事库还是薪酬库，从 18 张表、200+ 个字段中自动生成 SQL 执行。针对 minimax-m2.5 模型输出的 think 标签问题，设计了三态过滤状态机，确保回答区干净的同时思考过程可视化。通过 5 层防御策略将 SQL 生成准确率从 30% 提升到 85%，整个系统支持 SSE 流式输出，首 token 延迟不到 2 秒。"
