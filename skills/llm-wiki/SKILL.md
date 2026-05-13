---
name: llm-wiki
description: 在项目中从 0-1 初始化、构建、增量维护、查询和审查一套基于 raw 文档、raw-code 源码库与 BUSINESS_CONTEXT.md 的 LLM Wiki。适用于新项目冷启动、需求文档 wiki、代码 wiki、需求-代码联合知识层、文本优先语义精修、实体/概念归一化、graph/health 维护、以及新窗口中的业务/代码问答和质量检查。
---

# LLM Wiki

这个 skill 面向“文件型 LLM Wiki 项目”的全生命周期，而不只是查询。
它也是这类项目后续唯一推荐维护和调用的统一入口，不再需要拆分单独的 query-only skill。

## Skill 包路径

文档中的 `README.md`、`references/...`、`scripts/...` 均相对于 **llm-wiki skill 包根目录**（与 `SKILL.md`、`scripts/` 同级的文件夹）。该根目录须从当前环境解析（例如根据已加载的 skill 文件路径、或 Codex/Cursor 等下的实际安装位置），**禁止**写死个人本机绝对路径。

**按本仓库 `install.sh` 安装后**，可直接使用（以 Codex 默认目录为例；Claude Code / Cursor 只需替换为各自 skills 根目录）：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"
```

其他布局下将 `$LLM_WIKI_SKILL_ROOT` 设为上述根目录即可：

```bash
python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"
```

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

若仓库**只提交了构建后的 `wiki/`**，而 `raw/` / `raw-code/` 由单独流程同步：先读 `staging/health/latest.json` 的 `evidence_gaps` / `recommended_actions`。当工具报 `missing_raw_evidence` 或 `missing_raw_code_evidence` 时，**主动提示用户**拉取原始证据后再执行 `update` / `build-code` / `code-trace`，不要假装可以完整重建。只读 `query` / `doctor` 仍可按 `references/commands.md` 的 Evidence preflight 规则进行。

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

新项目初始化时必须先安装随 skill 打包的项目模板，除非目标项目已经有等价脚本：

```bash
python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"
```

该模板提供 `tools/build_wiki.py`、`tools/scan_code.py`、`tools/graphify_code.py`、`tools/build_traceability.py`、`tools/health.py`、`tools/build_graph.py`、`tools/anchor_check.py`、项目 `AGENTS.md`、`.gitignore` 和依赖说明。模板脚本只做确定性扫描、脚手架、校验和图谱构建；语义 summary、实体归一、能力判断和证据强度仍由 Codex / subagent 完成。

**内置 Confluence/Cwiki 下载（无需单独安装 obsidian-wiki-export skill）**：模板中包含 `tools/confluence_sync/export_obsidian_wiki.py`。安装模板并 `uv sync` 后，用带 `pageId` 的空间页面 URL 可把 wiki 树落入 **`raw/<pageId>-<slug>/index.md`**（每页目录 + `assets/`），同步元数据（`export-state.json`、`progress/`、`manifest-*.json`）默认写在 **`staging/wiki-export/`**，不把状态文件放进 `raw/`。详见 `references/bootstrapping.md`「从 wiki URL 拉取 raw」。

## 阅读顺序

### 新项目 / 构建任务

- `README.md`（llm-wiki 包内）
- `references/bootstrapping.md`
- `references/build-and-maintenance.md`
- 如果存在 `raw-code/`：`references/code-wiki.md`

### 已有项目 / 查询任务

- `README.md`（llm-wiki 包内）
- `docs/retrieval-playbook.md`
- `docs/build-and-maintenance.md`
- 如果问题涉及代码实现或项目存在 `wiki/code/`：`references/code-wiki.md`

### 按需读

- `references/project-principles.md`
- `references/wiki-structure.md`
- `references/architecture-and-retrieval.md`
- `references/query-logic.md`
- `references/commands.md`
- `references/subagent-handoff.md`
- `references/image-evidence.md`
- `references/fe-req-review-skill.md`

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

### 0. 二级命令路由

`llm-wiki` 是统一入口，但推荐用二级命令降低提示词长度。看到这些命令时，先读取 llm-wiki 包内 `references/commands.md`：

- `llm-wiki fast`：新项目一口气完成标准首轮，从输入检查到 health / graph 收口；适合用户明确希望一次性跑完。
- `llm-wiki init`：0-1 初始化，可分阶段汇报。
- `llm-wiki resume`：读取状态文件，从未完成阶段续跑。
- `llm-wiki doctor`：只读诊断整个 LLM Wiki 站点状态，指出健康度、缺口、优化建议和下一步命令。
- `llm-wiki update`：`raw/`、`BUSINESS_CONTEXT.md`、`raw-code/`、wiki 或代码变化后的影响范围更新；结束前自动运行 health/graph/必要 anchor 检查，检查通过后提示是否进入 ship。
- `llm-wiki add-wiki`：把另一个文档/wiki 目录或 wiki URL 接入当前项目，作为新的 `raw/` 需求/业务证据来源；wiki URL 应尝试推导 RSS/feed，无法推导时要求用户手动提供，否则该来源 RSS 留空且不具备后续自动更新能力。
- `llm-wiki add-code`：把另一个项目代码库接入当前项目，作为新的 `raw-code/<codebase_id>/` 代码证据来源。
- `llm-wiki refine`：source / concepts / entities / layered pages 精修。
- `llm-wiki gplus`：综合层二次校准、查询验收、质量审查。
- `llm-wiki build-code`：构建或刷新 `wiki/code/codebases` 和 `wiki/code/capabilities`。兼容旧别名：`llm-wiki code`。
- `llm-wiki code-trace`：构建或更新 `wiki/code/traceability` 需求到代码追踪矩阵。兼容旧别名：`llm-wiki trace`。
- `llm-wiki query`：按意图分流回答业务或代码问题；业务知识默认不展开大量代码实现证据。
- `llm-wiki query-plus`：同时拉通业务/需求证据和代码实现证据，输出更详尽的联合答案。
- `llm-wiki review-requirement`：对新 PRD、Cwiki 页面或需求文档做证据型需求评审，纳入 raw 原文、图片、zip 原型、前端评审和代码能力证据。
- `llm-wiki audit`：findings-first 质量审查。
- `llm-wiki image`：高价值图片证据补充。
- `llm-wiki ship`：health / graph / 可选 anchor check 后提交发布。

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

例外：`llm-wiki review-requirement` 是需求评审命令。如果目标项目或目标需求证据中存在图片、截图、图表、附件图片或 zip 原型，必须把这些材料纳入需求证据层分析；图片必须用多模态详细识别，zip 很可能是 HTML 原型，必须解压到临时工作区并审查页面结构、交互、状态和静态资源关系。

### 5. 代码 wiki 是可选但一等的证据层

如果存在 `raw-code/`，默认应把它纳入构建/审查设计。推荐输出：

- `wiki/code/index.md`
- `wiki/code/codebases/<codebase_id>/`
- `wiki/code/capabilities/`
- `wiki/code/traceability/`
- `staging/code-graph/<codebase_id>/`

`wiki/code/codebases/<codebase_id>/` 记录单个源码库内部事实。
`wiki/code/capabilities/` 记录跨需求文档、前端、后端、异步任务、技术设计的业务能力实现链路。
`wiki/code/traceability/` 记录需求点到页面、URI、Controller/Dubbo、Service、配置、表、消息和任务的可审计追踪矩阵。

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
- 只有当问题涉及代码、实现状态或使用 `query-plus` 时，才说明使用了哪些 `wiki/code/` 页面、代码库、接口、类或方法；业务知识查询不要为了填格式而展开代码证据

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

### 11. 完成后建议下一步

每次执行任何 `llm-wiki` 命令后，最终输出都必须包含“建议下一步”：

- 基于当前项目状态，而不是泛泛建议。
- 给出 1-3 个优先级排序的下一步动作。
- 如果适合继续执行，直接推荐对应二级命令，例如 `llm-wiki update`、`llm-wiki code-trace`、`llm-wiki doctor`、`llm-wiki ship`。
- 如果同一轮变更同时留下 source 精修和代码追踪缺口，优先推荐继续 `llm-wiki update` 一次性收口；只有 traceability-only 时才单独推荐 `llm-wiki code-trace`。
- 对 `llm-wiki update` 来说，低风险 pending/stale/source/code-trace/health/graph 收口应在当前命令里继续完成；不要把“再跑一次 update”当成默认建议，除非有明确 blocker 或用户要求只做诊断/确定性阶段。
- 对 `llm-wiki update` 来说，最终建议必须根据检查结果分流：检查失败时建议修复或继续 update；检查通过且无阻塞时，提醒用户可以选择 `llm-wiki ship` 做发布/提交/推送前收口，但不要自动 ship。
- 如果当前状态已经健康，说明“可以暂停”的条件和后续触发 `update` 的时机。

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

### Doctor 任务

只读诊断，至少说明：

1. 当前阶段和整体 verdict
2. 输入层：`raw/`、`BUSINESS_CONTEXT.md`、`raw-code/`
3. 文档层：sources、layered pages、concepts、entities、G+ 产物
4. 代码层：codebases、capabilities、traceability、graphify
5. 校验层：health、broken links、graph、可选 anchor check
6. 风险与缺口
7. 优先级建议和下一步命令

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

### 追踪矩阵任务

至少说明：

1. 覆盖的业务能力和需求点
2. 需求来源
3. 前端页面 / 组件 / URI
4. Controller / Dubbo / Service / Method
5. 配置 / 表字段 / 消息 / 任务
6. 证据强度：`strong`、`partial`、`inferred`、`external`、`missing`
7. 关键代码锚点
8. 外部系统边界和缺口

## 推荐入口

### 中文短入口

`用 $llm-wiki fast 从 raw/ 和 BUSINESS_CONTEXT.md 初始化新项目，并按标准顺序一次性完成首轮构建、精修、代码 wiki、验收、health 和 graph。`

`用 $llm-wiki doctor 诊断整个 LLM Wiki 站点状态，告诉我哪里健康、哪里缺口最大、下一步建议怎么做。`

`用 $llm-wiki update 响应这次文档或代码变更。先判断影响范围；如果项目已配置 raw 或接入了 raw-code codebase，就先默认刷新它们，再只更新受影响的 source、concept/entity、code/capability/traceability 页面，最后跑 health 和 graph；检查通过后提醒我是否要继续 llm-wiki ship。`

`用 $llm-wiki add-wiki 添加这个文档目录或 wiki URL 到当前项目。保持 raw 不可变，建立来源记录；如果是 wiki URL，尝试推导 RSS，失败则要求我手动提供 RSS。`

`用 $llm-wiki add-code 添加这个代码项目到当前项目。把它作为 raw-code 下独立 codebase，构建代码 wiki 和必要的能力链接。`

`用 $llm-wiki 继续维护这个项目。先读 BUSINESS_CONTEXT.md 和当前状态，从未完成阶段续跑，不要重建已完成内容。`

`用 $llm-wiki build-code 构建需求+代码联合 wiki。raw 是需求证据，raw-code 是代码证据，按现有协议并发推进并输出验收结果。`

`用 $llm-wiki code-trace 构建需求到代码追踪矩阵，说明需求点、前端、后端、Service、表、消息和证据强度。`

`用 $llm-wiki 查询这个问题。先读 BUSINESS_CONTEXT.md，说明查询类型、检索路径、结论、支撑页面和未决点。`

### 新项目初始化

`Use $llm-wiki to bootstrap a new LLM Wiki project from raw/ and BUSINESS_CONTEXT.md. Explain the phases first, then initialize the structure, build deterministic outputs, and tell me what still needs AI-native refinement.`

`Use $llm-wiki to bootstrap a new LLM Wiki project from raw/ and BUSINESS_CONTEXT.md. Treat first-pass full-corpus summary and AI-native refinement as part of the initial build, not as an optional later cleanup. You may process it layer by layer, but finish the full first-round corpus build in one run if feasible.`

### 查询已有 wiki

`Use $llm-wiki against this project. Read BUSINESS_CONTEXT.md first, state the query type and retrieval path, then answer with supporting wiki pages and unresolved points. If the question is business-only, do not include detailed code evidence unless necessary.`

### 质量审查

`Use $llm-wiki to audit this wiki project. Check entry usability, semantic consistency, retrieval usefulness, layered-page quality, and concept/entity conflicts. Put findings first with file paths and a final usability verdict.`

### 需求 + 代码联合 wiki

`Use $llm-wiki to build a joint business-and-code LLM Wiki. Read BUSINESS_CONTEXT.md first, treat raw/ as immutable business evidence, treat raw-code/* as separate codebases, use graphify when available for code graph extraction, then create wiki/code/codebases and wiki/code/capabilities pages that link code facts back to concepts, entities, and source documents.`

### 代码实现查询

`Use $llm-wiki against this project. Read BUSINESS_CONTEXT.md first, then answer this implementation question by checking wiki/code/codebases, wiki/code/capabilities, concepts/entities, and source documents. Clearly separate requirement evidence, code evidence, inference, and missing evidence.`
