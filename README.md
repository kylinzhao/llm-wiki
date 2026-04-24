# LLM Wiki Skill

## 1. 这是什么

`llm-wiki` 是一个全局可调用的 Codex skill，用来处理一套文件型 LLM Wiki 的完整生命周期：

- 0-1 初始化
- 确定性构建
- AI-native 精修
- 增量维护
- 查询问答
- 质量审查

它面向的不是“只会查”的场景，而是“把一个项目从原始文档变成可用知识库”的全链路工作。
对于已经建好的 wiki，查询也统一通过 `llm-wiki` 完成，不再维护单独的 query-only skill。

## 2. 适用场景

### A. 新项目 0-1

例如：

- `我现在 raw 和 BUSINESS_CONTEXT 都准备好了，怎么开始构建项目？`
- `帮我从 0-1 初始化一套 LLM Wiki 仓库`

### B. 增量维护

例如：

- `新加了一批 raw，帮我增量更新 wiki`
- `我更新了业务说明文档，帮我看看要不要重建`

### C. 业务问答

例如：

- `车商直联目前有什么问题？`
- `新能源专区最近几轮方案和复盘主线是什么？`

### D. 质量审查

例如：

- `不要生成内容，纯检查这套 wiki 是否真的可用`
- `检查 concepts / entities 有没有冲突`

## 3. 项目原理

这套架构不是传统 wiki，也不是纯向量库，而是五层组合：

1. `raw/` 原始证据层
2. `BUSINESS_CONTEXT.md` 业务语义基线
3. `wiki/sources/` 主知识层
4. `wiki/proposals/evidence/reference/operations/conflicts/truth` 分层投影视图
5. `wiki/concepts/`、`wiki/entities/`、`graph/` 索引与图谱层

因此它的核心思路是：

- 先把结构搭起来
- 再把语义写清楚
- 最后让 agent 能按协议查询

## 4. 为什么构建和查询必须放在一起

如果把“构建 skill”和“查询 skill”完全拆开，会出现两个问题：

- 查询时不知道这套库是怎么生成的，容易误判页面可信度
- 构建时没有查询协议，后续新窗口不知道该如何使用成果

所以统一 skill 的原则是：

- 构建协议和查询协议放在一起
- `BUSINESS_CONTEXT.md` 同时约束生成和查询
- 同一套目录语义同时服务 build 和 query

## 5. 关键输入

一个新项目最重要的两个输入是：

### `raw/`

原始文档目录，是不可变输入。

### `BUSINESS_CONTEXT.md`

根目录业务说明文档，是业务语义基线。

它适合存放：

- 实体定义
- 同义词归并
- 历史叫法与规范叫法映射
- 角色边界
- 业务缩写解释
- 容易误判的概念说明

例如：

- `C1 = 卖车 C 端用户`
- `车主 = C1 的历史别名`
- `C2 = 购车 C 端用户`

## 6. 文档结构

### `wiki/sources/`

主知识页，一篇 raw 对应一篇主 digest。

### `wiki/proposals/`

方案、规划、设计、需求、草案。

### `wiki/evidence/`

实验、复盘、分析、归因、数据结论。

### `wiki/reference/`

接口、字段、规则、参数、手册、字典。

### `wiki/operations/`

SOP、活动执行、流程落地、运营动作。

### `wiki/conflicts/`

问题、风险、争议、未决项、冲突。

### `wiki/truth/`

当前事实、稳定状态、明确说明。

### `wiki/concepts/`

按主题聚合的索引层。

### `wiki/entities/`

按实体聚合的索引层。

### `graph/`

由 wikilink 抽取生成的关系图谱。

### `staging/`

构建中间产物与辅助材料。

## 7. 0-1 构建顺序

从一个全新项目开始，推荐顺序是：

1. 准备 `raw/`
2. 准备 `BUSINESS_CONTEXT.md`
3. 初始化 `wiki/graph/staging/docs/tools`
4. 运行确定性构建
5. 做健康检查
6. 做 AI-native 文本精修
7. 重建 graph

标准命令：

```text
uv run python tools/build_wiki.py
uv run python tools/health.py --json
uv run python tools/build_graph.py
```

这三步分别负责：

- `build_wiki.py`：搭 wiki 骨架
- `health.py`：检查结构是否健康
- `build_graph.py`：把 wikilink 连成图谱

## 8. 查询逻辑

默认查询顺序是：

1. 识别问题类型
2. 读取 `BUSINESS_CONTEXT.md`
3. 提取关键词和近义词
4. 选择优先目录层
5. 扩展 `concepts / entities`
6. 回到 `sources`
7. 必要时回 `raw/`
8. 输出结论、证据和未决点

问题类型与优先层：

- 问题/风险：`conflicts -> evidence -> proposals -> sources`
- 证据/效果：`evidence -> sources`
- 方案/规划：`proposals -> sources`
- 接口/规则：`reference -> truth -> sources`
- 当前状态：`truth -> reference -> sources`
- 操作执行：`operations -> sources`

## 9. 图片策略

当前默认是：

- 文本优先
- 不主动做图片多模态识别
- 只有用户明确要求，或文本明显不足以回答时，才把图片纳入主链路

所以这套 skill 的默认行为是：

- 先用文本 wiki 回答
- 不默认启动图片分析

## 10. 推荐用法

### 新项目 0-1

```text
Use $llm-wiki to bootstrap a new LLM Wiki project from raw/ and BUSINESS_CONTEXT.md. Explain the phases first, then initialize the structure, build deterministic outputs, and tell me what still needs AI-native refinement.
```

### 已有项目查询

```text
Use $llm-wiki against this project. Read BUSINESS_CONTEXT.md first, state the query type and retrieval path, then answer with supporting wiki pages and unresolved points.
```

### 质量审查

```text
Use $llm-wiki to audit this wiki project. Check entry usability, semantic consistency, retrieval usefulness, layered-page quality, and concept/entity conflicts. Put findings first with file paths and a final usability verdict.
```

## 11. 参考文件

skill 核心文件：

- [SKILL.md](./SKILL.md)
- [agents/openai.yaml](./agents/openai.yaml)

参考材料：

- [bootstrapping.md](./references/bootstrapping.md)
- [build-and-maintenance.md](./references/build-and-maintenance.md)
- [project-principles.md](./references/project-principles.md)
- [wiki-structure.md](./references/wiki-structure.md)
- [query-logic.md](./references/query-logic.md)
