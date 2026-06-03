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
- `install.sh` 支持 `--client codex|claude|cursor|qoder|all|auto`：
  - `codex` -> `${CODEX_HOME:-$HOME/.codex}/skills`
  - `claude` -> `${CLAUDE_HOME:-$HOME/.claude}/skills`
  - `cursor` -> `${CURSOR_HOME:-$HOME/.cursor}/skills`
  - `qoder` -> `${QODER_HOME:-$HOME/.qoder}/skills`
  - `auto`（默认）会按当前机器上已存在的客户端目录自动选择目标；`all` 强制安装到三者。
- **可选**：`graphify`（仅当需要代码图谱增强时）。**可选**：`local-port-registry` skill——仅在 `requirement-review` 流程里要起本地预览服且担心端口冲突时使用；本 bundle 未内置该 skill。
- **需求评审依赖**：`prd-review-max`（上游只读，来自 `c2b-fe/pre-code`）。安装本 bundle 后需额外执行 `./scripts/install_prd_review_max.sh`；`$requirement-review` 会在缺失时提示自动安装。

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

## 语言要求

使用 `llm-wiki` 及其相关短入口时，面向用户的回答、诊断、审查报告和最终总结默认使用中文；由 agent 生成或改写的 `wiki/`、`docs/`、`staging/` Markdown 知识文档也默认使用中文。代码标识符、命令、路径、API 名称、配置键、英文专有名词和原始证据引用可保留原文，并用中文解释。

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

- **`engine-v1.0.5`**：补齐 update-skill 与 shared update 的 GitLab token 本机鉴权 fallback，init_auth_env 可选保存 GitLab PAT，并保持优先使用本机 SSH Key / Git credential。
- **`engine-v1.0.4`**：同步 GrapeHub 发布包（SKILL.md + manifest.json），合入 Cwiki exclude-author 下载过滤，以及 update-skill 默认联动升级 prd-review-max。
- **`engine-v1.0.3`**：发布 shared update checkpoint 语义、Cwiki smoke 限流、raw path/image 下载保护，并合入 Confluence source path metadata。
- **`engine-v1.0.2`**：新增发布版本脚本与 GitLab 发布规则，要求每次发布前同步升级 VERSION、manifest 和 README 发行记录。
- **`engine-v1.0.1`**：修复项目模板健康检查与图谱构建对 Markdown 代码片段中 `[[...]]` 路径的误判，避免 Next.js catch-all 路由等代码路径被当作 broken wikilink；修复 `tools/health.py` 普通 CLI 输出的统计变量错误；当已启用本机 SSO 自动鉴权时，Cwiki 同步不再提前打印缺鉴权提示。
- **`engine-v1.0.0`**：冻结 `kb.manifest.yaml` 字段、`config/rss-feeds.yaml` 形状、`tools/rss_sync.py` 抓取与限速语义，以及 **`tools/update_wiki.py`** 优先的确定性更新链。详见仓库根目录 **`INSTRUCTION_AND_RELEASE_PLAN.md`**。对外 Git tag：`engine-v1.0.0`（在 `llm-wiki-skill` 仓库创建）。

发布到 GitLab 前必须先升级版本号并写入发行记录，不允许只提交代码。使用：

```bash
python3 scripts/release_version.py \
  --version <next-patch-version> \
  --engine-version engine-v<next-patch-version> \
  --note "<中文发行说明>"
```

随后提交版本文件、README 和功能变更，推送 `main` 后打并推送同名 `engine-v*` tag。

## Bundle 内容

| 路径 | 说明 |
| --- | --- |
| `skills/llm-wiki/` | 主 skill，包含完整生命周期协议、二级命令路由、references、项目模板脚本和 agent handoff 规则。 |
| `skills/llm-wiki-*/` | 常用命令的短入口 wrapper，便于在 Codex skill 列表里直接发现和调用。 |
| `skills/requirement-review/` | KB 证据桥接 + 调用上游 `prd-review-max` 的需求评审 skill。 |
| `scripts/install_prd_review_max.sh` | 从 `c2b-fe/pre-code` 安装/链接 `prd-review-max`（不修改上游内容）。 |
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
./install.sh --copy --backup --client qoder
```

更新已安装的 bundle 时，可从源码 checkout 运行安装脚本，或使用已安装 skill 内的 updater：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/update_installed_skill.py" --source "$PWD" --client auto --backup
```

更新来源优先由本地 bundle checkout 的 git upstream 决定；若无法推断本地 checkout，updater 会从公司 GitLab 默认地址 `https://git.guazi-corp.com/c2b-fe/llm-wiki.git` 下载到 `~/.cache/llm-wiki-skill/llm-wiki`，再从该 cache 安装。可用 `--git-url` / `LLM_WIKI_SKILL_GIT_URL` 覆盖下载地址，用 `--cache-dir` / `LLM_WIKI_SKILL_CACHE_DIR` 覆盖 cache 目录。仓库里可能还有 GitHub mirror remote，但不作为默认更新源。若下载私有 GitLab 仓库时缺少凭据，Personal Access Token 创建地址是 `https://git.guazi-corp.com/profile/personal_access_tokens`，所需 scope 为 `read_repository`。

如果 skill 是通过 `--link` 从本仓库安装的，也可以省略 `--source`，脚本会尝试从当前 skill 路径推断 bundle checkout 并执行 `git pull --ff-only` 后重新安装。

安装脚本会清理已下线的 llm-wiki wrapper；使用 `--backup` 时旧目录默认会移动到 `~/.llm-wiki-skill-backups/`（可通过 `--backup-dir` 或 `LLM_WIKI_SKILL_BACKUP_DIR` 覆盖），避免被 skills 扫描器误识别为可用 skill。

安装完成后，在**空的 wiki 项目目录**中初始化脚手架（会创建 `raw/` 与工具脚本；随后请补全 `BUSINESS_CONTEXT.md` 与 `raw/` 证据）：

```bash
cd /path/to/your-wiki-repo
# 以 codex 为例；claude/cursor 请把前缀改为对应 skills 目录
python3 "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"
uv run python tools/update_wiki.py
```

当 `config/rss-feeds.yaml` 已配置启用的 feed URL 时，`tools/update_wiki.py` 会默认先执行 RSS 同步，再进入增量更新。代码证据只支持一种接入方式：用 `llm-wiki add-code` 将仓库接成 `raw-code/<codebase_id>/` 下的 engine-managed git checkout。之后同一次 update 会默认先对这些受管 codebase 执行安全的 `git pull --ff-only`，再继续 code wiki 构建；如果仓库权限缺失、checkout 损坏或 worktree 不干净，update 必须明确失败而不是假装已刷新。

代码库如果自带 `raw-code/<codebase_id>/docs/wiki` 且签名完整，update 会把它作为上游代码导航层，优先结合 `scan_code.py` 生成 compact 候选和 traceability proposal。此时 `graphify` 默认是按需结构增强：只有缺少结构证据、graphify 输出过期、发生结构性代码变更，或用户明确需要调用/依赖关系时才运行；跳过 graphify 是正常健康状态，不能自动宣称 `strong` traceability。

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
- 自定义备份目录：`./install.sh --copy --backup --backup-dir "$HOME/.skill-backups"`

默认安装目录是：

```text
codex  -> ${CODEX_HOME:-$HOME/.codex}/skills
claude -> ${CLAUDE_HOME:-$HOME/.claude}/skills
cursor -> ${CURSOR_HOME:-$HOME/.cursor}/skills
qoder  -> ${QODER_HOME:-$HOME/.qoder}/skills
```

## 主入口

`$llm-wiki` 是主入口，适合完整生命周期任务和不确定应该走哪个命令的场景。

典型用法：

- `用 $llm-wiki fast 从 raw/ 和 BUSINESS_CONTEXT.md 初始化新项目，一次性跑完标准首轮。`
- `用 $llm-wiki doctor 看看整个站点健康度、缺口和下一步建议。`
- `用 $llm-wiki update 响应这次文档和代码变更，只更新受影响页面，并完成收口。`
- `用 $llm-wiki-backfill 补齐老知识库的历史 draw.io、Jira/Cjira、source metadata 等证据，并继续精修吸收。`
- `用 $llm-wiki review-requirement 帮我 review 这个 Cwiki 需求，并输出评论稿。`
- `用 $llm-wiki trace 补某个业务能力的需求到代码追踪矩阵。`

## 二级 Skill

这些 `$llm-wiki-*` 是二级 skill，也就是常用命令的短入口 wrapper。它们让 Codex skill 列表里能直接发现具体能力；执行协议来自 `skills/llm-wiki/references/core-rules.md` 与 `skills/llm-wiki/references/commands/`（按命令拆分，索引见 `commands.md`）。子入口**不要**再反向加载完整 `SKILL.md`。

| 二级 skill | 等价命令 | 适用场景 |
| --- | --- | --- |
| `$llm-wiki-fast` | `llm-wiki fast` | 从 `raw/` 和 `BUSINESS_CONTEXT.md` 一口气完成标准首轮构建、精修、可选代码 wiki、health 和 graph 收口。 |
| `$llm-wiki-init` | `llm-wiki init` | 分阶段初始化新 LLM Wiki 项目，适合需要边构建边汇报的 0-1 场景。 |
| `$llm-wiki-doctor` | `llm-wiki doctor` | 只读诊断 wiki 健康度、质量问题、缺口、过期页面和下一步动作；集合原 audit 能力。 |
| `$llm-wiki-update` | `llm-wiki update` | `raw/`、`BUSINESS_CONTEXT.md`、`raw-code/`、wiki 页面或源码变化后的影响范围更新；也负责续跑、精修、代码 wiki、traceability 和收口检查；自动维护 `AGENTS.md` 查询路由规则。 |
| `$llm-wiki-backfill` | `llm-wiki backfill` | 存量 KB 历史证据补全；重新扫描历史 raw/wiki/staging，补齐新版确定性派生能力，并继续进入 source/G+ 精修吸收。 |
| `$llm-wiki-maintain-all` | `llm-wiki maintain-all` | 维护本机已注册 KB registry；默认 dry-run，可发现、列出、清理 missing 项，并在确认后批量执行完整 backfill/update 维护。 |
| `$llm-wiki-update-skill` | `llm-wiki update-skill` | 显式更新本机安装的 llm-wiki skill bundle、模板脚本和命令协议；不更新当前 KB 内容。 |
| `$llm-wiki-add-wiki` | `llm-wiki add-wiki` | 把另一个文档库、wiki 导出、Markdown 目录、Confluence 导出、文档目录或 wiki URL 加入 `raw/` 原始证据层。 |
| `$llm-wiki-add-code` | `llm-wiki add-code` | 把另一个本地仓库接成 `raw-code/<codebase_id>/` 下的 engine-managed git checkout，并构建代码 wiki、能力候选和必要 traceability。若存在 `docs/wiki`，优先作为上游导航；graphify 仅按需增强。缺少仓库权限时必须立即终止。 |
| `$llm-wiki-query` | `llm-wiki query` | 按意图回答业务、产品、需求、实现或代码问题；业务知识默认不展开大量代码证据。 |
| `$llm-wiki-query-plus` | `llm-wiki query-plus` | 同时回答业务/需求口径与代码实现证据，适合需要更详尽联动分析的问题。 |
| `$llm-wiki-image` | `llm-wiki image` | 文本层完成后补充高价值图片、截图、图表或附件证据；默认不批量分析低价值截图。 |
| `$llm-wiki-review-requirement` | 兼容入口 | 兼容旧的 `llm-wiki review-requirement` 调用；转向 `$requirement-review`（KB 证据 + `$prd-review-max`）。 |

`llm-wiki maintain-all` 使用本机 `~/.llm-wiki/projects.json` registry。常用操作包括 `--discover <dir>` 补录历史 KB、`--list` 查看、`--prune-missing` 清理不存在路径，以及用户确认后的 `--apply` 批量执行完整 backfill/update 维护；默认不加 `--apply` 时只输出 dry-run 计划。

## 独立需求评审 Skill

需求评审由两层组成：

1. **`$prd-review-max`**（上游，只读）：PRD/Spec 通用基础检测、业务评审、UX 评审。来源：<https://git.guazi-corp.com/c2b-fe/pre-code/tree/master/prd-review-max>。安装：

   ```bash
   ./scripts/install_prd_review_max.sh --link --client auto
   ```

   **升级**：随 `llm-wiki update-skill` 自动执行（`install_prd_review_max.sh --upgrade`）；也可单独运行：

   ```bash
   ./scripts/install_prd_review_max.sh --upgrade --client auto
   ```

2. **`$requirement-review`**（本 bundle）：在调用 `prd-review-max` 前后接入 LLM Wiki 知识库——检索 `BUSINESS_CONTEXT.md`、`raw/`、`wiki/`、`raw-code/`、`wiki/code/`，输出 MECE 影响范围、历史规则冲突、已有实现差异与 Cwiki 评论稿。

可脱离 `$llm-wiki` 主 skill 使用；但不要修改 `prd-review-max` 包内文件，增量规则写在 `skills/requirement-review/references/kb-evidence-bridge.md`。

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
2. 准备有效的 `BUSINESS_CONTEXT.md`。这是硬性前置；模板 TODO 占位文件不算有效输入。
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

- 修改主协议时，更新 `skills/llm-wiki/references/commands/<command>.md` 与 `references/core-rules.md`；跨命令共享部分更新 `references/commands/_shared.md`；仅路由/阅读顺序变更时再改 `SKILL.md`。
- 新增常用命令时，增加对应 `skills/llm-wiki-*/SKILL.md` wrapper，并同步更新本 README 的二级 skill 表。
- 修改安装行为时，同步更新 `install.sh`、`tests/` 和安装说明。
- 修改需求评审能力时：KB 桥接更新 `skills/requirement-review/` 与 `skills/llm-wiki-review-requirement/`；`prd-review-max` 规则变更在上游仓库维护，本仓库只更新 `install_prd_review_max.sh` 与桥接文档。
