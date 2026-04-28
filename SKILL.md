---
name: llm-wiki
description: 在项目中从 0-1 初始化、构建、增量维护、查询和审查一套基于 raw 文档、raw-code 源码库与 BUSINESS_CONTEXT.md 的 LLM Wiki。适用于新项目冷启动、需求文档 wiki、代码 wiki、需求-代码联合知识层、文本优先语义精修、实体/概念归一化、graph/health 维护、以及新窗口中的业务/代码问答和质量检查。
---

# LLM Wiki

这个 skill 面向“文件型 LLM Wiki 项目”的全生命周期，而不只是查询。
它也是这类项目后续唯一推荐维护和调用的统一入口，不再需要拆分单独的 query-only skill。

它适用于：

- 新项目 0-1 初始化
- 已有项目的增量构建
- `raw/` 需求文档与 `raw-code/` 多源码仓库的联合 wiki 构建
- `BUSINESS_CONTEXT.md` 驱动的业务语义规范化
- 基于 `wiki/`、`wiki/code/` 的业务/代码查询与审查

## 必查入口

开始前先确认项目根目录里是否存在：

- `raw/`
- `BUSINESS_CONTEXT.md`

如果项目根目录存在 `raw-code/`：

- 将 `raw-code/*` 的每个一级目录视为一个 `codebase_id`
- 先识别每个源码库的技术栈、入口、模块边界和本地说明文档
- 不要把代码证据混入 `raw/` 需求证据层

如果项目已经初始化，还要确认：

- `wiki/index.md`
- `wiki/overview.md`
- `docs/retrieval-playbook.md`
- `docs/build-and-maintenance.md`

如果缺文件，不要假装项目已经完整可用，要先说明缺什么，再走初始化或补档流程。

## 阅读顺序

### 新项目 / 构建任务

- `/Users/zhaoliang/.codex/skills/llm-wiki/README.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/bootstrapping.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/build-and-maintenance.md`
- 如果存在 `raw-code/`：`/Users/zhaoliang/.codex/skills/llm-wiki/references/code-wiki.md`

### 已有项目 / 查询任务

- `/Users/zhaoliang/.codex/skills/llm-wiki/README.md`
- `docs/retrieval-playbook.md`
- `docs/build-and-maintenance.md`
- 如果问题涉及代码实现或项目存在 `wiki/code/`：`/Users/zhaoliang/.codex/skills/llm-wiki/references/code-wiki.md`

### 按需读

- `/Users/zhaoliang/.codex/skills/llm-wiki/references/project-principles.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/wiki-structure.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/query-logic.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/subagent-handoff.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/image-evidence.md`

## 续跑优先级

如果项目不是空目录，默认按“继续未完成阶段”处理，而不是从头重建。

开始前优先读取：

1. `BUSINESS_CONTEXT.md`
2. `staging/refinement-status.md`
3. `staging/health/latest.json`
4. `graph/summary.md` 或 `staging/graph/latest.json`
5. `wiki/overview.md`
6. `docs/build-and-maintenance.md`
7. `docs/retrieval-playbook.md`

续跑规则：

- 保留已有 `wiki/`、AI refinement、人工编辑和 `wiki/code/` 页面。
- 只有 `raw/`、`BUSINESS_CONTEXT.md`、taxonomy、entity 规则或大批量 wikilink 变化时，才考虑宽范围重建。
- 如果已有 health、graph、source 精修或 G+ 产物，应先补齐未完成部分。
- 每轮重要写入后更新 `staging/refinement-status.md`，再运行 health 和 graph 收口。

## 核心工作方式

### 1. 阶段模型

默认阶段：

1. 阶段 A：输入与状态检查
2. 阶段 B：项目骨架初始化
3. 阶段 C：确定性构建
4. 阶段 D：health 初检
5. 阶段 E：AI-native source 全量精修
6. 阶段 F：代码 wiki / 联合知识层（当 `raw-code/` 存在且任务需要）
7. 阶段 G：graph 构建与首轮验收
8. 阶段 G+：综合层二次校准、查询验收、质量审查
9. 阶段 H：选择性高价值图片证据补充
10. 阶段 I：发布 / 提交 / 远端同步
11. 阶段 M：后续增量维护

### 2. 新项目优先构建，不优先查询

如果项目还没有 `wiki/` 骨架，应先做：

1. 检查 `raw/` 和 `BUSINESS_CONTEXT.md`
2. 初始化目录结构
3. 运行确定性构建
4. 对全量语料完成首轮大模型 summary 与 AI-native 精修
5. 如果存在 `raw-code/`，构建代码 wiki 与需求-代码跨层链接
6. 运行健康检查
7. 最后构建 graph

这里的“首轮大模型 summary 与 AI-native 精修”是 0-1 初始化的必要环节，不应只停留在骨架、索引和占位页。
可以按 `sources -> layered pages -> concepts/entities` 分层推进，但默认应在同一轮里一口气完成，而不是把全量精修留到后续再补。

### 3. 已有项目优先读 BUSINESS_CONTEXT

在任何生成、查询、审查任务前，如果根目录存在：

- `BUSINESS_CONTEXT.md`

都要优先读取它，并把它当成业务语义基线。

### 4. 默认文本优先

除非用户显式要求或文本不足以回答，否则默认：

- 不主动做图片多模态识别
- 不把 `staging/image-notes/` 当默认主链路
- 代码也按文本证据处理，先使用 AST/路由/API/调用关系/技术设计文档，不默认进入截图或视觉资产

文本层完成后可以进入阶段 H，但只处理高价值图片证据。图片 note 必须结合图片在 `raw/**/index.md` 中的前后文，不做裸图 OCR。低价值页面走查、重复 UI 截图、装饰图默认跳过。

### 5. 代码 wiki 是可选但一等的证据层

如果存在 `raw-code/`，默认应把它纳入构建/审查设计。推荐输出：

- `wiki/code/index.md`
- `wiki/code/codebases/<codebase_id>/`
- `wiki/code/capabilities/`
- `staging/code-graph/<codebase_id>/`

`wiki/code/codebases/<codebase_id>/` 记录单个源码库内部事实。
`wiki/code/capabilities/` 记录跨需求文档、前端、后端、异步任务、技术设计的业务能力实现链路。

可以使用 `graphify` 作为代码图谱增强层。它用于提取 AST、调用关系、代码结构报告和交互式图谱；`llm-wiki` 仍负责业务语义基线、Markdown 目录协议、跨层链接和可审计回答。

### 6. 速度与并发优先

大型 wiki 构建、代码 wiki 构建和质量审查默认应追求吞吐，不应把可并行工作串行化。

- 可以独立推进的 codebase、目录层、能力页、source 批次、graphify 分析、health 审查，应使用 subagent 并发执行。
- 多个简单、相近、低风险的小任务可以打包给同一个 subagent，一次性完成，避免为每个小页面启动单独 subagent。
- 不要让多个 subagent 写同一文件或同一能力页；并发任务必须有清晰、互不重叠的输出范围。
- 主 agent 负责全局协议、命名、跨层链接、最终整合和质量口径；subagent 负责局部扫描、摘要、页面草稿、映射表和审查发现。
- 如果当前环境不能使用 subagent，也要用批次化策略推进，并在输出中说明并发受限。

阶段 E backlog 充足时，默认保持多 worker 并行；简单 source 可以 2-4 页打包，复杂长文档单页独占。使用 subagent 前按需读取 `references/subagent-handoff.md`。

### 7. 查询路径必须显式

不管是问答还是审查，都要说明：

- 问题类型
- 是否用了 `BUSINESS_CONTEXT.md`
- 先查哪一层目录
- 有没有用 `concepts / entities` 扩展
- 最终依据了哪些 `sources`
- 如果使用代码证据，还要说明使用了哪些 `wiki/code/` 页面、代码库、接口、类或方法

### 8. 规范实体优先

优先使用项目内规范实体，而不是历史别名。

例如在当前项目里：

- `C1` = 卖车 C 端用户
- `C2` = 购车 C 端用户
- `车主` = `C1` 的历史别名

如果旧页面和 `BUSINESS_CONTEXT.md` 冲突，应优先按 `BUSINESS_CONTEXT.md` 理解，并在回答中指出冲突。

### 9. 自动继续与停机条件

默认可自动继续：

- source 精修
- G+ 综合
- query acceptance
- quality audit
- broken wikilink 修复
- index 文案修正
- health / graph 收口
- 高价值图片证据补充
- remote 已明确且 `raw/` 已排除时的提交推送

必须停下来等用户确认：

- 需要改变 canonical entity 或业务口径
- 业务判断无法由 source / code evidence 支撑
- 是否处理低价值或大批量图片
- 是否提交 `raw/`
- 是否覆盖、迁移或替换已有远端仓库

### 10. 安全与证据边界

- 可以读取 `raw/`，不得修改 `raw/`。
- `raw/` 不应被提交到 Git；提交前检查它没有被 track 或 staged。
- 不调用本地模型 SDK 做摘要、分类、实体归一或语义判断；这些由 Codex / subagent 完成。
- 本地脚本只做确定性扫描、health、graph、文件统计和格式检查。
- 不把 token、cookie、密码、私钥、access key、内部凭据或完整敏感配置值写入 wiki；必要时只写用途并脱敏。
- 不修改项目 `tools/` 来产品化一次性 workflow，除非用户明确要求。

## 任务模式

### A. 0-1 初始化

适用于：

- 新项目只有 `raw/`
- 新项目已有 `raw/` 和 `BUSINESS_CONTEXT.md`
- 需要搭一整套 `wiki/graph/staging/tools/docs`
- 需要在首轮里完成全量语料的 summary、分层落位和 AI-native 精修

### B. 增量构建

适用于：

- 新增了一批 `raw/`
- 更新了 `BUSINESS_CONTEXT.md`
- 调整了 taxonomy / entity 规则

### C. 查询问答

适用于：

- 业务问题
- 专题串讲
- 概念/实体解释
- 分层目录解释

### D. 质量审查

适用于：

- 检查 wiki 是否真的可用
- 检查实体/概念冲突
- 检查 layered pages 是否错分
- G+ 阶段必须输出查询验收和质量审查

### E. 代码 wiki / 联合知识层

适用于：

- 项目存在 `raw-code/`
- 需要从前端、后端或多源码仓库生成代码 wiki
- 需要把需求文档、业务概念、接口、页面、服务、异步任务和技术设计打通
- 需要回答“需求说了什么、代码实际怎么实现、还有哪些证据缺口”

## 输出要求

### 构建任务

至少说明：

1. 当前处于哪个阶段
2. 缺什么输入
3. 先执行哪些命令
4. 首轮是否包含全量 summary / AI-native 精修
5. 是否存在 `raw-code/`，会纳入哪些 `codebase_id`
6. 是否使用 `graphify`，输出位置在哪里
7. 哪些需求页面、代码页面和能力页面会在本轮被一口气做完，哪些只能明确留待后续
8. 当前是否是续跑；如果是，说明从哪个 checkpoint 或状态文件继续

### 查询任务

至少说明：

1. 查询类型
2. 检索路径
3. 结论
4. 支撑页面
5. 未决点
6. 如果涉及代码，区分“需求文档证明”“代码实现证明”“推断”“缺失证据”

### 审查任务

必须 findings first。

### G+ 任务

至少说明：

1. source 精修是否已完成
2. concepts/entities/truth/conflicts/evidence/proposals/reference/operations 的二次校准状态
3. `docs/query-acceptance.md` 状态
4. `docs/gplus-quality-audit.md` 状态
5. health / broken wikilinks / graph 状态

### 代码 wiki 任务

至少说明：

1. codebases discovered
2. graphify status
3. pages created or updated
4. capability coverage
5. frontend-backend mappings
6. requirement evidence linked
7. code evidence linked
8. inference-only links
9. missing evidence
10. validation results

## 推荐入口

### 中文短入口

`用 $llm-wiki 继续维护这个项目。先读 BUSINESS_CONTEXT.md 和当前状态，从未完成阶段续跑，不要重建已完成内容。`

`用 $llm-wiki 构建需求+代码联合 wiki。raw 是需求证据，raw-code 是代码证据，按现有协议并发推进并输出验收结果。`

`用 $llm-wiki 查询这个问题。先读 BUSINESS_CONTEXT.md，说明查询类型、检索路径、结论、支撑页面和未决点。`

### 新项目初始化

`Use $llm-wiki to bootstrap a new LLM Wiki project from raw/ and BUSINESS_CONTEXT.md. Explain the phases first, then initialize the structure, build deterministic outputs, and tell me what still needs AI-native refinement.`

`Use $llm-wiki to bootstrap a new LLM Wiki project from raw/ and BUSINESS_CONTEXT.md. Treat first-pass full-corpus summary and AI-native refinement as part of the initial build, not as an optional later cleanup. You may process it layer by layer, but finish the full first-round corpus build in one run if feasible.`

### 查询已有 wiki

`Use $llm-wiki against this project. Read BUSINESS_CONTEXT.md first, state the query type and retrieval path, then answer with supporting wiki pages and unresolved points.`

### 质量审查

`Use $llm-wiki to audit this wiki project. Check entry usability, semantic consistency, retrieval usefulness, layered-page quality, and concept/entity conflicts. Put findings first with file paths and a final usability verdict.`

### 需求 + 代码联合 wiki

`Use $llm-wiki to build a joint business-and-code LLM Wiki. Read BUSINESS_CONTEXT.md first, treat raw/ as immutable business evidence, treat raw-code/* as separate codebases, use graphify when available for code graph extraction, then create wiki/code/codebases and wiki/code/capabilities pages that link code facts back to concepts, entities, and source documents.`

### 代码实现查询

`Use $llm-wiki against this project. Read BUSINESS_CONTEXT.md first, then answer this implementation question by checking wiki/code/codebases, wiki/code/capabilities, concepts/entities, and source documents. Clearly separate requirement evidence, code evidence, inference, and missing evidence.`
