# LLM Wiki Skill Bundle

这是 LLM Wiki 的 skill bundle。它把 `llm-wiki` 主 skill、常用二级 skill wrapper、需求评审 skill、项目模板脚本和维护文档打包在一起，便于安装到 Codex / Claude Code / Cursor 的技能目录，也便于统一维护和发布。

项目仓库（对外分发时请改为受众可克隆的地址）：

```text
https://git.guazi-corp.com/c2b-fe/llm-wiki
```

## 前置条件

- **Python** 3.10+（与项目模板 `pyproject.toml` 一致）
- **`uv`**：模板与文档中的构建命令统一为 `uv run python ...`（见 `skills/llm-wiki/assets/project-template/docs/tooling-dependencies.md`）
- **Unix 环境**：`install.sh` 为 Bash 脚本；Windows 请手动将 `skills/` 下各目录复制到对应 skills 安装路径，或使用 WSL/Git Bash。
- `install.sh` 支持 `--client codex|claude|cursor|all|auto`：
  - `codex` -> `${CODEX_HOME:-$HOME/.codex}/skills`
  - `claude` -> `${CLAUDE_HOME:-$HOME/.claude}/skills`
  - `cursor` -> `${CURSOR_HOME:-$HOME/.cursor}/skills`
  - `auto`（默认）会按当前机器上已存在的客户端目录自动选择目标；`all` 强制安装到三者。
- **可选**：`graphify`（仅当需要代码图谱增强时）。**可选**：`local-port-registry` skill——仅在 `requirement-review` 流程里要起本地预览服且担心端口冲突时使用；本 bundle 未内置该 skill。

## 这是什么

`llm-wiki` 是一个全局可调用的 Codex skill，用来处理一套文件型 LLM Wiki 的完整生命周期：

- 0-1 初始化
- 确定性构建
- AI-native 精修
- 增量维护
- 查询问答
- 质量审查
- 需求评审
- 需求文档与多源码仓库的联合知识层构建

它面向的不是“只会查”的场景，而是“把一个项目从原始文档变成可用知识库”的全链路工作。对于已经建好的 wiki，查询也统一通过 `llm-wiki` 完成。

## 项目原理

LLM Wiki 不是传统 wiki，也不是纯向量库，而是多层证据结构：

1. `raw/` 原始证据层
2. `BUSINESS_CONTEXT.md` 业务语义基线
3. `wiki/sources/` 主知识层
4. `wiki/proposals/evidence/reference/operations/conflicts/truth` 分层投影视图
5. `wiki/concepts/`、`wiki/entities/`、`graph/` 索引与图谱层
6. 可选的 `raw-code/` 源码证据层
7. 可选的 `wiki/code/` 代码事实层与跨需求-代码能力索引

核心思路是：

- 先把目录和确定性索引搭起来
- 在首轮里把全量语义写清楚
- 如果存在源码库，把代码事实和业务语义打通
- 最后让 agent 能按协议查询、审查和增量维护

0-1 初始化不应只完成确定性骨架。首轮构建必须包含全量语料的大模型 summary 和 AI-native 精修，可以分层推进，但默认应在同一轮里完成首轮 corpus build。

## Engine 发行（`engine-v*`）

- **`engine-v0.1.0`**：冻结 `kb.manifest.yaml` 字段、`config/rss-feeds.yaml` 形状、`tools/rss_sync.py` 抓取与限速语义，以及 **`tools/update_wiki.py`** 优先的确定性更新链。详见仓库根目录 **`INSTRUCTION_AND_RELEASE_PLAN.md`**。对外 Git tag：`engine-v0.1.0`（在 `llm-wiki-skill` 仓库创建）。

## Bundle 内容

| 路径 | 说明 |
| --- | --- |
| `skills/llm-wiki/` | 主 skill，包含完整生命周期协议、二级命令路由、references、项目模板脚本和 agent handoff 规则。 |
| `skills/llm-wiki-*/` | 常用命令的短入口 wrapper，便于在 Codex skill 列表里直接发现和调用。 |
| `skills/requirement-review/` | 独立需求评审 skill，可脱离 `llm-wiki` 使用。 |
| `install.sh` | 把本 bundle 安装到 Codex / Claude Code / Cursor 的 skills 目录（可用 `--client` 选择目标）。 |
| `tests/` | 安装脚本和 bundle 结构测试。 |
| `INSTRUCTION_AND_RELEASE_PLAN.md` | 指令拆分、update 收口和发布方案说明。 |
| `FE_REQ_REVIEW_SKILL.md` | 前端需求评审能力设计说明。 |
| `REQUIREMENT_REVIEW_FEATURE_PROPOSAL.md` | 独立需求评审 skill 的功能方案。 |

## 安装

首次在本机安装 bundle（默认 `--client auto`；目标目录下尚无同名 skill 时，可省略 `--backup`）：

```bash
./install.sh --copy --backup
# 或显式指定客户端
./install.sh --copy --backup --client codex
./install.sh --copy --backup --client claude
./install.sh --copy --backup --client cursor
```

安装完成后，在**空的 wiki 项目目录**中初始化脚手架（会创建 `raw/` 与工具脚本；随后请补全 `BUSINESS_CONTEXT.md` 与 `raw/` 证据）：

```bash
cd /path/to/your-wiki-repo
# 以 codex 为例；claude/cursor 请把前缀改为对应 skills 目录
python3 "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"
uv run python tools/update_wiki.py
```

按客户端可直接复制的初始化命令：

```bash
# Codex
python3 "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"

# Claude Code
python3 "${CLAUDE_HOME:-$HOME/.claude}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"

# Cursor
python3 "${CURSOR_HOME:-$HOME/.cursor}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"
```

软链安装，适合继续开发这个 bundle：

```bash
./install.sh --link --backup
```

安装脚本默认不会覆盖已有 skill。遇到同名目录时会停止并提示：

- 先预览：`./install.sh --copy --dry-run`
- 保留旧版本并安装：`./install.sh --copy --backup`
- 明确丢弃旧版本并覆盖：`./install.sh --copy --force`

默认安装目录是：

```text
codex  -> ${CODEX_HOME:-$HOME/.codex}/skills
claude -> ${CLAUDE_HOME:-$HOME/.claude}/skills
cursor -> ${CURSOR_HOME:-$HOME/.cursor}/skills
```

## 主入口

`$llm-wiki` 是主入口，适合完整生命周期任务和不确定应该走哪个命令的场景。

典型用法：

- `用 $llm-wiki fast 从 raw/ 和 BUSINESS_CONTEXT.md 初始化新项目，一次性跑完标准首轮。`
- `用 $llm-wiki doctor 看看整个站点健康度、缺口和下一步建议。`
- `用 $llm-wiki update 响应这次文档和代码变更，只更新受影响页面。`
- `用 $llm-wiki review-requirement 帮我 review 这个 Cwiki 需求，并输出评论稿。`
- `用 $llm-wiki trace 补某个业务能力的需求到代码追踪矩阵。`

## 二级 Skill

这些 `$llm-wiki-*` 是二级 skill，也就是常用命令的短入口 wrapper。它们让 Codex skill 列表里能直接发现具体能力，但不复制一套规则；真正的执行协议仍来自 `skills/llm-wiki/SKILL.md` 和 `skills/llm-wiki/references/commands.md`。

| 二级 skill | 等价命令 | 适用场景 |
| --- | --- | --- |
| `$llm-wiki-fast` | `llm-wiki fast` | 从 `raw/` 和 `BUSINESS_CONTEXT.md` 一口气完成标准首轮构建、精修、可选代码 wiki、health 和 graph 收口。 |
| `$llm-wiki-init` | `llm-wiki init` | 分阶段初始化新 LLM Wiki 项目，适合需要边构建边汇报的 0-1 场景。 |
| `$llm-wiki-resume` | `llm-wiki resume` | 上次构建、精修、代码 wiki、追踪矩阵、图片、健康检查或图谱任务中断后，从状态文件续跑。 |
| `$llm-wiki-doctor` | `llm-wiki doctor` | 只读诊断 wiki 健康度、缺口、过期页面、下一步动作。 |
| `$llm-wiki-update` | `llm-wiki update` | `raw/`、`BUSINESS_CONTEXT.md`、`raw-code/`、wiki 页面或源码变化后的影响范围更新。 |
| `$llm-wiki-add-wiki` | `llm-wiki add-wiki` | 把另一个文档库、wiki 导出、Markdown 目录、Confluence 导出、文档目录或 wiki URL 加入 `raw/` 原始证据层。 |
| `$llm-wiki-add-code` | `llm-wiki add-code` | 把另一个本地项目、仓库或源码目录加入 `raw-code/<codebase_id>/` 代码证据层，并构建对应代码 wiki 页面。 |
| `$llm-wiki-refine` | `llm-wiki refine` | 精修来源页、概念页、实体页、分层页面、冲突页或 AI-native 文案，同时保留证据链和确定性构建块。 |
| `$llm-wiki-build-code` | `llm-wiki build-code` | 扫描或刷新 `raw-code/*`，生成 `wiki/code/codebases`、`wiki/code/capabilities`、接口映射、graphify 记录和代码证据页。 |
| `$llm-wiki-code-trace` | `llm-wiki code-trace` | 构建需求到代码追踪矩阵，映射前端页面、URI、Controller/Dubbo/Service 方法、配置、表、消息、任务和证据强度。 |
| `$llm-wiki-query` | `llm-wiki query` | 按检索协议回答业务、产品、需求、实现或代码问题，并给出结论、支撑页面、未决点和证据类型。 |
| `$llm-wiki-audit` | `llm-wiki audit` | 以 findings-first 方式审查 wiki 可用性、语义一致性、来源页覆盖、实体冲突、证据强度、追踪矩阵、过期页面和图谱质量。 |
| `$llm-wiki-image` | `llm-wiki image` | 文本层完成后补充高价值图片、截图、图表或附件证据；默认不批量分析低价值截图。 |
| `$llm-wiki-ship` | `llm-wiki ship` | 发布收口：运行 health、graph、可选 anchor check，并在 remote 和意图明确时提交、推送或发布。 |
| `$llm-wiki-review-requirement` | 兼容入口 | 兼容旧的 `llm-wiki review-requirement` 调用；实际转向 `$requirement-review` 做 evidence-first 需求评审。 |

## 独立需求评审 Skill

`$requirement-review` 是独立 skill，可脱离 `$llm-wiki` 使用。它用于评审 PRD、Cwiki 页面、Markdown 需求、图片、zip/HTML 原型和前端交互说明。

当当前项目本身是 LLM Wiki 项目时，`$requirement-review` 可以把 `BUSINESS_CONTEXT.md`、`raw/`、`wiki/`、`raw-code/`、`wiki/code/` 作为证据层；但它不再依赖 `$llm-wiki` 主 skill 的命令协议。

## 适用场景

### 新项目 0-1

- `我现在 raw 和 BUSINESS_CONTEXT 都准备好了，怎么开始构建项目？`
- `帮我从 0-1 初始化一套 LLM Wiki 仓库`

### 增量维护

- `新加了一批 raw，帮我增量更新 wiki`
- `我更新了业务说明文档，帮我看看要不要重建`
- `继续上次没做完的 wiki 精修，不要重建已经完成的内容`

### 业务问答

- `车商直联目前有什么问题？`
- `新能源专区最近几轮方案和复盘主线是什么？`

### 质量审查

- `不要生成内容，纯检查这套 wiki 是否真的可用`
- `检查 concepts / entities 有没有冲突`

### 需求评审

- `帮我 review 这个 PRD 是否能进入开发`
- `这个 Cwiki 需求有没有遗漏前端交互、异常状态和埋点`
- `结合历史需求、代码能力、图片和 zip 原型，找出阻塞开发的问题`

### 需求 + 代码联合 wiki

- `raw-code 里有前端和后端代码，帮我把代码 wiki 也建设出来`
- `把需求文档、前端页面、后端接口和服务实现打通`
- `以后问业务逻辑时，同时参考需求文档和代码实现`

## LLM Wiki 项目结构

生成出来的 wiki 项目通常包含：

| 路径 | 说明 |
| --- | --- |
| `raw/` | 原始文档目录，不可变输入。 |
| `BUSINESS_CONTEXT.md` | 业务语义基线，存放实体定义、同义词归并、角色边界和容易误判的概念。 |
| `wiki/sources/` | 主知识页，一篇 raw 对应一篇主 digest。 |
| `wiki/proposals/` | 方案、规划、设计、需求、草案。 |
| `wiki/evidence/` | 实验、复盘、分析、归因、数据结论。 |
| `wiki/reference/` | 接口、字段、规则、参数、手册、字典。 |
| `wiki/operations/` | SOP、活动执行、流程落地、运营动作。 |
| `wiki/conflicts/` | 问题、风险、争议、未决项、冲突。 |
| `wiki/truth/` | 当前事实、稳定状态、明确说明。 |
| `wiki/concepts/` | 按主题聚合的索引层。 |
| `wiki/entities/` | 按实体聚合的索引层。 |
| `raw-code/` | 可选源码证据层，每个一级目录是一个 `codebase_id`。 |
| `wiki/code/` | 可选代码知识层，包含 codebase 事实页、业务能力实现链路和需求到代码追踪矩阵。 |
| `graph/` | 由 wikilink 抽取生成的关系图谱。 |
| `staging/` | 构建中间产物、健康检查、状态文件和辅助材料。 |

`raw/` 需求证据和 `raw-code/` 实现证据必须分层，不应混在一起。代码证据进入 `wiki/code/codebases/<codebase_id>/`，再通过 `wiki/code/capabilities/` 和 `wiki/code/traceability/` 与业务概念、实体和需求来源页相连。

## 构建顺序

从一个全新项目开始，推荐顺序是：

1. 准备 `raw/`
2. 准备 `BUSINESS_CONTEXT.md`
3. 初始化 `wiki/graph/staging/docs/tools`
4. 运行确定性构建
5. 对全量语料完成首轮大模型 summary 和 AI-native 文本精修
6. 如果存在 `raw-code/`，构建代码 wiki 与跨需求-代码能力索引
7. 做健康检查
8. 重建 graph

第 5 步不是“后续有空再补”的增强项，而是 0-1 构建完成的必要条件。

## 执行效率原则

大型 wiki 构建不是单线程手工整理任务。只要工作范围可以独立切分，就应该用 subagent 并发推进。

适合并发的任务：

- 多个 `raw/` source 批次
- 多个 `raw-code/*` codebase
- 前端 routes/pages/services 与后端 controllers/services/jobs
- 多个 `wiki/code/capabilities/*` 能力页
- graphify 分 codebase 分析
- health 审查、断链检查、证据缺口检查

并发边界：

- 每个 subagent 必须有明确、互不重叠的输出范围
- 不要让多个 subagent 写同一文件
- 主 agent 负责全局命名、跨层链接、最终整合和质量口径

## 维护约定

- 修改主协议时，优先更新 `skills/llm-wiki/SKILL.md` 和 `skills/llm-wiki/references/commands.md`。
- 新增常用命令时，增加对应 `skills/llm-wiki-*/SKILL.md` wrapper，并同步更新本 README 的二级 skill 表。
- 修改安装行为时，同步更新 `install.sh`、`tests/` 和安装说明。
- 修改需求评审能力时，同步更新 `skills/requirement-review/` 和兼容入口 `skills/llm-wiki-review-requirement/`。
