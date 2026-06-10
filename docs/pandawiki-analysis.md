# PandaWiki 知识库技术分析报告

> 项目地址: https://github.com/chaitin/PandaWiki  
> Stars: 9.7k | 语言: TypeScript 66.7% / Go 29.6% | 许可证: AGPL-3.0

---

## 一、项目概述

PandaWiki 是长亭科技（Chaitin）开源的 **AI 大模型驱动的知识库系统**，定位为"可私有化部署的 Wiki + RAG"。提供 AI 创作、AI 问答、AI 搜索三大能力，支持搭建产品文档、FAQ、博客等场景。

---

## 二、核心技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React 19 + TypeScript 5.9 + MUI v7 + Tiptap + Vite | Monorepo（admin 控制台 + app 前台） |
| 后端 | Go + Echo Framework + GORM | REST API + NATS 消息队列 |
| 数据库 | PostgreSQL + Redis + MinIO/S3 | 元数据 + 缓存 + 文件存储 |
| LLM 框架 | **ModelKit** + **CloudWeGo eino** | LLM 抽象层 + AI 编排引擎 |
| 向量引擎 | **RagLite**（自研/闭源） | 向量存储 + 检索 + 分块 + Rerank |
| 嵌入模型 | 多供应商（OpenAI/Ollama/Ark） | 动态配置，不硬编码 |

---

## 三、知识库架构（五层模型）

```
┌────────────────────────────────────────────┐
│  1. 文档接入层                              │
│  URL / RSS / Sitemap / 文件上传 / EPUB      │
│  Notion / 飞书 / 钉钉 / 语雀 / Confluence    │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  2. 解析与预处理层  (RagLite)               │
│  PDF/DOCX/MD/HTML/Excel → Markdown 转换     │
│  DeepDoc 版面识别 / HTML4Excel              │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  3. 分块与索引层  (RagLite)                 │
│  • 可配置 chunk_token_num / delimiter        │
│  • RAPTOR 层次化摘要（树状索引）             │
│  • GraphRAG 实体抽取 + 社区检测              │
│  • 自动关键词/问题生成                       │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  4. 检索层  (混合搜索)                      │
│  • 向量搜索 (语义)                          │
│  • BM25 关键词搜索                          │
│  • VectorSimilarityWeight 加权融合           │
│  • Reranker 重排序                          │
│  • Query Rewriting（多轮对话改写）            │
│  • 权限/相似度阈值过滤                        │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  5. 生成层  (模型无关)                      │
│  • 结构化 Prompt（<document> XML 标签）      │
│  • 流式输出 + DFA 敏感词实时过滤             │
│  • 多模型支持（OpenAI/DeepSeek/Gemini/Ollama）│
└────────────────────────────────────────────┘
```

---

## 四、与我们项目的对比

| 维度 | PandaWiki | 我们的 HR Agent |
|------|-----------|----------------|
| **定位** | 通用知识库 + Wiki 建站 | 企业 HR 专用助手 |
| **向量引擎** | RagLite（自研闭源） | ChromaDB（开源） |
| **嵌入模型** | 多供应商可配 | BGE-M3（单一、质量待验证） |
| **分块策略** | RAPTOR + GraphRAG + 可配参 | RecursiveCharacterTextSplitter |
| **检索方式** | 向量 + BM25 混合 + Rerank | 关键词路由 + Rerank |
| **Query 改写** | ✅ 多轮对话自动改写 | ❌ 无 |
| **文档接入** | 13+ 种来源/格式 | 3 种（txt/md/pdf/docx） |
| **文档预处理** | HTML→MD、版面识别 | 无预处理 |
| **敏感词过滤** | ✅ DFA 实时过滤 | ❌ 无 |
| **多租户** | ✅ KB 级权限隔离 | ❌ 无 |
| **前端** | React 19 + MUI + 富文本编辑器 | Vue 3 + 手写 CSS |
| **部署** | Docker 一键安装 | 手动 venv + npm |

---

## 五、值得借鉴的技术点

### 1. Prompt 结构化（P0 - 可直接采用）
PandaWiki 用 XML 标签包裹检索结果，明确区分 `id`/`title`/`url`/`content`，减少 LLM 混淆：
```xml
<documents>
  <document>
    <ID>doc_001</ID>
    <Title>出差休假管理办法</Title>
    <Content>...</Content>
  </document>
</documents>
```
我们可以将 FAQ 检索结果改为类似格式，提升 LLM 对多块内容的理解。

### 2. 混合检索权重（P1）
`VectorSimilarityWeight` 参数让向量和关键词结果可调权融合，避免单一策略的盲区。当前我们只有关键词路由。

### 3. Query Rewriting（P1）
多轮对话时，将"那公积金呢"改写为"公积金缴存比例"，提升检索精度。当前我们没有这个能力。

### 4. DFA 敏感词过滤（P2）
流式输出时实时替换敏感词。适合企业内网场景。

### 5. 文档预处理（P2）
HTML→Markdown 转换、版面识别（DeepDoc）提升 PDF 表格/扫描件解析质量。

---

## 六、结论

PandaWiki 的 RAG 管道是**生产级**的：分块有 RAPTOR 层次索引、检索有混合搜索+Rerank、生成有结构化 Prompt+流式过滤。但其核心向量引擎 RagLite 是闭源的，无法直接复用。

对我们项目最具落地价值的借鉴：
1. **结构化 Prompt** — 改进 FAQ 回答质量（< 2h）
2. **Query Rewriting** — 提升多轮对话检索（< 4h）
3. **混合检索权重** — BM25+向量融合（< 4h）
