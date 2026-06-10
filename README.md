# HR 智能助手 (HR Intelligent Assistant)

基于 **LangChain + LangGraph + Function Calling** 的企业人力资源 AI 助手。单一对话入口，AI 自动识别意图并调用对应工具（数据查询 / 制度问答 / 简历解析 / 流程引导）。

## Features

- **🧠 统一对话入口** — 一个输入框搞定所有场景，AI 自动判断查制度还是查数据
- **📊 Text-to-SQL 数据查询** — Function Calling 双工具 Agent（人事库/薪酬库），自然语言 → SQL → 实时结果
- **💬 HR 制度问答** — 基于公司制度文档智能问答
- **📄 简历智能解析** — 结构化提取候选人信息
- **🚪 入转调离引导** — 入职/转正/离职/退休流程 AI 引导
- **⚡ 流式输出** — SSE 实时推送，思考过程可视化
- **🧠 会话记忆** — 多轮对话上下文保持，左侧栏会话管理
- **💾 会话持久化** — localStorage 自动保存，刷新不丢失

## Tech Stack

`Python` `LangChain` `LangGraph` `FastAPI` `Vue 3` `MySQL` `SSE` `Function Calling`

## Architecture

```
┌──────────┬──────────────────────────────────────────┐
│  会话管理   │            统一对话界面                    │
│ (侧边栏)   │  ┌──────────────────────────────────┐   │
│          │  │     AI 自动意图识别                 │   │
│ + 新会话  │  ├────┬────┬────┬────┬───────────────┤   │
│          │  │ 查人 │ 查薪 │ FAQ │ 简历 │ 入转调离     │   │
│ 会话 1   │  │ 事库 │ 酬库 │     │ 解析 │ 流程引导     │   │
│ 会话 2   │  └────┴────┴────┴────┴───────────────┘   │
│          │              LangGraph Agent              │
│ 会话 3   │          LLM (minimax-m2.5)              │
└──────────┴──────────────────────────────────────────┘
                             │
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
          人事库 MySQL   薪酬库 MySQL   制度文档
         (cyj_ehr_pro)  (cyj_ehr_wa)   (txt)
```

## Quick Start

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置凭证（复制模板填入真实值）
cp src/hr_assistant/config.example.py src/hr_assistant/config.py

# 3. 启动后端
.\venv\Scripts\python.exe -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 启动前端
cd web && npm install && npm run dev

# 5. 打开浏览器 http://localhost:5173
```

## Project Structure

```
LangChain/
├── server/                       # FastAPI 后端
│   ├── main.py                   # 应用入口 + CORS
│   └── api/
│       ├── chat.py               # ★ 统一对话 API（FC 5 工具 Agent + SSE 流式）
│       ├── query.py              # 数据查询 API（双工具 Agent）
│       ├── faq.py                # FAQ 问答 API
│       ├── resume.py             # 简历解析 API
│       └── lifecycle.py          # 入转调离 API
├── src/hr_assistant/
│   ├── config.py                 # 数据库/LLM 配置 + Schema（需自行创建）
│   ├── config.example.py         # 配置模板
│   ├── tools/
│   │   ├── hr_query_tools.py     # Text-to-SQL 工具（query_hr/query_salary）
│   │   └── resume_tool.py        # 简历解析工具
│   └── utils/
│       ├── db_utils.py           # MySQL 连接池
│       └── sql_logger.py         # SQL 查询日志
├── web/                          # Vue 3 前端
│   └── src/
│       ├── App.vue               # 布局：左侧会话栏 + 右侧聊天
│       ├── views/ChatView.vue    # 统一对话界面（SSE 流式）
│       └── api/client.js         # SSE 客户端
├── docs/                         # 技术文档 + 测试报告
└── logs/                         # SQL 查询日志（gitignored）
```

## Key Design Decisions

| 决策 | 方案 | 原因 |
|------|------|------|
| 统一对话 | 单一入口 + FC 5 工具 Agent | 用户无需手动切换功能，AI 自动路由 |
| 会话管理 | 左侧栏 + localStorage | 多会话并行，刷新不丢消息 |
| Agent 模式 | Function Calling | 工具选择准确率 95%+，无需关键词路由 |
| 数据库隔离 | 双工具（hr/salary） | 人事问题只查人事库，避免数据串扰 |
| Schema 维护 | DESCRIBE 直连获取 | 消除字段编造，保证字段名准确 |
| 流式架构 | FastAPI + SSE | 首 token < 2s，思考过程实时可见 |
| think 标签处理 | 三态过滤状态机 | 回答干净 + 思考可查看 |

## License

MIT
