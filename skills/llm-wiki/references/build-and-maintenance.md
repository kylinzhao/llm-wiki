# 构建与维护

`$LLM_WIKI_SKILL_ROOT` 为 llm-wiki skill 包根目录（见主 `SKILL.md`「Skill 包路径」）。

## 1. 标准命令

```text
python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"
uv run python tools/build_wiki.py
uv run python tools/scan_code.py
uv run python tools/build_traceability.py
uv run python tools/health.py --json
uv run python tools/build_graph.py
uv run python tools/anchor_check.py
```

如果存在 `raw-code/`，标准文档构建之后还要进入代码 wiki 阶段。`raw-code/*` 只支持由 `llm-wiki add-code` 创建的 engine-managed git checkout；旧的复制、软链或外部路径形态属于迁移对象，不再是合法终态。
如果需要 graphify 代码图谱增强，运行：

```text
uv run python tools/graphify_code.py --all
```

重要写入后必须收口：

```text
uv run python tools/health.py --json
uv run python tools/build_graph.py
uv run python tools/anchor_check.py
```

要求：

- health 必须 pass，或明确列出阻塞原因。
- broken wikilinks 必须修到 0，除非用户确认暂留。
- graph 必须反映最新 wiki links。
- 修复明显断链、过时 index 文案、错误本地路径时默认自动继续。

## 2. 各命令职责

### `build_wiki.py`

- 扫描 `raw/`
- 生成 `wiki/` 骨架
- 输出确定性结构
- 为后续全量大模型 summary 和 AI-native 精修提供稳定落点

### `scan_code.py`

- 扫描 `raw-code/*`
- 验证每个 codebase 是否是合法的 engine-managed git checkout
- 识别技术栈 marker、文件角色、endpoint / route 候选和符号
- 输出 `staging/code-graph/<codebase_id>/manifest.json`
- 输出 `staging/code-graph/<codebase_id>/endpoint-map.json`
- 生成或刷新 `wiki/code/codebases/<codebase_id>/index.md`

### `graphify_code.py`

- 检查 `graphify` 或 `graphifyy` 是否在 `PATH`
- 对每个 `raw-code/<codebase_id>` 单独运行 `graphify update`
- 将 `graphify-out/` 归档到 `staging/code-graph/<codebase_id>/graphify-out/`
- 写入 `staging/code-graph/<codebase_id>/graphify-status.json`
- 缺失或失败时留痕，不阻断确定性代码扫描和 Markdown 构建

### `build_traceability.py`

- 基于 source manifest 和 code scan 输出生成 traceability 种子
- 写入 `wiki/code/traceability/index.md`
- 从 code manifest 生成 `Code Anchor Candidates`，完整候选写入 `staging/traceability-candidates.json`
- 合并 `staging/traceability/runs/<run_id>/proposals.json` 到单一长期状态 `staging/traceability/state.json`
- 从 `state.json` 渲染 `Verified`、`Proposed`、`Gaps` 和 `Rejected` traceability sections
- 生成确定性候选行和候选级别；真实需求点到代码锚点只有在存在可规则匹配或已验证证据时才能提升为 `strong`、`partial`、`inferred`、`external` 或 `missing`

### `health.py`

- 检查结构健康度
- 查缺页、空页、漏索引

### `build_graph.py`

- 解析 wikilink
- 输出 graph 数据

### `anchor_check.py`

- 检查 traceability 页面中反引号引用的 `raw-code/...` 锚点是否存在
- 输出 `staging/anchor-check.json`

### `rss_sync.py`

- 标准上游清单是 `upstream/wiki-sources.json`。0-1 根 wiki、后续 `add-wiki` 新增关系、RSS URL、层级和筛选条件都必须写入这个文件；不要把 URL 写死在 shell 脚本、agent 提示词或单独 RSS 配置里。
- Cwiki 根页树用一个 source object 记录：`type: confluence`、`source_id`、`relationship.role`、`page_id`、`url`、`depth`、`rss_url`、`metadata_dir`、`output_dir`、`filters.updated_since`。
- 普通 RSS/Atom 来源只在无法导出完整 wiki 正文树时使用：`{"type":"rss","source_id":"...","id":"...","url":"...","target_dir":"raw/rss/..."}`。
- `tools/update_wiki.py` 会从 `upstream/wiki-sources.json` 生成本轮 RSS 同步配置并调用 `rss_sync.py`；旧项目只有 `config/rss-feeds.yaml` 时会自动迁移为 `type: rss` 来源。
- `tools/discover_wiki_feeds.py --write-upstream` 会把验证后的 RSS/feed URL 和发现状态回写到同一个 `upstream/wiki-sources.json`，供 `add-wiki` 和 0-1 构建复用。
- `rss_sync.py` 读取生成后的 RSS 配置，按 feed/host **限速**抓取 RSS/Atom
- 将摘要写入 `staging/rss/latest.json` 与 `staging/rss/latest.md`；按需落地条目快照到各 feed 的 `target_dir`
- **无启用 feed** 或仅有空配置时 **退出码 0**（noop），便于管线安全跳过
- 当项目已经配置启用 feed 时，`llm-wiki update` / `tools/update_wiki.py` 应默认先运行这一阶段刷新 `raw/`，而不是要求用户手动补 `--raw-sync-command`
- 新项目模板默认 `kb.manifest.yaml` 中 `phases.rss_sync: true`。只有显式设置为 `false` 才关闭该阶段；如果没有 enabled `type: rss` 来源，RSS 阶段自然 no-op。

### `tools/confluence_sync/`（Confluence 正文导出）

- **`export_obsidian_wiki.py`**：入口脚本（Cookie、`--project-dir`、`--levels`、`--update`）。
- **`export_confluence_tree.py`**：REST API 拉取页面树、本地化 wiki 域内图片、写 Markdown。
- 页面证据落在 **`raw/<pageId>-<slug>/index.md`**（及 `assets/`）；导出状态与 manifest 默认在 **`staging/wiki-export/`**，与 `rss_sync.py` 的通用 RSS 快照不同用途——前者拉完整 wiki 页面内容，后者只做 feed 条目镜像。
- Cwiki `.zip` 附件会按可能的 HTML 原型处理：zip 本体保存在 `assets/`，解压内容保存在 `assets/prototypes/<name>/`，可读摘要写入 `assets/<name>.zip.prototype.md` 并回链到页面正文。
- 项目级上游配置落在 **`upstream/wiki-sources.json`**。0-1 从 Cwiki URL 导出成功后必须写入该文件；`tools/update_wiki.py` 会优先读取它并在确定性构建前自动运行 Cwiki `--update`。
- 日期筛选统一写在 `filters.updated_since`，例如 `"filters": {"updated_since": "2025-10-01"}`。历史顶层 `updated_since` 只作为兼容输入。
- 旧项目如果只有 `staging/wiki-export/export-state.json` 或历史 `raw/export-state.json`，`tools/update_wiki.py` 会自动迁移生成 `upstream/wiki-sources.json`，再按该配置刷新 Cwiki raw 页面。

### 代码 wiki 阶段

- 扫描 `raw-code/*`，识别每个 `codebase_id`
- 要求每个 codebase 都是 `llm-wiki add-code` 创建的受管 git checkout
- 读取 codebase 内部的 README、AGENTS、OpenSpec、技术设计等文本说明
- 按技术栈抽取结构事实
- 可选运行 graphify，生成源码图谱与结构报告
- 生成 `wiki/code/codebases/<codebase_id>/`
- 生成或更新 `wiki/code/capabilities/`
- 建立需求来源页、业务概念、实体、前端页面、后端接口、服务实现、异步任务之间的 wikilink

## 3. 续跑与恢复

已有项目默认续跑，不默认重建。开始前读取：

1. `BUSINESS_CONTEXT.md`
2. `staging/refinement-status.md`
3. `staging/health/latest.json`
4. `graph/summary.md` 或 `staging/graph/latest.json`
5. `wiki/overview.md`
6. `docs/build-and-maintenance.md`
7. `docs/retrieval-playbook.md`

从这些文件判断：

- source 总数与 deterministic seed 剩余数。
- 阶段 E source 精修是否完成。
- G+ text synthesis 是否完成。
- image evidence 是否完成。
- `raw/` 是否存在图片资产，以及 `staging/image-notes/` 是否已有高价值图片证据笔记。
- code wiki 是否存在、是否 stale。
- health / graph 是否为最新。
- 下一步维护建议。

每轮构建或维护结束前，更新 `staging/refinement-status.md`，至少记录：

- `task_id`
- `scope`
- `phase`
- `status`
- `checkpoint`
- `resume_from`
- `heartbeat_state`
- `last_verified_inputs`
- `last_output_paths`
- `blocked_reason`
- `image_asset_count`
- `image_note_count`
- `image_evidence_status`：`not_applicable` / `pending` / `in_progress` / `complete` / `skipped_by_user`
- `next_action`

如果项目已有精修产物、人工编辑或 `wiki/code/`，不要用确定性构建覆盖它们。只在确认输入或规则变化影响范围后，更新受影响页面。

## 4. 什么时候该重建

应该重建：

- 新增 `raw/`
- 新增或更新 `raw-code/*`
- 更新了 `BUSINESS_CONTEXT.md`
- 修了 taxonomy / entity 规则
- 批量修了 wikilink
- 调整了代码能力映射、接口映射或 codebase 识别规则

0-1 首轮构建时，除了确定性重建之外，还应把全量语料的大模型 summary 和 AI-native 精修一起完成。
如果只做了 `build_wiki.py` / `health.py` / `build_graph.py`，还不能算首轮构建完成。
如果存在 `raw-code/` 且任务目标是联合 wiki，也不能只完成需求文档层；必须至少完成 codebase 识别、代码事实入口页和首轮能力页。

不必全量重建：

- 只是回答一个问题
- 只是做质量审查
- 只是修一两个 source page

## 5. 标准增量顺序

1. 更新 `raw/`
2. 更新 `BUSINESS_CONTEXT.md`
3. 跑 `build_wiki.py`
4. 对受影响语料做大模型 summary 与 AI-native 精修
5. 如果存在 `raw-code/`，扫描受影响 codebase 并更新代码 wiki
6. 更新跨层能力页和代码-需求链接
7. 跑 `health.py`
8. 跑 `build_graph.py`

## 6. G+ 综合层验收

触发条件：

- 阶段 E source 全量 AI-native 精修已完成。
- health / graph 已存在。
- 项目需要达到“可查询、可审查、可交接”状态。

标准输出：

- concepts 二次校准。
- entities 二次校准。
- truth / conflicts 重新综合。
- evidence / proposals / reference / operations 加厚。
- `docs/query-acceptance.md`。
- `docs/gplus-quality-audit.md`。
- health pass。
- graph rebuilt。
- 图片证据状态：如果 `raw/` 存在图片资产但尚未完成高价值图片证据补充，明确记录为阶段 H pending，并在建议下一步中推荐 `llm-wiki image`。

`docs/query-acceptance.md` 至少覆盖 8-10 个真实查询，查询项应包含：

- 查询类型。
- 检索路径。
- 结论。
- 支撑页面。
- 未决点。
- 是否使用 `BUSINESS_CONTEXT.md`。
- 是否使用代码证据；如果使用，区分需求证据、代码证据、推断和缺失证据。

`docs/gplus-quality-audit.md` 采用 findings-first，至少检查：

- 入口可用性。
- 实体一致性。
- source 覆盖。
- evidence strength / 证据强度区分。
- broken links / health。
- graph。
- 剩余风险。
- final verdict。

审查发现的低风险结构问题默认自动修复：

- broken wikilink。
- 明显错误的本地路径。
- 过时 index 文案。
- health 报告中的非业务判断类结构问题。

业务口径问题不要擅自定论；记录到 conflicts 或等待用户确认。

## 7. 代码 wiki 推荐顺序

1. 识别 `raw-code/*` 的 codebase 清单
2. 为每个 codebase 记录技术栈、入口、模块边界和本地规范
3. 前端优先抽取 routes、pages、services、components、API URI
4. 后端优先抽取 controllers、endpoints、API contracts、domain services、managers、dao、kafka、jobs、OpenSpec
5. 运行 graphify 或读取既有 graphify 输出
6. 把 graphify 结果转写为 `wiki/code/codebases/<codebase_id>/` 的 Markdown 事实页
7. 生成 `wiki/code/capabilities/`，把代码事实链接回 `wiki/concepts/`、`wiki/entities/`、`wiki/sources/`
8. 做代码 wiki health：查空页、断链、重复能力、未标注推断、缺失证据

## 8. 并发执行原则

为了保证速度，构建和审查应优先识别可并行工作，并用 subagent 并发推进。

推荐并发切分：

- 按 `raw/` source 批次切分需求摘要和精修
- 按 `raw-code/*` codebase 切分代码扫描和 graphify 分析
- 前端按 routes/pages/services/components 切分
- 后端按 controllers/api-contracts/domain-services/managers/dao/async/jobs/openspec 切分
- 按 `wiki/code/capabilities/*` 切分能力页草稿
- 按 health 类型切分断链、空页、证据覆盖、推断误标检查

简单任务打包规则：

- 同类、低风险、输出范围相近的小任务可以放进同一个 subagent
- 例如一组小 endpoint 映射、一组组件页、一组 source 摘要、一组 wikilink 检查
- 不要为每个小文件启动独立 subagent

安全边界：

- 每个 subagent 的写入范围必须互不重叠
- 能力页、索引页、总入口页通常由主 agent 汇总写入
- subagent 可以产出草稿、表格、发现和局部页面；主 agent 负责最终合并、命名统一和跨层链接
- 如果环境无法使用 subagent，应按批次化串行推进，并说明并发限制

阶段 E backlog 充足时，默认保持多 worker 并行。简单相关 source 可按 2-4 页打包，复杂长文档单页独占。worker 完成后立即 claim 下一批 bundle。

## 9. graphify 使用原则

graphify 是代码图谱增强层，不是业务语义基线。

默认策略：

- 有 `raw-code/` 且用户希望构建代码 wiki 时，优先考虑 graphify
- 必须先在 `docs/tooling-dependencies.md` 或最终输出中说明依赖：Python 3.10+、`uv` 必需，`graphify` 可选
- 每个 codebase 单独运行或单独归档输出
- 输出放在 `staging/code-graph/<codebase_id>/graphify-out/`
- 将 graphify 的 `graph.json`、报告、调用关系和聚类结果作为输入证据
- 最终仍要写入 `wiki/code/` Markdown，不能只留下 graphify HTML 或 JSON

不要让 graphify 覆盖以下职责：

- `BUSINESS_CONTEXT.md` 的实体规范
- `wiki/sources/` 的需求证据
- `wiki/code/capabilities/` 的跨层业务解释
- `graph/` 的 wiki-link 图谱

## 10. 发布 / 提交收口

`raw/` 不可修改和 `raw/` 不提交是两个不同约束：

- 可以读取 `raw/`。
- 不修改 `raw/`。
- 不把 `raw/` 提交到 Git。
- `staging/image-notes/` 可以引用 raw 图片路径，不复制 raw 图片。

如果需要提交或推送，先确保 `.gitignore` 包含：

```gitignore
raw/
.DS_Store
**/.DS_Store
```

提交前检查：

```bash
git ls-files 'raw/*' | wc -l
git diff --cached --name-only | rg '^raw/'
```

如果 remote / group 已明确，且 `raw/` 已确认排除，可以自动提交推送。以下情况必须停下确认：

- 用户要求提交 `raw/`。
- 需要覆盖、迁移或替换已有远端仓库。
- remote 目标不明确。
