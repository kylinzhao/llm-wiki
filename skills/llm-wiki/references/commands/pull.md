## `llm-wiki pull`

Purpose: fast, no-refresh warm-up. Sync the KB git repository and the local `raw/` + `raw-code/` evidence caches with their upstream sources, then report the KB's last update and last refinement times. `llm-wiki pull` must **not** enter source/concept/entity/wiki refinement, code wiki rebuild, traceability refresh, or shared publish. It is the lightest possible maintenance command and never modifies `wiki/`, `staging/`, `graph/`, `index/`, or `tools/` outputs.

Use it when:

- The user is about to ask questions and wants the local evidence caches to reflect the latest upstream before reading.
- The user explicitly says "只拉最新但不做精修 / just pull the latest, do not refine / warm up the KB without rebuilding".
- The user wants a quick freshness report (last update time, last refinement time) without paying for a full `llm-wiki update`.
- The user is on a slow or low-context host and wants a low-risk, deterministic sync only.

Do not use it when:

- The user wants wiki, source, concept, entity, code wiki, or traceability to be regenerated or refined. Route to `llm-wiki update`, `llm-wiki refine`, `llm-wiki code-trace`, or `llm-wiki backfill`.
- The user wants the skill bundle itself upgraded. Route to `llm-wiki update-skill`.
- The user wants a read-only health portrait. Route to `llm-wiki doctor`.

Read:

1. `BUSINESS_CONTEXT.md`
2. `upstream/wiki-sources.json` and `upstream/code-sources.json` (declared upstream sources)
3. `staging/refinement-status.md` (for `last_verified_inputs`, `phase`, `next_action`)
4. `staging/update/latest.json` (most recent deterministic update report, if present)
5. `staging/health/latest.json` (for `evidence_gaps` / `recommended_actions` context)
6. `docs/build-and-maintenance.md`

Run order:

1. Resolve mode. `llm-wiki pull` is always **local-only**. It does not run the shared preflight, does not commit, does not push, and does not require a clean worktree. It does not modify `wiki/`, `staging/`, `graph/`, `index/`, or `tools/` outputs.
2. Detect the KB git repository. If the project root is not a git repository, or has no upstream, report "no KB git upstream" in Chinese and continue with step 3 (raw / raw-code sync) only.
3. Run KB git sync:
   - `git fetch --all --prune`
   - `git status --porcelain` — if the worktree is dirty, report the dirty paths in Chinese and stop before any destructive git operation. Do not auto-stash, do not auto-reset, do not auto-merge. Ask the user whether to continue with `git pull` (and accept the risk) or to commit/stash first.
   - `git pull --ff-only` against the tracked upstream. If a non-fast-forward is reported, stop and ask the user in Chinese: "KB git 已分叉，请先决定 rebase / merge / 切换到本地副本再重试"，do not silently rewrite history.
4. Sync `raw/` from declared wiki sources:
   - read `upstream/wiki-sources.json`; for each entry, refresh the local evidence cache (Cwiki full-page export for `type: confluence`, RSS/Atom snapshot for `type: rss`).
   - this is the same evidence sync that `llm-wiki update` performs in shared preflight, but `pull` does not trigger deterministic update, does not write to `wiki/`, and does not refresh `staging/update/latest.json` from the new evidence.
5. Sync `raw-code/` from declared code sources:
   - read `upstream/code-sources.json`; for each entry, run `git pull --ff-only` inside the managed `raw-code/<codebase_id>/` checkout.
   - unmanaged, copied, symlinked, or dirty raw-code worktrees must be reported, not auto-repaired. Do not silently overwrite them. Do not run `llm-wiki add-code` migration automatically.
6. Do not enter any refinement stage. Do not run `tools/update_wiki.py`, `tools/graphify_code.py`, `tools/build_traceability.py`, `tools/doctor.py`, or `tools/check_refinement.py` in write mode. A read-only `tools/check_refinement.py --status` is allowed only to classify the freshness verdict in step 7, and must not write.
7. Compute the freshness report:
   - `kb_git_head`: current `HEAD` commit SHA and committed-at timestamp (`git log -1 --format=%H %cI`).
   - `kb_git_upstream`: upstream branch name and the last fetched HEAD.
   - `last_update_time`: prefer `staging/update/latest.json` `updated_at` / `generated_at`; fall back to `staging/refinement-status.md` `last_verified_inputs.<input>.last_seen`; fall back to KB git HEAD commit time.
   - `last_refinement_time`: `staging/refinement-status.md` `phase` and the most recent refined source page mtime (or `staging/refinement-plan.json` `last_processed_at` if present). If no refinement has ever been recorded, report "从未精修".
   - `raw_status`: per-source counts (pages / RSS entries / mtimes) for each `upstream/wiki-sources.json` entry.
   - `raw_code_status`: per-codebase HEAD SHA, dirty/clean, and `git pull --ff-only` outcome for each `upstream/code-sources.json` entry.
   - `pending_refinement`: read-only summary from `staging/refinement-status.md` / `staging/refinement-plan.json` / `tools/check_refinement.py --status`; `pull` does not process the queue.
   - `evidence_gaps`: read-only summary from `staging/health/latest.json` `evidence_gaps`; `pull` does not heal them.
8. Produce the verdict:
   - If `last_update_time` is missing, or the KB has never been initialized, say "KB 尚未初始化，建议先执行 `llm-wiki init` 或 `llm-wiki fast`".
   - If `last_update_time` exists and the gap to `now` is **≤ 1 day**, say "知识库较新（距上次更新 < 1 天），建议直接使用 `llm-wiki query` / `llm-wiki query-plus`". Do not recommend `llm-wiki update` in this branch.
   - If `last_update_time` exists and the gap to `now` is **> 1 day**, say "距离上次更新已超过 1 天，建议执行 `llm-wiki update` 让 `raw/` / `raw-code/` 的变化进入 wiki 与 traceability". Always include the freshness sources in the report so the user can verify the verdict themselves.
   - The 1-day threshold is informational, not enforced. Do not auto-run `llm-wiki update`.

Common triggers:

- Before opening the project for a Q&A / coding session.
- Periodic warm-up on a low-context host.
- After a teammate said they pushed new raw or raw-code changes and the user just wants the local cache to catch up.

Do not:

- Modify `wiki/`, `staging/`, `graph/`, `index/`, `BUSINESS_CONTEXT.md`, or `tools/`.
- Enter source / concept / entity / code wiki / traceability refinement.
- Run a shared-mode publish (no commit, no push, no `usable-with-gaps` checkpoint).
- Use `--no-auto-raw-sync` or `LLM_WIKI_NO_AUTO_RAW_SYNC=1`: `pull` always refreshes raw/raw-code; those escape hatches only apply to `llm-wiki update` local-mode.
- Auto-stash, auto-reset, auto-merge, or auto-rebase a dirty or diverged KB git.
- Use `LLM_WIKI_CWIKI_SMOKE_MAX_PAGES` or `LLM_WIKI_CWIKI_SMOKE_RSS_MAX_RESULTS`: `pull` is a local evidence sync, not a test control; truncation must not be silently published.

Final report (Chinese, mirror the existing `llm-wiki update` report shape but minimal):

- 上游同步状态：KB git / `raw/` / `raw-code/` 各自的 `ok` / `dirty` / `no_upstream` / `diverged` / `permission_denied` / `skipped`
- 上次更新时间：来源（`staging/update/latest.json` / `staging/refinement-status.md` / KB git HEAD），UTC+8 展示
- 上次精修时间：来源（`staging/refinement-status.md` `phase` / `staging/refinement-plan.json` / 源页 mtime），未精修时显式标注
- `raw/` 缓存摘要：每个 wiki 源页面数、RSS 条目数和最近 mtime
- `raw-code/` 缓存摘要：每个 codebase 的 HEAD SHA、dirty/clean、`git pull --ff-only` 结果
- 待办精修：仅报告 P1 / P2 数量与来源，不处理
- 证据缺口：仅报告 `staging/health/latest.json` `evidence_gaps`，不修复
- 建议下一步：见下方 `Verdict & 建议下一步` 规则

Verdict & 建议下一步 rule:

- `last_update_time` 缺失 → 建议 `llm-wiki init` / `llm-wiki fast`。
- `now - last_update_time ≤ 1 day` → 建议直接使用 `llm-wiki query` / `llm-wiki query-plus`；**不要**在 `建议下一步` 里推荐 `llm-wiki update`。
- `now - last_update_time > 1 day` → 建议 `llm-wiki update`（用户可显式追加 `--local` / `LLM_WIKI_UPDATE_MODE=local` 做本机试跑）。
- 1 天阈值是经验值；当阈值触发但 `pending_refinement` 队列为空且 `evidence_gaps` 为空，仍按 "> 1 天" 分支给出 `llm-wiki update` 建议，但要在报告里说明上游时间只是"软提示"，由用户决定是否升级。
- 权限失败、KB git 分叉、`raw-code/` dirty、未受管 `raw-code/` 等阻断项必须显式列出；不要把它们降级成普通 gap。

Cloud result envelope:

When `llm-wiki pull` is executed by Cloud, end the Markdown report with exactly one fenced block whose info string is `llm-wiki-job-result-json`. The JSON must use `schemaVersion: "llm-wiki-job-result/v1"`, `command: "llm-wiki pull"`, `status` (`completed`, `failed`, `blocked`, `partial`, or `skipped`), `phases`, `issues`, `pushStatus: "not_requested"`, and `recommendations`. Use stable phase names such as `kb_git_sync`, `raw_sync`, `raw_code_sync`, and `freshness_report`. `issues` must be an empty array when there are no issues; otherwise each issue must include a stable uppercase `code`, redacted `message`, and optional `remediation`.

Never include GitLab tokens, Authorization headers, Cookie values, askpass output, environment dumps, or token-bearing remote URLs in the Markdown report or the `llm-wiki-job-result-json` envelope. Replace sensitive values with `[REDACTED]`.
