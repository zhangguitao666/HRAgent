# PandaWiki 知识库管理系统详解

> 基于 `chaitin/PandaWiki` 源码分析 · Go + PostgreSQL + Redis

---

## 一、核心概念

PandaWiki 的知识库不是简单的"文档集合"，而是一个**完整的内容管理 + 版本发布 + 权限控制 + 向量检索 + 多端输出**的系统。

### 6 个核心实体及关系

```
KnowledgeBase (知识库)
  ├── dataset_id ──→ RagLite (向量引擎)
  │                   └── Documents → Chunks (分块向量)
  │
  ├── Nav (导航分类)
  │   └── Node (文档/文件夹)
  │       ├── Status: 未发布 | 草稿 | 已发布
  │       └── NodeRelease (发布快照)
  │           └── doc_id → RAG 文档索引
  │
  ├── App (应用配置)
  │   └── 类型: Web站点 | 嵌入式挂件 | 钉钉/飞书/企微机器人 | MCP Server
  │
  ├── Users (KB 用户)
  │   └── 权限: 全控 | 文档管理 | 数据操作
  │
  └── Releases (版本发布)
      └── Tag + 发布说明 + 快照集合
```

---

## 二、知识库数据模型

### 2.1 KnowledgeBase 主体

```go
type KnowledgeBase struct {
    ID             string         // UUID 主键
    Name           string         // 知识库名称
    DatasetID      string         // 关联向量引擎的 dataset
    AccessSettings AccessSettings // 访问控制配置 (JSONB)
}
```

### 2.2 AccessSettings — 多维度访问控制

```go
type AccessSettings struct {
    Ports          []int       // HTTP 端口 (Caddy 反向代理)
    SSLPorts       []int       // HTTPS 端口
    PublicKey      string      // SSL 证书
    PrivateKey     string      // SSL 私钥
    Hosts          []string    // 绑定的域名
    BaseURL        string      // 显式基础 URL
    SimpleAuth     SimpleAuth  // 密码认证
    EnterpriseAuth EnterpriseAuth // 企业 SSO (GitHub/OAuth/CAS/LDAP)
    IsForbidden    bool        // 总开关: 禁止公开访问
}
```

**三种认证模式**：
| 模式 | 配置 | 行为 |
|------|------|------|
| Null | 无任何认证 | 完全公开访问 |
| Simple | 设置密码 | 浏览器 Session 验证 |
| Enterprise | 配置 SSO 提供者 | GitHub/OAuth/CAS/LDAP 登录 |

---

## 三、文档管理 — 树形结构 + 版本快照

### 3.1 Node 模型（文档/文件夹）

```go
type Node struct {
    ID          string      // UUID
    KBID        string      // 所属知识库
    NavId       string      // 所属导航分类
    Type        NodeType    // 1=文件夹, 2=文档
    Status      NodeStatus  // 0=未发布, 1=草稿(有未发布修改), 2=已发布
    Name        string
    Content     string      // Markdown 或 HTML 全文
    Meta        NodeMeta    // {摘要, Emoji, 内容类型}
    ParentID    string      // 父节点 (树形结构)
    Position    float64     // 排序位置 (支持拖拽重排)
    Permissions NodePermissions
}
```

**三种状态流转**：
```
未发布(0) ──→ 已发布(2) ──→ 草稿(1) ──→ 已发布(2)
              (首次发布)    (修改后)    (再次发布)
```

### 3.2 树形组织结构

```
知识库 (KB)
  └── 导航 1: "人事制度"
      ├── 📁 考勤管理 (文件夹)
      │   ├── 📄 出差管理办法
      │   ├── 📄 休假管理办法
      │   └── 📄 加班管理规定
      ├── 📁 薪酬福利
      │   ├── 📄 工资发放制度
      │   └── 📄 公积金管理办法
      └── 📄 员工手册 (文档)
  └── 导航 2: "技术文档"
      └── ...
```

- **文件夹**可以无限嵌套
- **文档**是叶子节点
- `Position` 用 float64 实现无限精度插入（新节点取相邻两节点中间值）
- 支持跨导航拖拽移动

### 3.3 三级权限控制

```go
type NodePermissions struct {
    Answerable NodeAccessPerm  // 谁能通过 AI 问答获取本文档内容
    Visitable  NodeAccessPerm  // 谁能查看文档详情页
    Visible    NodeAccessPerm  // 谁能在侧边栏看到本文档
}
```

每级权限可选：
- `"open"` — 所有人
- `"partial"` — 指定用户组
- `"closed"` — 仅管理员

---

## 四、版本发布系统 — 最核心的设计

PandaWiki 的发布系统采用了 **"编辑-预览-发布"分离** 的设计模式：

### 4.1 发布流程

```
                    ┌──────────┐
  编辑文档 ──────→  │  nodes   │  (草稿区)
                    │  表      │
                    └────┬─────┘
                         │ CreateKBRelease()
                         ▼
                    ┌──────────────┐
                    │ node_releases │  (发布快照)
                    │   表          │
                    └──────┬───────┘
                           │ 异步 MQ 任务
                           ▼
                    ┌──────────────┐
                    │  RagLite     │  (向量索引)
                    │  UpsertRecords│
                    └──────────────┘
```

### 4.2 发布数据结构

**KBRelease** — 一次发布操作：
```go
type KBRelease struct {
    ID      string  // 发布 UUID
    KBID    string  // 所属知识库
    Tag     string  // 版本标签, 如 "v1.2.0"
    Message string  // 发布说明
}
```

**NodeRelease** — 单个文档的快照：
```go
type NodeRelease struct {
    ID       string // 快照 UUID
    NodeID   string // 原始节点 ID
    DocID    string // RAG 向量引擎的文档 ID
    Name     string // 快照时的文档名
    Content  string // 快照时的完整内容
    Position float64
    ParentID string
}
```

**KBReleaseNodeRelease** — 关联表：
```go
// 一次发布包含哪些节点的哪些快照
KBRelease(ID) ←→ NodeRelease(IDs)
```

### 4.3 发布步骤详解

```
CreateKBRelease():
  1. 可选: 指定要发布的 NodeID 列表
  2. 为每个 Node 创建 NodeRelease 快照
     └─ 复制当前 name/content/position/parentID
  3. 创建 KBRelease 记录 (版本标签 + 说明)
  4. 异步投递 MQ 任务:
     └─ AsyncUpdateNodeReleaseVector → RagLite.UpsertRecords()
        ├─ HTML → Markdown 自动转换
        ├─ 按 ChunkTokenNum 分块
        ├─ 生成嵌入向量
        └─ 存入向量索引
```

**关键特性**：
- 编辑影响 `nodes` 表 → 不影响正在服务的 wiki
- 发布创建 `node_releases` 快照 → 冻结当前版本
- 向量索引仅在发布时更新 → 避免搜索到未完成的编辑
- 发布可选范围 → 可以只发布某些文档

---

## 五、应用输出 — 一套内容，多种形态

```go
type AppType int
const (
    AppTypeWeb              AppType = 1   // 公开 Wiki 网站
    AppTypeWidget           AppType = 2   // 可嵌入网页挂件
    AppTypeDingTalkBot      AppType = 3   // 钉钉机器人
    AppTypeFeishuBot        AppType = 4   // 飞书机器人
    AppTypeWechatBot        AppType = 5   // 企业微信机器人
    AppTypeDisCordBot       AppType = 7   // Discord 机器人
    AppTypeOpenAIAPI        AppType = 9   // OpenAI 兼容 API (可对接 AI Agent)
    AppTypeMcpServer        AppType = 12  // MCP Server (AI Agent 工具调用)
)
```

**最重要的两种模式**：

1. **Wiki 网站** (`AppTypeWeb`) — 通过 Caddy 反向代理提供独立的静态/SSR 站点
2. **OpenAI API** (`AppTypeOpenAI`) — 暴露 `/v1/chat/completions` 兼容端点，任何 AI Agent 都可以把 PandaWiki 当作一个"带 RAG 的 LLM"来调用

---

## 六、检索同步状态追踪

每个 Node 都有一个 `RagInfo` 字段追踪向量同步状态：

```go
RagInfo.Status:
  PENDING   → 等待处理 (刚发布，MQ 消息已投递)
  RUNNING   → 处理中 (RagLite 正在分块/嵌入)
  SUCCEEDED → 成功 (可被检索)
  FAILED    → 失败 (需排查)
  REINDEX   → 重新索引中
```

**管理端操作**：
- `ReStudy` — 强制重新索引某个文档
- `ListDocuments` — 查看 RAG 中的文档列表及状态

---

## 七、Wiki 网站渲染流程

用户访问 `https://wiki.company.com/doc/xxx` 时的完整链路：

```
浏览器
  │
  ▼
Caddy 反向代理
  │  (根据域名匹配 KB, 注入 X-KB-ID header)
  │  (SSL 终止, 路由到后端)
  ▼
Share Handler (/share/v1/*)
  │
  ├─→ GET /app/web/info  ──→ 返回主题/导航/页脚/SEO 配置
  ├─→ GET /nav/list       ──→ 返回导航树 (NavRelease)
  ├─→ GET /node/list      ──→ 返回文档树 (NodeRelease, 按权限过滤)
  └─→ GET /node/detail    ──→ 返回文档全文 (NodeRelease, 检查 Visitabile)
  │
  ▼
前端 SPA (React)
  │  获取配置 + 数据 → 渲染 Wiki 页面
  │  包含: 导航侧边栏 + 文档内容 + 搜索 + AI 问答入口
```

**权限控制贯穿始终**：
- `Visible` — 控制侧边栏是否显示该文档
- `Visitable` — 控制是否能打开文档详情
- `Answerable` — 控制 AI 问答是否能引用该文档

---

## 八、用户权限体系

### 系统级角色
| 角色 | 能力 |
|------|------|
| Admin | 创建/删除知识库，管理所有用户 |
| User | 只能访问被邀请的知识库 |

### KB 级权限
| 权限级别 | 能力 |
|----------|------|
| `full_control` | 管理 KB 设置、用户、权限 |
| `doc_manage` | 创建/编辑/发布文档 |
| `data_operate` | 查看和操作数据 |

### 用户组 (AuthGroup)
- 用户可以被加入多个组
- 组可以嵌套（父子继承）
- 文档权限绑定到组，而非个人
- 检索时 GroupIDs 用于过滤可访问的向量

---

## 九、知识库完整生命周期

```
1. 创建 KB
   ├── 系统调用: RAGService.CreateKnowledgeBase() → 获得 datasetID
   └── DB 记录: INSERT INTO knowledge_bases

2. 配置访问
   ├── 绑定域名 (Hosts)
   ├── 配置 SSL (证书 + 端口)
   └── 设置认证 (公开/密码/SSO)

3. 搭建内容
   ├── 创建导航分类 (Nav)
   ├── 创建文档 (Node, Type=Document)
   │   ├── 富文本编辑器写入内容 (Markdown/HTML)
   │   ├── 设置权限 (谁可见/可访问/可AI问答)
   │   └── 在树中拖拽排序
   └── 创建文件夹组织层级 (Node, Type=Folder)

4. 发布版本
   ├── 调用 CreateKBRelease()
   ├── 系统自动: 创建 NodeRelease 快照
   ├── 异步任务: 向量索引 → RagLite
   └── Wiki 网站立即可访问新版本

5. 日常运营
   ├── 编辑文档 → Status 变为 Draft
   ├── 再次发布 → 新快照覆盖旧版本
   ├── AI 问答 → 基于最新发布的向量索引
   └── 用户反馈 → 文档评价/评论

6. 多端分发
   ├── Wiki 网站 (AppTypeWeb)
   ├── 嵌入式挂件 (AppTypeWidget)
   ├── 钉钉/飞书/企微机器人
   ├── OpenAI API (供 AI Agent 调用)
   └── MCP Server (供 IDE AI 工具调用)

7. 销毁 KB
   ├── 删除 DB 记录 (级联删除节点/发布/用户关联)
   └── 删除向量索引 (RAGService.DeleteKnowledgeBase)
```

---

## 十、与普通文件存储的对比

| 特性 | 普通文件系统/云盘 | PandaWiki KB |
|------|-------------------|--------------|
| 内容存储 | 二进制文件 | Markdown/HTML + 向量嵌入 |
| 版本管理 | 文件名后缀或覆盖 | 发布快照(不可变) + 草稿分离 |
| 搜索 | 文件名/全文关键词 | 语义搜索(向量) + 关键词 + Rerank |
| 权限 | 目录级 | 文档级(可见/可访/可问答三轴) |
| 输出形态 | 原始文件 | 网站/机器人/API 多形态 |
| AI 能力 | 无 | 内建 RAG 问答 + AI 创作辅助 |
