---
name: llm-wiki-update
description: LLM Wiki 增量维护入口。用于 raw/、BUSINESS_CONTEXT.md、raw-code/、wiki 页面或源码变更后的影响范围更新，也用于续跑、精修、代码 wiki、能力页、追踪矩阵、健康检查和图谱收口。
---

# LLM Wiki Update

这是 `$llm-wiki update` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-update` 后面的用户文本作为 `llm-wiki update` 参数。
4. 优先使用项目内更新入口，例如 `uv run python tools/update_wiki.py`；如果项目已配置可用 RSS/feed，同步原始 wiki 证据应作为 update 的默认前置步骤，而不是等用户额外提醒。只要项目已接入 `raw-code/<codebase_id>/` git worktree，同一次 update 也应默认先安全刷新这些干净 codebase，再继续 code wiki 构建；如有特殊刷新命令，则按项目 manifest 覆盖。
   - 如果上游 Cwiki 同步因缺少 `COOKIE_HEADER` / SSO 凭据阻塞，不要把手填 Cookie 作为推荐路径。llm-wiki engine 内置 `guazi-sso-login` 登录组件，推荐路径是让用户提供瓜子用户名、密码、手机号，并可同时提供 Jira 令牌；内置登录组件自动换取并本地缓存 Cwiki Cookie，Jira 读取优先使用 `JIRA_TOKEN`，CHDSSO 只作为没有 Jira token 时的 fallback。给用户的 Bash 必须是“复制后直接运行、按提示输入”的形式，不要出现需要用户手动替换的 `/path/to/...`、`GUAZI_SSO_SKILL_ROOT` 或其他内部路径，也不要让用户在 Bash 里重新执行 `uv run python tools/update_wiki.py`；让用户执行完凭据注册后回到 agent，由 agent 再继续执行 update。
   - 说明边界时要准确：llm-wiki skill 不会上报用户名、密码、手机号、Jira 令牌、Cookie 或 token，也不会把敏感信息写入 KB 项目的 raw/wiki/staging/git；如果选择持久化 SSO/Jira token，则会写到用户电脑本地 `~/.llm-wiki/guazi-sso.env`，供后续本机 update 自动加载。`guazi-sso-login` 如生成 Cookie/token 缓存，也只在用户电脑本地。
   - 给用户两个选择并讲清楚凭据组：首选是用户直接在 agent 窗口提供瓜子用户名、密码、手机号和 Jira 令牌，由 agent 写入本机 `~/.llm-wiki/guazi-sso.env` 后继续 update；备选是复制 Bash 到本地终端，按提示输入并持久化这些值。说明 agent 窗口输入的内容可能进入当前 agent 会话上下文或本地会话记录，具体取决于 engine，不能承诺 engine 不记录。完整 `COOKIE_HEADER` 只作为更低优先级的一次性 fallback，不要作为主要应急建议。
   - Cwiki 鉴权失败是硬阻塞：立刻中断本轮 update，不要尝试 `--no-auto-raw-sync`、不要先做本地 deterministic pipeline、不要“跳过上游同步继续干别的”。只有用户明确说“跳过上游同步/只基于当前 raw 更新”时，才允许使用 `--no-auto-raw-sync`，并且必须在结果里把 `confluence_sync` 记为 skipped。
   - 任何跳过都必须显式告诉用户。当前 update 可能跳过的步骤包括：`confluence_sync` / `auto_raw_sync`（用户显式 `--no-auto-raw-sync` 或 `LLM_WIKI_NO_AUTO_RAW_SYNC=1`）、`auto_code_sync`（用户显式 `--no-auto-code-sync` 或 `LLM_WIKI_NO_AUTO_CODE_SYNC=1`）、`agent_rules_refresh`（`--no-agent-rules-refresh`）、`graphify_code`（未传 `--graphify`）、以及缺少对应工具脚本时的失败/阻塞。不要把鉴权失败归类为可静默跳过。
5. 刷新受影响页面；除非直接过期，否则保留人工编辑。
6. 必须读取 `staging/update/latest.json` 里的 `gplus_quality`（或用 doctor 同口径只读判断）。即使 health pass、raw 未变、stale source 为 0，只要 `gplus_quality.status=needs_attention`，也把它当作 update 触发器：进入 Codex-native G+ semantic expansion，扩展/校准 concepts/entities/truth/conflicts/evidence/proposals/operations/reference，回填 source Business Links，刷新 query acceptance 和 G+ quality audit；不要为了 G+ 欠拟合重建 `raw/`。
7. 如果同一轮变更同时影响 source 精修和代码追踪，把 source 精修、capability 更新、traceability 刷新作为同一个 update 收口动作。
8. 如果发现当前命令可以安全完成的 pending/stale/source/traceability/G+/health/graph 工作，继续完成，不要建议用户再跑一次同一个 update。
9. update 结束前必须自动执行收口检查：health、graph；如果 traceability 或代码锚点变化，再执行可用的 anchor check。
10. 如果收口检查失败或仍有可安全修复的问题，优先继续修复或建议继续 `llm-wiki update`。
11. 如果收口检查通过且没有阻塞项，在 `建议下一步` 中说明当前 KB 已可使用，并说明未来什么变化应触发下一次 `llm-wiki update`；如果只剩 G+ 欠拟合且本轮无法安全完成，明确说“结构健康但语义层欠拟合”，并给出最小继续动作。
12. 最后输出 `建议下一步`。
