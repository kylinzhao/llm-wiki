---
name: llm-wiki-update
description: LLM Wiki 增量维护入口。用于 raw/、BUSINESS_CONTEXT.md、raw-code/、wiki 页面或源码变更后的影响范围更新，也用于续跑、精修、代码 wiki、能力页、追踪矩阵、健康检查和图谱收口。
---

# LLM Wiki Update

这是 `$llm-wiki update` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包内 `references/core-rules.md`（子入口必读；**不要**加载完整 `SKILL.md`）。
2. 读取 `references/commands/_shared.md` 与 `references/commands/update.md`。
3. 将 `$llm-wiki-update` 后面的用户文本作为 `llm-wiki update` 参数。
4. 默认协作模式：`llm-wiki update` 默认先同步共享 KB git 基线，再恢复 `raw/` / `raw-code/` 证据缓存，完成结构校验后发布共享 KB 产物。只有用户显式使用 `--local` 或 `LLM_WIKI_UPDATE_MODE=local` 时，才跳过 pull/push。共享模式不得使用 `--no-auto-raw-sync` 或 `LLM_WIKI_NO_AUTO_RAW_SYNC=1` 发布基线。
   - 如果 `git pull` / `git push` 因权限失败，中文说明缺少读取/写入权限，并提示用户申请仓库权限或检查 SSH Key / Git 凭证。
   - 如果共享发布失败且不是权限缺失、分叉、未识别本地提交或脏工作区等硬阻塞，交互式场景应提醒用户“是否切换到本机模式继续？”。切换后必须重新执行本机模式 preflight，不得复用失败的共享状态。
   - `tools/check_refinement.py` 或 `staging/update/latest.json.refinement_contract.status=needs_refinement` 表示 P1 自动 update 任务：当前 agent 必须在同一轮进入 agent-native source 精修队列，更新对应 `wiki/sources/*`、Business Links 和 `staging/refinement-status.md`。不能只发布后提醒用户“下次再 update”。
   - 在分派语义精修前，`update` 必须自动执行轻量历史状态收口：修复已经精修但 metadata/status 仍显示 pending/applied/缺 completed record 的 source page。该步骤只允许修改 `wiki/sources/*` 的 `Source Metadata` 与 `staging/refinement-status.md`，不得重写 source 正文；用户不需要为了这类历史异常手动知道或先跑 `backfill`。
   - 当 pending source 队列较大（建议阈值：超过 10 页）时，必须优先使用当前环境可用的 subagent / worker 并行分片处理，分片写入范围限定到互不重叠的 `wiki/sources/*` 文件；主 agent 负责汇总 `staging/refinement-status.md`、重跑 health/graph/anchor、提交发布。分片目标应按可用 worker 与上下文容量尽可能覆盖完整队列，不得把 5 页或少量样本当作默认完成策略。只有遇到真实 blocker、工具限制、上下文耗尽或用户要求停止时，才允许发布 batch checkpoint；checkpoint 必须说明为什么没能继续并行处理、已处理范围和剩余队列。只要 health/graph/必要 anchor 通过，剩余 `needs_refinement` 不得让 allowlisted 生成产物长期停留在本地未提交状态。
   - worker / subagent 选择必须按“任务难度和风险 -> 能力层级”动态路由，不得写死 Codex、Cursor、Qoder、WorkBuddy、Claude Code 或任何具体模型名。确定性状态修复、metadata/status 收口、短页格式化使用当前环境中最低成本且能安全完成的 lightweight worker；普通 source 精修使用 standard worker；跨页冲突、G+ 语义重构、traceability 强证据判断、高风险业务口径使用 strongest available worker。若当前 agent 平台没有暴露模型/能力选择，只使用默认 worker 或顺序批处理，并在结果里说明“当前环境未暴露 worker 能力选择”。
5. 优先使用项目内更新入口，例如 `uv run python tools/update_wiki.py`；如果项目已配置可用 RSS/feed，同步原始 wiki 证据应作为 update 的默认前置步骤，而不是等用户额外提醒。对于 `raw-code/`，只允许一种协议：`llm-wiki add-code` 创建的 engine-managed git checkout。同一次 shared update 必须在写入 raw/wiki/staging 产物前，先对这些受管且干净的 codebase 执行 `git pull --ff-only`；发现 legacy copy/symlink/raw snapshot、权限缺失、checkout 损坏或 worktree 不干净时，必须立即阻断共享更新，避免生成缺代码证据的脏 wiki。权限受限时说明缺少代码仓库读取权限，并让用户选择：先申请权限/修复凭证后重试，或显式切换到 `--local` / `LLM_WIKI_UPDATE_MODE=local` 做本机试跑。
   - 在任何“需要重新录入鉴权”提示之前，必须先检查用户电脑本地是否已经存在可复用的鉴权状态：`~/.llm-wiki/guazi-sso.env` 中的 `GUAZI_SSO_*` / `JIRA_TOKEN` / `COOKIE_HEADER`，以及 `guazi-sso-login` 的本地 cache / login records。只要本地已有可用鉴权状态，就禁止再次提醒用户录入用户名、密码、手机号、Jira token 或 Cookie；应直接继续 `update`，或只提示“检测到本机已有鉴权，但当前登录态失效，需要刷新”。
   - 如果上游 Cwiki 同步因缺少 `COOKIE_HEADER` / SSO 凭据阻塞，不要把手填 Cookie 作为推荐路径。llm-wiki engine 内置 `guazi-sso-login` 登录组件，推荐路径是让用户提供瓜子用户名、密码、手机号，并可同时提供 Jira 令牌；内置登录组件自动换取并本地缓存 Cwiki Cookie，Jira 读取优先使用 `JIRA_TOKEN`，CHDSSO 只作为没有 Jira token 时的 fallback。给用户的 Bash 必须是“复制后直接运行、按提示输入”的形式，不要出现需要用户手动替换的 `/path/to/...`、`GUAZI_SSO_SKILL_ROOT` 或其他内部路径，也不要让用户在 Bash 里重新执行 `uv run python tools/update_wiki.py`；让用户执行完凭据注册后回到 agent，由 agent 再继续执行 update。
   - 说明边界时要准确：llm-wiki skill 不会上报用户名、密码、手机号、Jira 令牌、Cookie 或 token，也不会把敏感信息写入 KB 项目的 raw/wiki/staging/git；如果选择持久化 SSO/Jira token，则会写到用户电脑本地 `~/.llm-wiki/guazi-sso.env`，供后续本机 update 自动加载。`guazi-sso-login` 如生成 Cookie/token 缓存，也只在用户电脑本地。
   - 给用户两个选择并讲清楚凭据组：首选是用户直接在 agent 窗口提供瓜子用户名、密码、手机号和 Jira 令牌，由 agent 写入本机 `~/.llm-wiki/guazi-sso.env` 后继续 update；备选是复制 Bash 到本地终端，按提示输入并持久化这些值。说明 agent 窗口输入的内容可能进入当前 agent 会话上下文或本地会话记录，具体取决于 engine，不能承诺 engine 不记录。完整 `COOKIE_HEADER` 只作为更低优先级的一次性 fallback，不要作为主要应急建议。
   - Cwiki 鉴权失败是硬阻塞：立刻中断本轮 update，不要尝试 `--no-auto-raw-sync`、不要先做本地 deterministic pipeline、不要“跳过上游同步继续干别的”。只有用户明确说“跳过上游同步/只基于当前 raw 更新”且本轮已切换到本机模式时，才允许使用 `--no-auto-raw-sync`，并且必须在结果里把 `confluence_sync` 记为 skipped；共享模式下仍必须拒绝。
   - 任何跳过都必须显式告诉用户。当前 update 可能跳过的步骤包括：`confluence_sync` / `auto_raw_sync`（用户显式 `--no-auto-raw-sync` 或 `LLM_WIKI_NO_AUTO_RAW_SYNC=1`）、`agent_rules_refresh`（`--no-agent-rules-refresh`）、`graphify_code`（未传 `--graphify`，或已有完整 `docs/wiki` + scan anchors 足够生成候选）、以及缺少对应工具脚本时的失败/阻塞。不要把 raw-code 权限失败、legacy unmanaged raw-code、dirty worktree 或损坏 checkout 归类为可静默跳过。
   - 临时 clone 烟测可以使用 `LLM_WIKI_UPDATE_MODE=local LLM_WIKI_CWIKI_SMOKE_MAX_PAGES=<n>` 或 `LLM_WIKI_CWIKI_SMOKE_RSS_MAX_RESULTS=<n>` 来减少 Cwiki 下载压力，同时仍测试登录和页面下载链路。该限流只能用于本机/临时测试；共享模式必须拒绝，避免把截断 raw 产物发布为共享基线。
6. 刷新受影响页面；除非直接过期，否则保留人工编辑。
7. 必须读取 `staging/update/latest.json` 里的 `gplus_quality`（或用 doctor 同口径只读判断）。即使 health pass、raw 未变、stale source 为 0，只要 `gplus_quality.status=needs_attention`，也把它当作 update 触发器：进入 agent-native G+ semantic expansion，扩展/校准 concepts/entities/truth/conflicts/evidence/proposals/operations/reference，回填 source Business Links，刷新 query acceptance 和 G+ quality audit；不要为了 G+ 欠拟合重建 `raw/`。
8. 如果同一轮变更同时影响 source 精修和代码追踪，把 source 精修、capability 更新、traceability 刷新作为同一个 update 收口动作。代码更新后必须先刷新 freshness、upstream `docs/wiki` 适配、anchor/capability candidates，再让 `build_traceability.py` 刷新 `Code Anchor Candidates` 和 `staging/traceability-candidates.json`。如果当前 agent 或外部 agent worker 能执行 trace worker contract，则把结果写入 `staging/traceability/runs/<run_id>/proposals.json`，再由 `build_traceability.py` 合并到 `staging/traceability/state.json`；没有模型 worker 输出时，只能记录候选，不能自动宣称 `strong`。
9. 如果发现当前命令可以安全完成的 pending/stale/source/traceability/G+/health/graph 工作，继续完成，不要建议用户再跑一次同一个 update。source refinement pending 是 P1 自动任务；优先处理后再进入发布判断。
10. update 结束前必须自动执行收口检查：health、graph；如果 traceability 或代码锚点变化，再执行可用的 anchor check。
11. 如果硬收口检查失败或仍有可安全修复的问题，优先继续修复或建议继续 `llm-wiki update`。硬阻断包括 raw/raw-code 同步失败、health 失败、graph broken edges、必要 anchor check 失败、发布范围外文件或凭据/证据缓存误入 git。refinement pending 不属于 raw/graph/health 硬阻断，但属于 P1 自动精修任务；未尝试处理前不得把它降级成普通 soft gap。
12. 如果硬收口检查通过且没有阻塞项，在 `建议下一步` 中说明当前 KB 已可使用，并说明未来什么变化应触发下一次 `llm-wiki update`；如果只剩图片证据待筛选或已分批 checkpoint 的语义层待加厚，明确说“已发布/可发布 usable-with-gaps 共享基线”，并给出最小继续动作。若 doctor / update 没有 P0/P1，但存在重要 P2（图片证据 unknown、Cjira 状态质量、orphan source、G+ 薄层等），把最重要的 P2 提权为 P1，作为下一轮 update 消化焦点。
13. 最后输出 `建议下一步`。
