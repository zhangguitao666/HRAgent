# 模块5：RAG 检索增强生成

> **目标**：理解 RAG 原理，掌握文档加载、文本分割、向量化、检索、生成的完整流水线

---

## 5.1 什么是 RAG？

**RAG = Retrieval-Augmented Generation（检索增强生成）**

问题是：LLM 的知识截止训练日期，不知道你公司的内部制度。
方案是：把公司文档"喂"给 LLM，让它基于文档回答。

```
        ┌──────────────┐
        │  用户提问     │
        └──────┬───────┘
               │
               ▼
┌──────────────────────────────┐
│ 1. 检索 (Retrieval)          │
│    从知识库找相关文档片段      │
└──────────────┬───────────────┘
               │ 相关片段
               ▼
┌──────────────────────────────┐
│ 2. 增强 (Augmented)          │
│    把片段 + 问题拼成 prompt   │
└──────────────┬───────────────┘
               │ 完整 prompt
               ▼
┌──────────────────────────────┐
│ 3. 生成 (Generation)          │
│    LLM 基于材料生成回答        │
└──────────────────────────────┘
```

**RAG vs 传统搜索的区别**：
- 传统搜索：给你一堆链接，自己看
- RAG：帮你读懂了，直接回答你

---

## 5.2 RAG 的完整流水线（深度拆解）

RAG 不是一步完成的，它分为**离线阶段**（建库）和**在线阶段**（查询）两个独立的过程。

### 离线阶段：构建知识库

```
┌─────────────────────────────────────────────────────────────┐
│                    离线阶段（建库，一次性）                      │
│                                                             │
│  原始文档──→加载──→分割成块──→向量嵌入──→存入向量库               │
│  (PDF/DOCX)  (Document)  (Chunks)    ([0.1,0.3,...])         │
│                                    每个块 → 一个向量            │
└─────────────────────────────────────────────────────────────┘
```

### 在线阶段：查询回答

```
┌─────────────────────────────────────────────────────────────┐
│                    在线阶段（每次查询执行）                      │
│                                                             │
│  用户提问──→提问向量化──→相似度搜索──→检索Top-K──→拼入Prompt──→LLM生成  │
│  "年假？"   [0.2,0.5..]  余弦相似度    相关片段    {context}   最终回答  │
└─────────────────────────────────────────────────────────────┘
```

**关键理解**：向量嵌入是同一个人用同一个模型做两次——离线时把文档嵌了存起来，在线时把问题嵌了去搜，因为用的是**同一个嵌入模型**，所以语义相近的文本向量在空间中距离近。

---

### 5.2.1 第一步：加载文档

```python
from langchain_community.document_loaders import TextLoader

loader = TextLoader("data/faq_knowledge/company_policy.txt")
documents = loader.load()  # 返回 Document 对象列表
# Document(page_content="文本内容", metadata={"source": "文件路径"})
```

支持的文档类型：
| Loader | 支持格式 |
|--------|---------|
| `TextLoader` | .txt |
| `CSVLoader` | .csv |
| `JSONLoader` | .json |
| `PyPDFLoader` | .pdf |
| `Docx2txtLoader` | .docx |

### 5.2.2 第二步：文本分割

LLM 每次能处理的文本有限（上下文窗口），而且向量检索精度会随文本变长而下降。所以要把文档切成小块。

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,       # 每块最多 500 字符
    chunk_overlap=50,     # 块之间重叠 50 字符（避免截断语义）
    separators=["\n\n", "\n", "。", "，", " ", ""],  # 优先级分隔符
)

chunks = splitter.split_documents(documents)
# chunks = [Document(page_content="片段1..."), Document(...), ...]
```

**关键参数解释**：
- `chunk_size`：太大检索不准，太小语义不完整。中文建议 300-800。
- `chunk_overlap`：重叠让相邻块共享部分内容，避免关键信息被切在边界上。

### 5.2.3 第三步：向量嵌入（Embedding）——BGE-M3 详解

计算机不懂文字，只懂数字。Embedding 把文字变成向量（一组数字），意思相近的文字向量在空间中距离也近。

```python
from langchain_openai import OpenAIEmbeddings

# 本项目使用的 BGE-M3 嵌入服务（OpenAI 兼容接口）
embeddings = OpenAIEmbeddings(
    model="bge-m3",
    api_key="<your-embedding-api-key>",
    base_url="https://your-embedding-host/v1",
)

# 一句话变成一个向量（1024维浮点数组）
vector = embeddings.embed_query("年假怎么算？")
# vector = [0.023, -0.154, 0.891, ...]  ← 1024个数字

# 多句话变成多个向量
vectors = embeddings.embed_documents(["文档1", "文档2", "文档3"])
```

**BGE-M3 是什么？**

BGE-M3 是 BAAI（北京智源人工智能研究院）开源的**多语言嵌入模型**。M3 代表三个特性：

| 特性 | 说明 | 实际意义 |
|------|------|---------|
| **Multi-Lingual**（多语言） | 支持 100+ 种语言 | 中英文混合文档也能准确嵌入 |
| **Multi-Functionality**（多功能） | 同时支持 Dense 和 Sparse 检索 | 既能语义匹配也能关键词匹配 |
| **Multi-Granularity**（多粒度） | 支持短句到长文（8192 tokens） | 一条制度文本不需要切太碎 |

**向量空间直观理解**：

```
         "年假有几天"  ←→  "带薪年假政策"
              ↑                    ↑
          [0.12, -0.34, ...]  [0.14, -0.31, ...]   余弦相似度 ≈ 0.95（很近！）
              
              
         "年假有几天"  ←→  "加班费怎么算"
              ↑                    ↑
          [0.12, -0.34, ...]  [-0.67, 0.41, ...]   余弦相似度 ≈ 0.12（很远！）
```

**为什么选 BGE-M3？**

| 对比项 | BGE-M3 | OpenAI text-embedding-3 | 本地 HuggingFace |
|--------|--------|------------------------|-------------------|
| 向量维度 | 1024 | 1536 / 256 | 768 (text2vec) |
| 中文效果 | 优秀（专为中文优化） | 良好 | 良好 |
| 多语言 | 100+ | 支持 | 仅中英文 |
| Max Tokens | 8192 | 8191 | 512 |
| 部署方式 | API 服务 | API 服务 | 本地 GPU/CPU |
| 免费 | 是（开源） | 付费 | 是 |

---

### 5.2.4 第四步：向量存储与检索

```python
from langchain_chroma import Chroma

# 存储：把分块后的文档存入 ChromaDB
vector_store = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db",
)

# 检索：根据问题找最相关的文档
retriever = vector_store.as_retriever(
    search_kwargs={"k": 10}  # 召回更多候选，后面可以重排序
)

results = retriever.invoke("年假有多少天？")
```

**向量搜索的本质**：计算"问题向量"和"所有文档块向量"之间的**余弦相似度**，按相似度从高到低排序，返回 Top-K。

**召回数量 `k` 怎么选？**

```
k=3  → 只给LLM看3条，信息可能不够，但token消耗少
k=10 → 给LLM看10条，覆盖更全，但可能混入噪音
k=10 + Reranker → 最优方案：先召回10条，再用Reranker精选3条
                    ↑ 这就是下节要讲的"重排序"
```

### 5.2.5 第五步：重排序（Reranker）——BGE-Reranker-V2-M3 详解

这一步是**可选但强烈推荐**的。粗检索（向量相似度）召回了 10 条候选，但相似度 ≠ 相关性。Reranker 对这 10 条进行**精细评分**，挑出真正最相关的 3 条。

```
粗检索（BGE-M3 Embedding）           精排（BGE-Reranker-V2-M3）
┌──────────────────────┐          ┌──────────────────────┐
│ 10条候选（相似度排序）  │  ────→  │ 逐条与问题一起打分      │
│ 1. 年假申请流程  0.89  │          │   → 年假政策说明 0.95  │
│ 2. 年假天数限制  0.87  │          │   → 年假天数限制 0.88  │
│ 3. 加班调休制度  0.81  │          │   → 年假申请流程 0.72  │
│ 4. 年假政策说明  0.80  │          │                       │
│ ...                    │          │  输出：精选 Top-3      │
└──────────────────────┘          └──────────────────────┘
   速度快，但语义理解粗                   速度慢，但理解精确
```

**BGE-Reranker-V2-M3 是什么？**

同样是 BAAI 开源的**跨编码器（Cross-Encoder）重排序模型**。

```
                      BGE-M3（Embedding）                    BGE-Reranker-V2-M3（Reranker）
                      ─────────────────                      ──────────────────────────
架构类型              Bi-Encoder（双塔模型）                    Cross-Encoder（交叉编码器）
                     
                      doc → [Encoder] → vec1                  [Question + Doc] → [Encoder] → score
                      q   → [Encoder] → vec2                  把问题和文档拼接在一起过模型
                      然后计算 vec1·vec2 的余弦
                      
                      问题编码一次，文档编码一次                   每次都要把问题+文档一起编码
                      然后点积                                     所以更慢但更准
                      
类比                  先各自拍张照片，再比对照片                     把人脸和身份证并排仔细比对

速度                  极快（向量点积 O(n)）                        较慢（每次都要推理）
准确度                粗粒度语义匹配                              细粒度相关性判断
输入                  单独处理文本                                 文本对 (query, doc) 同时输入
输出                  向量 [0.1, 0.3, ...]                       相关性分数 0~1
典型用法              召回阶段（从海量文档中初筛）                      精排阶段（对少量候选精准打分）
适合数据量             百万级                                      几十到几百条

本质区别              "各自编码，然后比距离"                         "放一起编码，直接给分数"
```

**为什么需要 Reranker？用 Embedding 直接检索不行吗？**

```
场景：用户问 "公司年假天数政策"
知识库中有：
  A. "员工入职满1年享有5天带薪年假"       ← 正确答案
  B. "年假需提前5个工作日提交申请"         ← 相关但不是答案
  C. "每年组织全体员工年度旅游活动"        ← 不相关

Embedding 相似度排序：A(0.91) > B(0.89) > C(0.25)    ← B 得分虚高
Reranker 精排后：     A(0.97) > B(0.42) > C(0.02)    ← 差距拉开，B 被压下去
```

Reranker 把问答对放在一起做交叉注意力计算，能更准确判断"这条文档到底能不能回答这个问题"。

**LangChain 中使用 Reranker**：

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain_community.document_compressors import OpenAIRerankCompressor

# 1. 先粗检索
base_retriever = vector_store.as_retriever(search_kwargs={"k": 10})

# 2. 用 Reranker 做精排（OpenAI 兼容接口）
compressor = OpenAIRerankCompressor(
    model="bge-reranker-v2-m3",
    api_key="<your-embedding-api-key>",
    base_url="https://your-reranker-host/v1",
    top_n=3,  # 最终保留3条
)

# 3. 组合：粗检索 → 精排
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever,
)

# 使用时自动先粗检后精排
docs = compression_retriever.invoke("年假有多少天？")
# 返回经过重排序的 Top-3 最相关文档
```

### 5.2.6 第六步：组合成 RAG 链（两阶段完整版）

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 完整的两阶段 RAG 链（粗检索 + 精排）
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是HR知识助手。严格根据以下【参考材料】回答问题。
如果材料中没有相关信息，明确说"根据现有资料无法回答"。

【参考材料】：
{context}"""),
    ("human", "{question}"),
])

# compression_retriever = 粗检索(k=10) → Reranker精排(k=3)
rag_chain = (
    {"context": compression_retriever, "question": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("年假政策是什么？")
```

**完整数据流跟踪**：

```
用户输入: "年假政策是什么？"
    │
    ├─→ compression_retriever.invoke("年假政策是什么？")
    │       ├─ BGE-M3 向量检索 (粗排, k=10)
    │       │     问题向量化 → 余弦相似度 → 10条候选
    │       │
    │       └─ BGE-Reranker-V2-M3 精排 (top_n=3)
    │             每条候选与问题拼接 → 交叉编码 → 打分 → 取Top-3
    │             返回: [Document("员工入职满1年..."), Document("年假需提前..."), ...]
    │
    ├─→ RunnablePassthrough → "年假政策是什么？"（原样传递）
    │
    └─→ {"context": [3条精选文档], "question": "年假政策是什么？"}
            │
            ▼
         rag_prompt → 填入模板 → 完整消息
            │
            ▼
         llm → 生成回答
            │
            ▼
         StrOutputParser → 纯文本 → "根据公司制度，年假政策如下..."
```

---

### 5.2.7 检索参数调优速查

| 参数 | 位置 | 建议值 | 说明 |
|------|------|--------|------|
| `chunk_size` | TextSplitter | 300-500（中文） | 太大检索不准，太小语义不完整 |
| `chunk_overlap` | TextSplitter | 50-100 | 防止关键信息切在边界上 |
| `k`（粗检索） | as_retriever | 10-20 | 多一些候选给 Reranker 筛选 |
| `top_n`（精排） | Compressor | 3-5 | 最终给 LLM 看的文档数 |
| `temperature` | LLM | 0.1-0.3 | RAG 场景应偏低，减少幻觉 |

---

## 5.3 理解 RunnablePassthrough

```python
{"context": compression_retriever, "question": RunnablePassthrough()}
```

这是 LCEL 并行处理的关键模式：
- `compression_retriever` 根据用户输入 → 粗检索(k=10) → Reranker精排(top_n=3) → 精选文档列表
- `RunnablePassthrough()` 把用户输入原样传给 `question`
- 两者合并：`{"context": [精选文档], "question": "用户原问题"}`

---

## 5.4 完整 RAG 示例代码

参见 `src/basics/04_rag.py`（已使用 BGE-M3 + BGE-Reranker 两阶段检索）。

---

## 5.5 嵌入模型选型指南

### 方案对比

| 方案 | 模型 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| API 服务 | BGE-M3（本项目） | 中文效果最好，8192 tokens | 依赖网络 | 生产环境 |
| OpenAI API | text-embedding-3 | 质量高，生态完善 | 付费，网络限制 | 海外部署 |
| 本地模型 | HuggingFaceEmbeddings | 离线可用，免费 | 需 GPU，效果略差 | 内网/开发测试 |
| Ollama | nomic-embed-text | 一行命令启动 | 英文为主 | 本地实验 |

### 本项目选型理由

```
选择 BGE-M3 的原因：
1. 中文效果最优（BAAI 专门为中文优化）
2. 8192 tokens 长文本支持（制度文档不需要切太碎）
3. 支持 Dense + Sparse 双路检索（语义 + 关键词）
4. 你已有现成的 API 服务可用
5. 搭配 BGE-Reranker-V2-M3 形成完整召回+精排流水线
```

---

## 5.6 BGE-M3 vs BGE-Reranker 本质区别

```
                            BGE-M3                          BGE-Reranker-V2-M3
                            ────────                        ───────────────────
在 RAG 中的角色             召回阶段（粗排）                   精排阶段（重排序）

任务                       "从海量文档中快速找出                  "对少量候选逐条精细判断
                            可能相关的几十条"                     哪条真正能回答问题"

模型架构                    Bi-Encoder（双塔）                   Cross-Encoder（交叉编码器）
                            doc → [Enc] → vec_a                  [Q + Doc] → [Enc] → score
                            Q   → [Enc] → vec_b                  拼接后一起过模型
                            然后点积/余弦

速度                       极快（向量一次算完，                 较慢（每对Q+Doc都要推理一次）
                            检索时只做点积 O(1)）

精度                       粗粒度语义相似                       细粒度相关性判断
                            "这两段文字话题接近吗？"               "这段文字能回答这个问题吗？"

为什么需要两者配合？         只用 Embedding → Top-10 里可能        只用 Reranker → 从百万文档里逐条打分
                            混入"看起来像但不是答案"的噪音        太慢了，不可行

最佳实践                    先 Embedding 召回 10-20 条            再 Reranker 精选 3-5 条
                            保证不遗漏可能的答案                   保证给 LLM 的都是精华
```

**一句话总结**：Embedding 负责"快找"，Reranker 负责"找准"。前者是粗筛，后者是精筛。两者配合才能既快又准。

---

## 5.7 什么时候不需要 Reranker？

| 场景 | 建议 |
|------|------|
| 知识库 < 100 条文档 | 不需要，直接 k=5 给 LLM 即可 |
| 对延迟要求极高（< 200ms） | 跳过 Reranker，只用 Embedding |
| 文档高度同质化（全是同一类内容） | Reranker 增益不大 |
| 知识库 > 1000 条且要求准确 | **必须上 Reranker** |
| 多语言混合文档 | Reranker 精度提升明显 |

---

## 5.8 RAG 核心概念速查

| 组件 | 作用 | 所属阶段 | 关键方法 |
|------|------|---------|---------|
| `Document` | 文档对象（内容+元数据） | 加载 | `.page_content`, `.metadata` |
| `TextSplitter` | 切分长文档 | 离线建库 | `split_documents(docs)` |
| `Embeddings (BGE-M3)` | 文本 → 向量 | 离线+在线 | `embed_query()`, `embed_documents()` |
| `VectorStore (ChromaDB)` | 存储和搜索向量 | 离线+在线 | `from_documents()`, `similarity_search()` |
| `Retriever` | 粗检索（召回） | 在线 | `invoke(query)` → Top-K 文档 |
| `Reranker (BGE-Reranker)` | 精排（重排序） | 在线 | `compress_documents()` → 精选 Top-N |
| `ContextualCompressionRetriever` | 粗检+精排组合 | 在线 | 自动先粗后精 |

---

## 小结

RAG 是 LangChain 最重要的应用模式，**推荐的两阶段流水线**：

```
离线：文档 → 分割 → BGE-M3嵌入 → ChromaDB向量库

在线：用户提问 → BGE-M3向量检索(k=10) → BGE-Reranker精排(top_n=3) → Prompt → LLM → 回答
                └── 召回阶段（快，广）──┘    └── 精排阶段（慢，准）──┘
```

**核心原理**：
- **Embedding** = 双向独立编码后算相似度 → 速度快，适合海量召回
- **Reranker** = 拼接后联合编码直接打分 → 精度高，适合精选过滤
- 两者配合 = "先用筛子粗筛，再用放大镜细看"

👉 下一模块：[智能体与工具](06-agents-tools.md)
