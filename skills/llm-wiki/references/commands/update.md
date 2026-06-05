## `llm-wiki update`

Purpose: respond to changes, resume incomplete work, refine affected pages, and refresh code evidence without rebuilding the whole project.

update 可以自动进入 source refinement：当 `tools/check_refinement.py`、`staging/refinement-plan.json` 或 `staging/update/latest.json.refinement_contract.status` 暴露 pending / stale / needs_refinement 时，当前 agent 必须在同一轮处理可安全完成的语义精修。用户也可以主动触发 `llm-wiki refine`；它复用 update 的 shared preflight、validation 和 publish 规则，但把语义精修队列作为主目标。

Release note:

- `engine-v1.0.13`: 修复 raw-code 同步命令接入 Git 鉴权时重复 `git` 前缀的问题，并保留代码仓库权限诊断短句。
- `engine-v1.0.12`: 收敛 `llm-wiki code-trace` 为单一二级命令，诊断、确定性重建、AI 精修和验证改为内部阶段，不再暴露 `doctor/rebuild/refine` 三级子命令。
- `engine-v1.0.11`: 恢复 `llm-wiki-code-trace` 顶层短入口并从安装清理列表移除，确保 Codex/Qoder 等客户端可直接显示 code-trace 指令。
- `engine-v1.0.10`: 新增 `llm-wiki code-trace` 二级命令，支持独立 code trace 诊断、确定性重建和 AI 精修能力；AI 精修可分布执行但必须完成声明范围内的代码追踪精修。
- `engine-v1.0.9`: traceability 从“整页需求到代码文件”升级为 traceability units，优先按 endpoint/关键事实、业务能力、字段参数和调用链维度诊断代码追踪粒度，并在 health/doctor 中暴露低粒度与未映射候选问题。
- `engine-v1.0.7`: source 精修 contract 扩展为 source + code refinement contract；薄 codebase index、未消化 capability candidates 和代码 traceability 缺口会进入 `doctor` / `update` 的 P1 自动精修队列。
- `engine-v1.0.6`: `init_auth_env` reuses existing local GitLab/Jira tokens, dynamically detects GitLab SSH/credential auth, and presents GitLab/Jira token creation links only when needed.

If the user asks to update the **llm-wiki skill itself** rather than KB content, route to `llm-wiki update-skill` semantics below. Do not mix global skill installation changes into an ordinary KB update unless the user explicitly asked for it.

Shared update protocol:

- `llm-wiki update` defaults to shared mode. Before local deterministic work starts, synchronize the KB git repository with its upstream branch. After deterministic update and hard validation finish, publish the shared KB baseline with a normal git commit and push. Pending source refinement is not a raw/graph/health hard blocker, but `refinement_contract.status=needs_refinement` is a P1 automatic update task: the current agent must run agent-native source refinement before final closure, not merely publish and tell the user to run update later. If more than 10 source pages are pending, use currently available subagents/workers to process disjoint `wiki/sources/*` slices in parallel and try to finish the full queue in the same update. Do not treat a tiny sample, such as five pages, as the default completion target. If hard validation passes but a real blocker, tool limit, context limit, or explicit user stop prevents full refinement completion, publish a `usable-with-gaps` batch checkpoint instead of leaving generated KB artifacts dirty in one local clone.
- `llm-wiki update --local` or `LLM_WIKI_UPDATE_MODE=local` is the explicit local-only trial mode. Local mode may update the user's working copy without pulling or pushing the shared KB baseline.
- `--no-auto-raw-sync` and `LLM_WIKI_NO_AUTO_RAW_SYNC=1` are local-mode escape hatches only. Shared mode must reject them before running the update callback; do not publish a baseline built from intentionally stale `raw/` or `raw-code/`.
- `LLM_WIKI_CWIKI_SMOKE_MAX_PAGES=<n>` and `LLM_WIKI_CWIKI_SMOKE_RSS_MAX_RESULTS=<n>` are local/temp test controls for reducing Cwiki download pressure while still exercising Cwiki authentication and page fetch. They are rejected in shared mode because a truncated `raw/` cache must not be published as a shared baseline.
- `upstream/wiki-sources.json` restores `raw/`. `upstream/code-sources.json` restores `raw-code/` as engine-managed git checkouts created by `llm-wiki add-code`.
- `raw/` and `raw-code/` are local evidence caches. They must be ignored by git and excluded from shared publish. Shared publish is allowlisted to KB outputs such as `BUSINESS_CONTEXT.md`, `upstream/**`, `wiki/**`, selected `docs/**`, `staging/**`, `graph/**`, `index/**`, and engine-owned `tools/**` files refreshed from the installed skill template.
- If the KB repository is missing, has no upstream, diverges, has dirty local changes, or contains unrecognized local commits, fail closed before update or publish. In interactive cases where the failure can safely remain local, ask in Chinese whether to switch to local mode, then rerun local-mode preflight before continuing.
- If `git pull`, `git fetch`, raw-code checkout pull, or `git push` fails because of permission/authentication, report it in Chinese as missing read/write permission. Use wording like `缺少读取/写入权限，请先申请 KB/代码仓库权限，或检查 SSH Key / Git 凭证。` Do not present permission failures as skippable sync. For raw-code permission failures in shared mode, block before writing raw/wiki/staging outputs; tell the user to either fix code repository access and retry, or explicitly switch to `llm-wiki update --local` / `LLM_WIKI_UPDATE_MODE=local` for a local-only trial.

Common triggers:

- New or edited `raw/**/index.md`.
- Updated `BUSINESS_CONTEXT.md`.
- New or edited `raw-code/*` files.
- Code wiki pages became stale.
- Prior build/refinement/traceability work was interrupted and should resume from status.
- Source, concept, entity, layered page, capability, or traceability pages need targeted refinement.
- A user manually edited wiki pages and wants dependent pages refreshed.
- Health, graph, or traceability anchor checks started failing.
- G+ semantic underfit even when health is green: concepts/entities are too coarse for the source scale, source-to-concept coverage is low, manual concept/entity placeholders remain, G+ layers are index-only/low-density, or query acceptance / quality audit artifacts are stale.

Read:

1. `BUSINESS_CONTEXT.md`
2. `staging/refinement-status.md`
3. `staging/health/latest.json`
4. `graph/summary.md`
5. `docs/retrieval-playbook.md`
6. `docs/build-and-maintenance.md`
7. changed files and their dependents

Impact analysis:

- If `raw/` changed: update matching source pages, affected layered pages, concepts, entities, query acceptance, health, graph.
- If `BUSINESS_CONTEXT.md` changed: update canonical aliases, concepts, entities, conflicts, query playbook, affected answers.
- If `raw-code/` changed: update affected codebase pages, endpoint maps, compact upstream artifacts, capability candidates, traceability rows, and graphify status if needed.
- If `wiki/code/traceability/` changed: verify evidence strength, source anchors, code anchors, and linked capability pages.
- If docs changed only: update retrieval/build guidance and run link checks.
- If G+ semantic underfit is reported by `tools/update_wiki.py` or `tools/doctor.py`: do not rebuild `raw/` solely for that reason; run an agent-native G+ semantic expansion pass over existing source pages.

Default update order:

1. Resolve update mode. Default to shared mode unless `--local` or `LLM_WIKI_UPDATE_MODE=local` is present.
2. In shared mode, run KB git preflight first: evidence caches ignored and untracked, upstream configured, worktree clean, fetch/pull fast-forward only, recognized local shared-update commits pushed if needed, and skip flags rejected. If this fails with an interactive local fallback offer, continue only after the user accepts the switch to local mode.
3. Restore code evidence first in shared mode: use `upstream/code-sources.json` to clone or pull managed `raw-code/<codebase_id>/` checkouts before any raw/wiki/staging writes. If raw-code is unmanaged, damaged, dirty, missing permissions, or cannot fast-forward, stop the shared update before generating KB outputs. Then use `upstream/wiki-sources.json` to sync `raw/`. Local mode may use `--no-auto-raw-sync`; shared mode may not.
4. Identify changed files and classify the trigger.
5. Repair project agent query-routing rules when the standard template tooling is available:
   - Before running a local `tools/update_wiki.py` that may be from an older KB, refresh engine-owned project tooling from the installed skill template:

     ```bash
     python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
     ```

   - This is the automatic migration path for existing KB projects; do not ask the user to run `--agent-rules-only` manually during normal `llm-wiki update`.
   - `tools/update_wiki.py` refreshes `AGENTS.md` by default so older KB projects gain the `## Query Routing` rules automatically.
   - use `--no-agent-rules-refresh` only when the user explicitly wants a deterministic update without touching project-level agent instructions.
   - `llm-wiki doctor` should only report missing agent rules; it should not modify files.
6. Refresh upstream inputs when the project has a declared updater:
   - treat `upstream/wiki-sources.json` as the standard source of truth for upstream inputs; `type: confluence` refreshes full Cwiki pages, `type: rss` refreshes RSS/Atom snapshots
   - treat `upstream/code-sources.json` as the standard source of truth for code inputs; each source restores one clean managed checkout under `raw-code/<codebase_id>/`
   - keep every wiki relationship in that source object: 0-1 root, later added wiki, source role, depth, RSS URL, output/metadata paths, and `filters.updated_since`
   - if the project has enabled RSS feeds or Cwiki sources, run that upstream sync before the deterministic update
   - when an older repo only has `config/rss-feeds.yaml`, treat it as legacy input and let `tools/update_wiki.py` migrate it into `upstream/wiki-sources.json`
   - if upstream wiki URLs are configured but RSS/feed URLs are missing, attempt deterministic feed discovery from the wiki URL and platform metadata before syncing
   - if an RSS/feed URL cannot be inferred, tell the user exactly which wiki URL needs a manually supplied RSS URL; if the user does not provide one, leave the RSS/feed field empty and report that automatic future updates for that source cannot be completed
   - if the project has engine-managed `raw-code/<codebase_id>/` git checkouts, refresh them by default before code wiki rebuild; for the standard template this means auto-running `git pull --ff-only` inside `tools/update_wiki.py`
   - unmanaged, copied, symlinked, or ad-hoc raw-code directories are legacy states and should block update until migrated
   - never silently overwrite dirty `raw-code/*` worktrees; block and report the specific codebase instead
7. Run the deterministic project update command when available, such as `uv run python tools/update_wiki.py`.
   - when upstream sync is enabled in the project, prefer an update command path that includes the raw refresh automatically, for example by auto-running Cwiki sync and `tools/rss_sync.py` inside `tools/update_wiki.py` or by passing `--raw-sync-command`
   - when `raw-code/` codebases are connected through `llm-wiki add-code`, prefer an update command path that includes the code refresh automatically by auto-running `git pull --ff-only` per clean managed codebase inside `tools/update_wiki.py`
   - when the standard template is installed, `update` should refresh `staging/cjira-registry/active.json` after source scan; terminal pages move to `archive.json`
8. Map changed inputs to wiki outputs from the update report, usually `staging/update/latest.md` or `staging/update/latest.json`.
   - Read `staging/refinement-plan.json` and `references/refinement-contract.md`; use them as the write-scope and acceptance contract for semantic refinement.
   - Read `staging/update/latest.json` `gplus_quality`; if `status=needs_attention`, treat it as an update trigger even when `semantic_update_required=false`.
   - Before deciding which pending pages need semantic rewrite, run the lightweight historical refinement-state reconcile built into `tools/update_wiki.py`. This repairs source pages whose content is already refined but whose `Source Metadata` or `staging/refinement-status.md` still says pending/applied/missing completed record. It may update only `wiki/sources/*` metadata and `staging/refinement-status.md`; it must not rewrite source prose.
   - Before dispatching a large semantic queue, choose workers by capability tier instead of by client or model name:
     - inspect what the current host exposes: no worker support, workers without model/capability controls, or selectable worker tiers
     - choose the lowest-cost available worker that can safely satisfy the slice
     - use lightweight workers for deterministic state repair, metadata/status reconciliation, short low-risk source pages, and format-only cleanup
     - use standard workers for ordinary source refinement and source-to-link updates
     - use the strongest available worker only for cross-page conflicts, G+ taxonomy/entity redesign, traceability strong-evidence judgments, or high-risk business interpretation
     - have lightweight/standard workers mark ambiguity, missing evidence, or conflicting facts instead of guessing; reroute only those slices to a stronger worker or the main agent
     - if the host does not expose worker capability selection, use the default worker or sequential batching and state that capability selection is unavailable
9. Refresh affected pages:
   - changed `raw/` pages update matching source pages, layered pages, concepts, entities, query readiness, health, and graph
   - changed `raw-code/` files update affected codebase pages, endpoint maps, freshness state, capability/anchor candidates, traceability rows, and graphify status when needed
   - changed `BUSINESS_CONTEXT.md` updates canonical aliases, concepts, entities, conflicts, truth, and retrieval guidance
   - if health or the update report shows remaining `pending` or `stale` source pages, resolve them in the same command when they are in scope or the backlog is small enough to finish safely
   - G+ semantic underfit updates concepts/entities, source Business Links, truth/conflicts/evidence/proposals/operations/reference, query acceptance, and G+ quality audit without rewriting unrelated source summaries
10. When the same update affects both requirement/source evidence and implementation/code evidence, treat source refinement and code traceability refresh as one integrated update pass:
   - refine stale affected source pages first
   - immediately update affected `wiki/code/capabilities/` and `wiki/code/traceability/` rows against the refined requirement evidence
   - re-check evidence strength after both sides are updated
   - do not present these as separate optional next commands unless the user explicitly asked to stop after one layer
11. Continue automatically through all low-risk update completion work:
   - affected source AI refinement
   - affected concept/entity/layer page refresh
   - affected codebase and capability page refresh
   - affected code traceability rows
   - G+ semantic expansion when deterministic diagnostics report underfit and the needed facts are already present in source pages
   - broken wikilink fixes
   - health and graph rebuild
12. Preserve manual edits and refined prose unless directly stale.
13. Re-run health after AI-native edits, not only after deterministic build.
14. Rebuild graph after AI-native edits when wikilinks changed.
15. Run optional traceability anchor check when traceability pages changed.
16. Update `staging/refinement-status.md`.
17. Treat validation as part of update completion:
   - run or inspect `tools/check_refinement.py` and `staging/update/latest.json.refinement_contract` when `staging/refinement-plan.json` says semantic refinement is required; classify pending source refinement as a P1 automatic update task and process it in the current command before final closure. When more than 10 source pages are pending, dispatch parallel subagent/worker batches with disjoint write scopes, size the plan to cover as much of the full queue as possible, and do not manually stop after a tiny sample.
   - run health before final reporting when `tools/health.py` exists or the project has an equivalent health check
   - rebuild graph before final reporting when `tools/build_graph.py` exists or wikilinks changed
   - run `tools/anchor_check.py` when traceability pages or code anchors changed
   - if hard validation fails and the fix is low-risk and in scope, fix it before final reporting
   - if hard validation fails and cannot be fixed safely, report the blocker and recommend the smallest safe continuation
18. In shared mode, publish the shared KB after deterministic update and hard validation callbacks finish. P1 source refinement should be attempted before the final user-facing closure, but a remaining `refinement_pending` / `needs_refinement` checkpoint is publishable when health, graph and required anchor checks pass; do not leave allowlisted generated KB artifacts dirty only because semantic refinement still has a remaining queue. Image evidence pending or already checkpointed low-density G+ layers may remain `usable-with-gaps`. Stage exact allowlisted paths only; never broad-add `raw/`, `raw-code/`, credentials, logs, dependencies, or unrecognized local files. If push fails after commit, say in Chinese that the shared KB is committed locally but unpublished, and include read/write permission guidance when applicable.
19. For status-sensitive projects, read `staging/cjira-registry/active.json` and `archive.json` during update / doctor / query:
   - `doctor` should report stale Jira fetches and low-confidence primary selections
   - `query` should use registry state when answering whether a requirement is `idea`, `in_progress`, or `frozen`
   - when cjira lookup fails but raw contains an explicit `project.guazi-corp.com/browse/<KEY>` link for the same key, treat that legacy link as shipped/frozen historical evidence and set `status_source = legacy_project_jira_reference`
   - unknown or failed Jira lookups must remain active and must not be promoted to `frozen`

Project command convention:

- If the repo has `tools/update_wiki.py`, prefer it over manually chaining `build_wiki.py`, `health.py`, and `build_graph.py`.
- A template-installed project should also have `scan_code.py`, `graphify_code.py`, `build_traceability.py`, and `anchor_check.py`; use them for 0-1 builds involving code evidence.
- If the repo does not have a local update command, use the standard deterministic build order and create a brief impact report before AI-native edits.
- Local scripts may scan files, compare hashes, build manifests, and validate links; semantic summary, entity normalization, and implementation judgment must happen in the current agent or its available workers, not through local model SDK calls.

Do not:

- Regenerate the full wiki just because one input changed.
- Rewrite `raw/`.
- Rewrite unrelated refined pages.
- Upgrade `partial`, `inferred`, `external`, or `missing` evidence to `strong` without direct proof.
- End by asking the user to run `llm-wiki update` again for low-risk pending/stale/source/traceability work that can be completed now.

Final report:

- trigger
- changed inputs
- upstream sync status, including missing RSS/feed URLs when automatic wiki updates are configured
- code sync status, including which `raw-code/<codebase_id>/` worktrees were refreshed, skipped, overridden, or blocked as dirty
- agent rules status: created / updated / already present / skipped
- affected wiki layers
- pages updated
- pages intentionally left untouched
- validation results
- G+ semantic quality status: ok / needs_attention, including concept count, concept coverage, manual placeholders, and any P1/P2 underfit findings
- source refinement contract status: ok / needs_refinement, including processed pages, remaining queue, and whether any batch checkpoint was published
- drawio status: `auto-converted X/Y, Z missing` — report separately from image evidence; when `missing_evidence_count == 0`, drawio is complete and must not appear in `建议下一步` or any recommendation
- image evidence status: `N screenshots/photos pending screening, run llm-wiki image` — P2 suggestion only; never conflate with drawio status
- readiness: healthy / usable-with-gaps / blocked, with the reason
- remaining stale or missing evidence

Recommendation rule:

- Drawio vs image separation: `drawio_repair.py` is a **deterministic pipeline** that auto-converts `.drawio` XML to `.drawio.md` Markdown during every update. Ordinary images (screenshots/photos) are an **AI screening flow** triggered by `llm-wiki image`. These are fundamentally different workflows — never conflate them in reports or recommendations.
- When `drawio_repair.missing_evidence_count == 0`, drawio is fully converted: do **not** mention drawio in `建议下一步` or any recommendation. Only mention drawio when `missing_evidence_count > 0` (e.g., new `.drawio` files that failed parsing).
- Drawio promotion: once all `.drawio.md` evidence is extracted, check `drawio_promotion` in the health report. When `not_promoted_count > 0`, the drawio mermaid flow knowledge has not been absorbed into concept/overview pages. Treat this as a P2 agent-native promotion task: during `llm-wiki update`, read the top not-promoted `.drawio.md` source pages, extract key flow nodes/steps/rules, and inline them into the relevant `wiki/concepts/*.md` (under a `## 流程` section) and `wiki/overview.md` (under a `## 核心流程` section). Do not merely add wiki-links — actually extract and summarize the flow knowledge. If the promotion queue is large, prioritize pages with the highest node counts or strongest business signals (流程/状态/规则/风控/权限).
- Do not recommend `llm-wiki update` as the next step when the current `llm-wiki update` can safely finish the remaining source refinement, capability, traceability, health, or graph work. Finish it in the current command.
- Do not leave P1 `source_refinement_pending` as a plain soft gap. Run agent-native source refinement in the current update. If the queue is too large for one manual pass, use subagents/workers in parallel and target the full queue, not a tiny sample. Checkpoint only after a real blocker, tool/context limit, or explicit user stop, and state exactly what remains.
   - If affected source pages remain stale and affected code traceability also needs refresh but a hard blocker prevents completion, report the blocker and checkpoint, then recommend one combined continuation: `llm-wiki update` to resume the integrated source refinement plus traceability refresh.
   - If only code trace refinement remains and source/business evidence is otherwise current, recommend `llm-wiki code-trace` instead of another full `llm-wiki update`.
   - Source-only refinements still stay under `llm-wiki update` or `llm-wiki refine`; code-trace-only rebuild/refine work should route to `llm-wiki code-trace`.
- When validation fails, recommend the smallest safe continuation or fix, phrased as a command the user can run (`llm-wiki update`, `llm-wiki doctor`, or `llm-wiki image`) rather than a script chain.
- When validation passes and there are no blockers, say the KB is ready to use or ready for the owner's normal git/release process.
- Do not call a KB fully ready when `gplus_quality.status=needs_attention`; describe it as structurally healthy but semantically underfit, and either complete the G+ expansion in the current update or report the smallest blocker that prevents it.
