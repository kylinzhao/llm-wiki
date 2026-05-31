# LLM Wiki Skill

## 1. 这是什么

`llm-wiki` 是一个全局可调用的 Codex skill，用来处理一套文件型 LLM Wiki 的完整生命周期：

- 0-1 初始化
- 确定性构建
- AI-native 精修
- 增量维护
- 查询问答
- 质量审查
- 需求评审
- 需求文档与多源码仓库的联合知识层构建

它面向的不是“只会查”的场景，而是“把一个项目从原始文档变成可用知识库”的全链路工作。
对于已经建好的 wiki，查询也统一通过 `llm-wiki` 完成，不再维护单独的 query-only skill。

## 版本

- `version`: `1.0.3`
- `engine_version`: `engine-v1.0.3`

### Engine 发行记录

- **`engine-v1.0.3`**：发布 shared update checkpoint 语义、Cwiki smoke 限流、raw path/image 下载保护，并合入 Confluence source path metadata。
- **`engine-v1.0.2`**：新增发布版本脚本与 GitLab 发布规则，要求每次发布前同步升级 VERSION、manifest 和 README 发行记录。
- **`engine-v1.0.1`**：修复项目模板 health/graph 对 Markdown 代码片段中 `[[...]]` 路径的误判，修复 `tools/health.py` 普通 CLI 输出统计变量错误，并避免已有本机 SSO 自动鉴权时误打印 Cwiki 缺鉴权提示。
- **`engine-v1.0.0`**：冻结 `kb.manifest.yaml` 字段、`config/rss-feeds.yaml` 形状、`tools/rss_sync.py` 抓取与限速语义，以及 `tools/update_wiki.py` 优先的确定性更新链。

## 2. 适用场景

### 快速命令

例如：

- `用 $llm-wiki fast 从 raw/ 和 BUSINESS_CONTEXT.md 初始化新项目，一次性跑完标准首轮。`
- `用 $llm-wiki doctor 看看整个站点健康度、缺口和下一步建议。`
- `用 $llm-wiki update 响应这次文档和代码变更，只更新受影响页面；如果项目已配置 RSS/feed 或接入了 raw-code codebase，就先默认刷新它们；结束前自动检查收口。`
- `用 $llm-wiki-backfill 补齐老知识库的历史 draw.io、Jira/Cjira、source metadata 等证据，并继续精修吸收。`
- `用 $llm-wiki-maintain-all 发现并维护本机已注册的多个 KB，先 dry-run 再确认 apply。`
- `用 $llm-wiki update-skill 更新本机安装的 llm-wiki skill bundle。`
- `用 $llm-wiki review-requirement 帮我 review 这个 Cwiki 需求，并输出评论稿。`
- `用 $llm-wiki update 补某个业务能力的需求到代码追踪矩阵。`

### 可发现的二级 skill

本 bundle 还提供了一组 `$llm-wiki-*` 短入口。它们等价于主入口的二级命令，用来减少提示词长度、提高 Codex skill 列表里的可发现性。

| 二级 skill | 等价命令 | 适合什么时候用 |
| --- | --- | --- |
| `$llm-wiki-fast` | `llm-wiki fast` | 新项目标准首轮，一口气完成构建、精修、验证和收口。 |
| `$llm-wiki-init` | `llm-wiki init` | 新项目分阶段初始化。 |
| `$llm-wiki-doctor` | `llm-wiki doctor` | 只读诊断项目健康度、质量问题、缺口和下一步；集合原 audit 能力。 |
| `$llm-wiki-update` | `llm-wiki update` | 输入、wiki 或源码变化后的影响范围更新；也负责续跑、精修、代码 wiki、traceability 和收口检查；会自动维护 `AGENTS.md` 查询路由规则。 |
| `$llm-wiki-backfill` | `llm-wiki backfill` | 存量 KB 历史证据补全；重新扫描历史 raw/wiki/staging，补齐新版确定性派生能力，并继续进入 source/G+ 精修吸收。 |
| `$llm-wiki-maintain-all` | `llm-wiki maintain-all` | 维护本机已注册 KB registry；默认 dry-run，可发现、列出、清理 missing 项，并在确认后批量执行完整 backfill/update 维护。 |
| `$llm-wiki-update-skill` | `llm-wiki update-skill` | 显式更新本机安装的 llm-wiki skill bundle；不更新当前 KB 内容。 |
| `$llm-wiki-add-wiki` | `llm-wiki add-wiki` | 接入新的文档/wiki 来源到 `raw/`。 |
| `$llm-wiki-add-code` | `llm-wiki add-code` | 接入新的源码库到 `raw-code/`，并构建代码 wiki、能力页和必要 traceability。 |
| `$llm-wiki-query` | `llm-wiki query` | 按意图回答业务或实现问题；业务知识默认不展开大量代码证据。 |
| `$llm-wiki-query-plus` | `llm-wiki query-plus` | 同时回答业务/需求口径与代码实现证据，适合需要更详尽联动分析的问题。 |
| `$llm-wiki-image` | `llm-wiki image` | 补充高价值图片证据。 |
| `$llm-wiki-review-requirement` | 兼容入口 | 兼容旧调用；实际转向 `$requirement-review`。 |

`llm-wiki maintain-all` 使用本机 `~/.llm-wiki/projects.json` registry。常用操作包括 `--discover <dir>` 补录历史 KB、`--list` 查看、`--prune-missing` 清理不存在路径，以及用户确认后的 `--apply` 批量执行完整 backfill/update 维护；默认不加 `--apply` 时只输出 dry-run 计划。

这些 wrapper 只负责路由。完整规则仍以 `SKILL.md` 和 [commands.md](./references/commands.md) 为准。

### A. 新项目 0-1

例如：

- `我现在 raw 和 BUSINESS_CONTEXT 都准备好了，怎么开始构建项目？`
- `帮我从 0-1 初始化一套 LLM Wiki 仓库`

### B. 增量维护

例如：

- `新加了一批 raw，帮我增量更新 wiki`
- `我更新了业务说明文档，帮我看看要不要重建`
- `继续上次没做完的 wiki 精修，不要重建已经完成的内容`

### C. 业务问答

例如：

- `车商直联目前有什么问题？`
- `新能源专区最近几轮方案和复盘主线是什么？`

### D. 质量审查

例如：

- `不要生成内容，纯检查这套 wiki 是否真的可用`
- `检查 concepts / entities 有没有冲突`

### E. 需求评审

例如：

- `帮我 review 这个 PRD 是否能进入开发`
- `这个 Cwiki 需求有没有遗漏前端交互、异常状态和埋点`
- `结合历史需求、代码能力、图片和 zip 原型，找出阻塞开发的问题`

### F. 需求 + 代码联合 wiki

例如：

- `raw-code 里有前端和后端代码，帮我把代码 wiki 也建设出来`
- `把需求文档、前端页面、后端接口和服务实现打通`
- `以后问业务逻辑时，同时参考需求文档和代码实现`

## 3. 项目原理

这套架构不是传统 wiki，也不是纯向量库，而是多层组合：

1. `raw/` 原始证据层
2. `BUSINESS_CONTEXT.md` 业务语义基线
3. `wiki/sources/` 主知识层
4. `wiki/proposals/evidence/reference/operations/conflicts/truth` 分层投影视图
5. `wiki/concepts/`、`wiki/entities/`、`graph/` 索引与图谱层
6. 可选的 `raw-code/` 源码证据层
7. 可选的 `wiki/code/` 代码事实层与跨需求-代码能力索引

因此它的核心思路是：

- 先把结构搭起来
- 在首轮里把全量语义写清楚
- 如果存在源码库，把代码事实和业务语义打通
- 最后让 agent 能按协议查询

这里有一个硬约束：

- 0-1 初始化不应只完成确定性骨架
- 首轮构建必须包含全量语料的大模型 summary 和 AI-native 精修
- 可以分层做，但默认应在同一轮里一口气完成首轮 corpus build

## 4. 为什么构建和查询必须放在一起

如果把“构建 skill”和“查询 skill”完全拆开，会出现两个问题：

- 查询时不知道这套库是怎么生成的，容易误判页面可信度
- 构建时没有查询协议，后续新窗口不知道该如何使用成果

所以统一 skill 的原则是：

- 构建协议和查询协议放在一起
- `BUSINESS_CONTEXT.md` 同时约束生成和查询
- 同一套目录语义同时服务 build 和 query

## 5. 执行效率原则

大型 wiki 构建不是单线程手工整理任务。只要工作范围可以独立切分，就应该用 subagent 并发推进。

适合并发的任务：

- 多个 `raw/` source 批次
- 多个 `raw-code/*` codebase
- 前端 routes/pages/services 与后端 controllers/services/jobs
- 多个 `wiki/code/capabilities/*` 能力页
- graphify 分 codebase 分析
- health 审查、断链检查、证据缺口检查

简单任务可以合并给同一个 subagent：

- 一组相近 source 页的摘要
- 一个 codebase 内多个小组件页
- 一批 endpoint 到 controller 的映射
- 一批 wikilink / backlink 检查

并发边界：

- 每个 subagent 必须有明确、互不重叠的输出范围
- 不要让多个 subagent 写同一文件
- 主 agent 负责全局命名、跨层链接、最终整合和质量口径
- 如果当前环境不能使用 subagent，应改用批次化串行推进，并说明限制

子任务交接模板见 [subagent-handoff.md](./references/subagent-handoff.md)。

## 6. 关键输入

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

### `raw-code/`

可选源码证据目录。`raw-code/*` 的每个一级目录是一个独立 `codebase_id`。

代码证据不应混入 `raw/`。它应该进入 `wiki/code/codebases/<codebase_id>/`，再通过 `wiki/code/capabilities/` 与业务概念、实体和需求来源页相连。

当项目需要代码图谱时，默认优先使用 `graphify` 作为代码结构增强层：

- 对源码做 AST、imports、调用关系和结构报告抽取
- 输出到 `staging/code-graph/<codebase_id>/graphify-out/`
- 由 `llm-wiki` 将图谱结果转成可审计 Markdown

如果 `raw-code/<codebase_id>/docs/wiki` 存在且签名完整，优先把它当作上游代码导航层：解析 topic、concept、source-map，再结合 `scan_code.py` 的 endpoint、route、symbol 生成候选。此时 `graphify` 默认按需运行；只有结构证据缺失、结构性变更、graphify 输出过期或查询明确需要调用/依赖关系时才运行。

`graphify` 不替代 `llm-wiki` 的业务语义协议，也不替代由 wikilink 生成的项目 `graph/`。`docs/wiki` 与 graphify 都不能单独证明 `strong` traceability；强证据仍需要需求锚点和直接源码锚点。

## 7. 文档结构

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

按主题聚合的通用扩展层，用于从用户问题扩展到相关来源、规则、方案、风险和证据。它是导航和归一化入口，不是最终证据层。

### `wiki/entities/`

按实体聚合的通用扩展层，用于统一业务对象、角色、系统、页面、状态、历史别名和冲突叫法。它帮助回到 `wiki/sources/` 找证据，不替代来源证据。

### `wiki/code/`

可选代码知识层。

- `wiki/code/index.md`：代码 wiki 总入口
- `wiki/code/codebases/<codebase_id>/`：单源码库事实页
- `wiki/code/capabilities/`：跨需求文档、前端、后端、异步任务和技术设计的业务能力实现链路
- `wiki/code/traceability/`：需求点到页面、URI、Controller/Dubbo、Service、配置、表、消息和任务的追踪矩阵

常见 codebase 子层：

- 前端：`routes/`、`pages/`、`services/`、`components/`
- 后端：`api-contracts/`、`controllers/`、`dubbo-services/`、`domain-services/`、`managers/`、`data-access/`、`async/`、`jobs/`、`ops-tools/`、`openspec/`

### `graph/`

由 wikilink 抽取生成的关系图谱。

### `staging/`

构建中间产物与辅助材料。

## 8. 0-1 构建顺序

从一个全新项目开始，推荐顺序是：

1. 准备 `raw/`
2. 准备有效的 `BUSINESS_CONTEXT.md`。这是硬性前置；模板 TODO 占位文件不算有效输入。
3. 初始化 `wiki/graph/staging/docs/tools`
4. 运行确定性构建
5. 对全量语料完成首轮大模型 summary 和 AI-native 文本精修
6. 如果存在 `raw-code/`，构建代码 wiki 与跨需求-代码能力索引
7. 做健康检查
8. 重建 graph

注意：

- 第 5 步不是“后续有空再补”的增强项，而是 0-1 构建完成的必要条件
- 允许按层推进，例如先 `sources`，再 `proposals/evidence/reference/operations/conflicts/truth`，最后 `concepts/entities`
- 但不建议只生成 `wiki/sources` 或只生成骨架后就宣布首轮完成

已有项目默认从当前状态续跑。先读 `staging/refinement-status.md`、`staging/health/latest.json`、`graph/summary.md` 和 `wiki/overview.md`，再判断最后一个未完成阶段。

推荐阶段模型：

1. A 输入与状态检查
2. B 骨架初始化
3. C 确定性构建
4. D health 初检
5. E AI-native source 全量精修
6. F 代码 wiki / 联合知识层
7. G graph 构建与首轮验收
8. G+ 综合层二次校准、查询验收、质量审查
9. H 选择性高价值图片证据补充
10. I 发布 / 提交 / 远端同步
11. M 后续增量维护

标准命令（`$LLM_WIKI_SKILL_ROOT` 为 llm-wiki skill 包根目录，见主 `SKILL.md`「Skill 包路径」）：

```text
python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"
uv run python tools/build_wiki.py
uv run python tools/scan_code.py
uv run python tools/build_traceability.py
uv run python tools/health.py --json
uv run python tools/build_graph.py
uv run python tools/anchor_check.py
```

已构建的老 KB 只要通过新版 `$llm-wiki update` 进入维护流程，agent 应先刷新 engine-owned 项目工具并合并 agent 查询路由规则；此后每次新版 `tools/update_wiki.py` 都会自动检查。若只想补 `AGENTS.md`，不要使用 `--force` 覆盖模板文件；在 KB 根目录运行：

```text
python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --agent-rules-only
```

该命令会把当前模板中的 `## Query Routing` 合并进 `AGENTS.md`，保留原有规则，且重复执行不会重复插入。

更新本机安装的 skill bundle 时，使用显式 skill 维护命令，避免和普通 KB 内容更新混在一起：

```text
python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --client auto --backup
```

更新来源优先使用本地 `llm-wiki-skill` bundle checkout 的 git upstream。若无法从安装目录、环境变量或当前工作目录推断本地 checkout，updater 会从公司 GitLab 默认地址 `https://git.guazi-corp.com/c2b-fe/llm-wiki.git` 下载到 `~/.cache/llm-wiki-skill/llm-wiki`，再从该 cache 安装。可用 `--git-url` / `LLM_WIKI_SKILL_GIT_URL` 覆盖下载地址，用 `--cache-dir` / `LLM_WIKI_SKILL_CACHE_DIR` 覆盖 cache 目录；GitHub remote 只作为额外远端，除非显式指定，不默认使用。若下载私有 GitLab 仓库时缺少凭据，Personal Access Token 创建地址是 `https://git.guazi-corp.com/profile/personal_access_tokens`，所需 scope 为 `read_repository`。

如果要强制使用指定的本地 bundle 仓库路径：

```text
python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --source /path/to/llm-wiki-skill --client auto --backup
```

这些步骤分别负责：

- `install_project_template.py`：把完整项目脚手架复制到目标 wiki 项目
- `build_wiki.py`：搭 wiki 骨架
- `scan_code.py`：扫描 `raw-code/*` 并生成代码事实入口
- `build_traceability.py`：生成需求到代码追踪矩阵种子，记录代码扫描锚点候选，合并 trace worker proposals 到 `staging/traceability/state.json`，并渲染 `wiki/code/traceability/`
- `health.py`：检查结构是否健康
- `build_graph.py`：把 wikilink 连成图谱
- `anchor_check.py`：检查 traceability 中的代码锚点是否存在

## 语言要求

使用 `llm-wiki` 及其相关短入口时，面向用户的回答、诊断、审查报告和最终总结默认使用中文；由 agent 生成或改写的 `wiki/`、`docs/`、`staging/` Markdown 知识文档也默认使用中文。代码标识符、命令、路径、API 名称、配置键、英文专有名词和原始证据引用可保留原文，并用中文解释。

如果 `raw-code/` 存在且需要代码图谱增强，可运行：

```text
uv run python tools/graphify_code.py --all
```

依赖约定：

- 必需：Python 3.10+、`uv`
- 可选：`graphify`，用于代码图谱提取，输出归档到 `staging/code-graph/<codebase_id>/graphify-out/`；当上游 `docs/wiki` 和 scan anchors 已足够时可正常跳过
- 本地脚本不得调用模型 SDK；语义 summary、实体归一和能力判断可由 Codex / subagent 辅助。traceability 的模型步骤必须走 `docs/traceability-contract.md`：当前 agent 或外部 agent worker 输出 `staging/traceability/runs/<run_id>/proposals.json`，确定性工具合并到 `staging/traceability/state.json` 并渲染 Markdown。

代码 wiki 的构建可以是 AI-native 编排任务，不要求一开始就写入仓库脚本。执行时先识别 codebase，再按上游 `docs/wiki` 适配、确定性扫描、候选生成、必要时 graphify、Markdown 精修、跨层链接的顺序推进。

## 9. 查询逻辑

默认查询顺序是：

1. 读取 `BUSINESS_CONTEXT.md`
2. 判断查询意图
3. 先查 `wiki/overview.md`
4. 按查询意图进入专项目录层
5. 用 `concepts / entities` 做通用扩展和归一
6. 回到 `sources` 找直接需求/业务证据
7. 必要时回 `raw/`
8. 只有实现、架构、接口、调用链、落地状态、测试追踪或 `query-plus` 问题才进入 `wiki/code/`
9. 输出结论、证据、推断和未决点

问题类型与专项目录层：

- 问题/风险：`conflicts -> evidence -> proposals -> sources`
- 证据/效果：`evidence -> sources`
- 方案/规划：`proposals -> sources`
- 接口/规则：`reference -> truth -> sources`
- 当前状态：`truth -> reference -> sources`
- 操作执行：`operations -> sources`

`concepts / entities` 是通用扩展层，不是和 `evidence / operations / proposals / reference / truth / conflicts` 互斥的同类目录。先按意图选择专项目录层，再用 `concepts / entities` 扩展主题、实体和别名，最终回到 `sources` 或 `raw/` 核验证据。

如果问题涉及代码实现，追加代码检索路径：

- 业务实现状态：`BUSINESS_CONTEXT.md -> concepts/entities -> sources -> code/traceability -> code/capabilities -> code/codebases`
- 代码问题：`code/traceability -> code/capabilities -> code/codebases -> concepts/entities -> sources`

回答必须区分：

- 需求文档证明的业务规则
- 代码实现证明的页面、接口、服务、状态机、异步任务或数据访问
- 基于命名/调用关系的推断
- 仍缺失的证据

## 10. 图片策略

当前默认是：

- 文本优先
- 不主动做图片多模态识别
- 只有用户明确要求，或文本明显不足以回答时，才把图片纳入主链路

所以这套 skill 的默认行为是：

- 先用文本 wiki 回答
- 不默认启动图片分析
- 但会盘点 `raw/` 图片资产；如果文本层或查询验收已完成而图片证据未处理，会在 `doctor`、`update` 或初始化收尾里明确提示阶段 H

文本层完成后，可以进入阶段 H：选择性高价值图片证据补充。图片识别必须结合 `raw/**/index.md` 中图片前后文，输出到 `staging/image-notes/`，低价值页面走查和重复 UI 截图默认跳过。详见 [image-evidence.md](./references/image-evidence.md)。

如果核心页面依赖流程图、状态截图、数据表、验收图、账户/费用/保证金/风控/权限类图片，项目只能称为“文本层健康”；仍应把 `llm-wiki image` 作为高价值证据补强的建议下一步。

例外：`llm-wiki review-requirement` 进行需求评审时，图片、截图、图表和 zip 原型都属于需求证据；必须分析图片内容，并把 zip 优先当作 HTML 原型检查。

## 11. 推荐用法

### 中文短入口

```text
用 $llm-wiki fast 从 raw/ 和 BUSINESS_CONTEXT.md 初始化新项目，并按标准顺序一次性完成首轮构建、精修、代码 wiki、验收、health 和 graph。
```

```text
用 $llm-wiki doctor 诊断整个 LLM Wiki 站点状态，告诉我哪里健康、哪里缺口最大、下一步建议怎么做。
```

```text
用 $llm-wiki update 响应这次文档或代码变更。先判断影响范围；如果项目已配置 raw 或接入了 raw-code codebase，就先默认刷新它们，再只更新受影响的 source、concept/entity、code/capability/traceability 页面，最后跑 health 和 graph。
```

```text
用 $llm-wiki trace 补电话直连链路的需求到代码追踪矩阵，标注 strong/partial/inferred/external/missing 并补关键代码锚点。
```

```text
用 $llm-wiki 继续维护这个项目。先读 BUSINESS_CONTEXT.md 和当前状态，从未完成阶段续跑，不要重建已完成内容。
```

```text
用 $llm-wiki 构建需求+代码联合 wiki。raw 是需求证据，raw-code 是代码证据，按现有协议并发推进并输出验收结果。
```

```text
用 $llm-wiki 查询这个问题。先读 BUSINESS_CONTEXT.md，说明查询类型、检索路径、结论、支撑页面和未决点。
```

### 新项目 0-1

```text
Use $llm-wiki to bootstrap a new LLM Wiki project from raw/ and BUSINESS_CONTEXT.md. Explain the phases first, initialize the structure, run deterministic build steps, then complete the first-round full-corpus summary and AI-native refinement in the same run if feasible. Layered execution is allowed, but do not stop after only generating the skeleton.
```

### 已有项目查询

```text
Use $llm-wiki against this project. Read BUSINESS_CONTEXT.md first, state the query type and retrieval path, then answer with supporting wiki pages and unresolved points. If the question is business-only, do not include detailed code evidence unless necessary.
```

### 质量审查

```text
Use $llm-wiki doctor to review this wiki project. Check entry usability, semantic consistency, retrieval usefulness, layered-page quality, and concept/entity conflicts. Put findings first with file paths and a final usability verdict.
```

### 需求 + 代码联合 wiki

```text
Use $llm-wiki to build a joint business-and-code LLM Wiki. Read BUSINESS_CONTEXT.md first, treat raw/ as immutable business evidence, treat raw-code/* as separate codebases, use graphify when available for code graph extraction, then create wiki/code/codebases and wiki/code/capabilities pages that link code facts back to concepts, entities, and source documents.
```

## 12. 参考文件

skill 核心文件：

- [SKILL.md](./SKILL.md)
- [agents/openai.yaml](./agents/openai.yaml)

参考材料：

- [bootstrapping.md](./references/bootstrapping.md)
- [build-and-maintenance.md](./references/build-and-maintenance.md)
- [commands.md](./references/commands.md)
- [project-principles.md](./references/project-principles.md)
- [wiki-structure.md](./references/wiki-structure.md)
- [architecture-and-retrieval.md](./references/architecture-and-retrieval.md)
- [query-logic.md](./references/query-logic.md)
- [code-wiki.md](./references/code-wiki.md)
- [subagent-handoff.md](./references/subagent-handoff.md)
- [image-evidence.md](./references/image-evidence.md)
