# Commands

Use this reference when the user invokes a `llm-wiki` subcommand or when the request maps clearly to one command.

## Command Router

| Command | Use When | Primary Output |
| --- | --- | --- |
| `llm-wiki fast` | New project, user wants the standard path completed in one run | Full first-pass wiki, refinement, validation, status |
| `llm-wiki init` | New project, user wants phased initialization | Skeleton, deterministic build, first-pass plan |
| `llm-wiki doctor` | User wants site status, diagnosis, quality review, or prioritized recommendations | Findings plus health portrait and next steps |
| `llm-wiki version` | User asks for the llm-wiki skill / bundle version, current version, skill version, or engine version | Installed skill bundle version from `VERSION` |
| `llm-wiki update` | Existing KB needs resume, refinement, traceability refresh, source/code updates, or validation after changes | Impact-scoped update, validation, and maintenance report |
| `llm-wiki backfill` | Existing KB was built with older skill versions and needs historical evidence re-scanned | Deterministic evidence backfill, then refinement absorption through update semantics |
| `llm-wiki update-skill` | User explicitly asks to update the llm-wiki skill bundle itself, not the current KB content | Pull/reinstall the installed skill bundle, then optionally refresh project tooling |
| `llm-wiki add-wiki` | Add another document/wiki directory or wiki URL as business or requirement evidence | Imported raw evidence, source provenance, RSS/update status, and affected wiki updates |
| `llm-wiki add-code` | Add or refresh implementation evidence, code wiki, capabilities, and traceability | raw-code codebase plus code wiki and mappings |
| `llm-wiki query` | Answer a business or implementation question; business-only questions should not include detailed code evidence by default | Evidence-grounded answer with intent-based evidence scope |
| `llm-wiki query-plus` | Answer with business/requirement evidence and code implementation evidence together | Detailed business+code evidence analysis |
| `llm-wiki review-requirement` | Review a new PRD, Cwiki page, Markdown requirement, or prototype package against wiki, raw, image, zip, frontend, and code evidence | Findings-first requirement review and Cwiki comment draft |
| `llm-wiki image` | Add high-value image evidence after text completion | image notes and linked facts |

## Skill Version Queries

When the user asks for the llm-wiki skill / bundle version, current version, skill version, or engine version through `llm-wiki`, `/llm-wiki`, `llm-wiki query`, `/llm-wiki query`, `$llm-wiki-query`, or `/llm-wiki-query`, treat it as a skill metadata request, not as a KB query.

Read `VERSION` from the llm-wiki skill package root and answer from that file:

- `version`: llm-wiki skill bundle version.
- `engine_version`: bundled project template / deterministic tooling contract version.

If `VERSION` is missing, fall back to `manifest.json` in the same directory when available and report its `version`; state clearly that `engine_version` is not declared in that fallback.

## Evidence preflight (partial clone / git without raw)

Many teams **commit the built `wiki/`** but **do not commit** `raw/` or `raw-code/` (submodule, sparse checkout, or internal sync). The deterministic tools detect that situation and **block rebuild/update** until evidence is restored.

**Heuristics**

- **Expects `raw/`** when `wiki/sources/*.md` exists or `staging/source-manifest.json` lists sources.
- **Expects `raw-code/`** when `wiki/code/codebases/*/` exists or `staging/code-graph/summary.json` lists codebases.

**Behavior**

| Situation | `query` / `doctor` | `update` / `fast` / `build_wiki` | `scan_code` / `graphify` / `build_traceability` (when code evidence expected) |
| --- | --- | --- | --- |
| Built wiki present, `raw/` missing or empty while expectation holds | Continue; cite `staging/health/latest.json` `evidence_gaps` and `recommended_actions` | **Blocked** (`update_wiki` / `build_wiki` exit 2 with message) | If code expectation holds but `raw-code/` missing → **Blocked** |
| No source pages yet, empty `raw/` | N/A | Allowed (greenfield) | Skipped if no `raw-code/` and no code expectation |

**Agent rule**: When `evidence_gaps` is non-empty, **tell the user explicitly** to pull/restore `raw/` and/or `raw-code/` before promising a full rebuild or code-side refresh. `query` may still answer from committed `wiki/` when the user only needs read-only Q&A.

## Completion Rule

Every command must end with `建议下一步`.

The recommendation should be project-specific:

- 1-3 prioritized next actions.
- Include the exact next command when useful.
- Mention when it is reasonable to pause.
- Mention what future change should trigger `llm-wiki update`.

## `llm-wiki fast`

Purpose: one-shot standard build for a new project. Use when the user wants the whole first-pass workflow completed without repeated planning prompts.

Read:

1. `BUSINESS_CONTEXT.md`
2. `raw/`
3. this skill's `bootstrapping.md`
4. this skill's `build-and-maintenance.md`
5. if `raw-code/` exists, `code-wiki.md`

Run order:

1. Validate `raw/` and `BUSINESS_CONTEXT.md`.
2. Install the bundled project template unless equivalent scripts already exist: after bundle install, use your client's skills root (for example Codex: `python3 "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"`), or use `python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"` when the package lives elsewhere (see main `SKILL.md` "Skill 包路径").
3. Run deterministic build with `uv run python tools/update_wiki.py`.
   - when the standard template is installed, this command should auto-refresh enabled RSS/feed raw inputs and engine-managed `raw-code/<codebase_id>/` git checkouts before rebuilding deterministic code outputs
4. If `raw-code/` exists, run the code scan and candidate pipeline first. If a complete `raw-code/<codebase_id>/docs/wiki` exists, use it with scan anchors as the preferred first-pass code navigation layer. Run `uv run python tools/graphify_code.py --all` only when structural graph evidence is missing, stale, explicitly requested, or needed for call/dependency questions.
5. Complete first-pass source summary and AI-native refinement.
6. Build layered pages, concepts, entities, truth, conflicts, evidence, proposals, reference, operations.
7. If `raw-code/` exists, refine codebase indexes, capability pages, and traceability evidence strengths.
8. If implementation review is in scope, create traceability pages for highest-value capabilities.
9. Run G+ readiness checks when feasible: query acceptance and quality audit. For 0-1 builds this is part of the default path, not an optional follow-up: complete concepts/entities/truth/conflicts/evidence/proposals/reference/operations calibration unless a hard blocker appears or the user explicitly asks to stop after the baseline.
10. Inventory raw image assets and image-note status. Do not batch-analyze images by default, but if images exist and no image evidence pass is complete, record phase H as pending and recommend `llm-wiki image`.
11. Include deterministic text sidecars generated from `.zip` prototype attachments in source summary and refinement scope. Treat the sidecar Markdown as source evidence with provenance; do not treat binary zip files or extracted prototype assets as standalone system facts.
12. Run health, graph, and anchor check.
13. Update `staging/refinement-status.md`.

Default behavior:

- Proceed automatically through low-risk steps.
- Use subagents for large independent batches when available.
- Do not process low-value images.
- Do not submit or push unless the user explicitly asks for git publishing and the remote is clear.

Stop only when:

- `raw/` is missing.
- `BUSINESS_CONTEXT.md` is missing, empty, or still contains the bundled TODO placeholder.
- canonical entity rules need business confirmation.
- generated output would overwrite existing manual or refined wiki content.
- secrets or sensitive configs would be exposed.

Final report:

- phase completed
- files created / updated
- codebases included
- traceability coverage
- image evidence status: not applicable / pending high-value screening / complete / skipped by user
- validation results
- blocked items
- recommended next pass

## `llm-wiki update`

Purpose: respond to changes, resume incomplete work, refine affected pages, and refresh code evidence without rebuilding the whole project.

If the user asks to update the **llm-wiki skill itself** rather than KB content, route to `llm-wiki update-skill` semantics below. Do not mix global skill installation changes into an ordinary KB update unless the user explicitly asked for it.

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
- If G+ semantic underfit is reported by `tools/update_wiki.py` or `tools/doctor.py`: do not rebuild `raw/` solely for that reason; run a Codex-native G+ semantic expansion pass over existing source pages.

Default update order:

1. Identify changed files and classify the trigger.
2. Repair project agent query-routing rules when the standard template tooling is available:
   - Before running a local `tools/update_wiki.py` that may be from an older KB, refresh engine-owned project tooling from the installed skill template:

     ```bash
     python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
     ```

   - This is the automatic migration path for existing KB projects; do not ask the user to run `--agent-rules-only` manually during normal `llm-wiki update`.
   - `tools/update_wiki.py` refreshes `AGENTS.md` by default so older KB projects gain the `## Query Routing` rules automatically.
   - use `--no-agent-rules-refresh` only when the user explicitly wants a deterministic update without touching project-level agent instructions.
   - `llm-wiki doctor` should only report missing agent rules; it should not modify files.
3. Refresh upstream inputs when the project has a declared updater:
   - treat `upstream/wiki-sources.json` as the standard source of truth for upstream inputs; `type: confluence` refreshes full Cwiki pages, `type: rss` refreshes RSS/Atom snapshots
   - keep every wiki relationship in that source object: 0-1 root, later added wiki, source role, depth, RSS URL, output/metadata paths, and `filters.updated_since`
   - if the project has enabled RSS feeds or Cwiki sources, run that upstream sync before the deterministic update
   - when an older repo only has `config/rss-feeds.yaml`, treat it as legacy input and let `tools/update_wiki.py` migrate it into `upstream/wiki-sources.json`
   - if upstream wiki URLs are configured but RSS/feed URLs are missing, attempt deterministic feed discovery from the wiki URL and platform metadata before syncing
   - if an RSS/feed URL cannot be inferred, tell the user exactly which wiki URL needs a manually supplied RSS URL; if the user does not provide one, leave the RSS/feed field empty and report that automatic future updates for that source cannot be completed
   - if the project has engine-managed `raw-code/<codebase_id>/` git checkouts, refresh them by default before code wiki rebuild; for the standard template this means auto-running `git pull --ff-only` inside `tools/update_wiki.py`
   - unmanaged, copied, symlinked, or ad-hoc raw-code directories are legacy states and should block update until migrated
   - never silently overwrite dirty `raw-code/*` worktrees; block and report the specific codebase instead
4. Run the deterministic project update command when available, such as `uv run python tools/update_wiki.py`.
   - when upstream sync is enabled in the project, prefer an update command path that includes the raw refresh automatically, for example by auto-running Cwiki sync and `tools/rss_sync.py` inside `tools/update_wiki.py` or by passing `--raw-sync-command`
   - when `raw-code/` codebases are connected through `llm-wiki add-code`, prefer an update command path that includes the code refresh automatically by auto-running `git pull --ff-only` per clean managed codebase inside `tools/update_wiki.py`
   - when the standard template is installed, `update` should refresh `staging/cjira-registry/active.json` after source scan; terminal pages move to `archive.json`
5. Map changed inputs to wiki outputs from the update report, usually `staging/update/latest.md` or `staging/update/latest.json`.
   - Read `staging/refinement-plan.json` and `references/refinement-contract.md`; use them as the write-scope and acceptance contract for semantic refinement.
   - Read `staging/update/latest.json` `gplus_quality`; if `status=needs_attention`, treat it as an update trigger even when `semantic_update_required=false`.
6. Refresh affected pages:
   - changed `raw/` pages update matching source pages, layered pages, concepts, entities, query readiness, health, and graph
   - changed `raw-code/` files update affected codebase pages, endpoint maps, freshness state, capability/anchor candidates, traceability rows, and graphify status when needed
   - changed `BUSINESS_CONTEXT.md` updates canonical aliases, concepts, entities, conflicts, truth, and retrieval guidance
   - if health or the update report shows remaining `pending` or `stale` source pages, resolve them in the same command when they are in scope or the backlog is small enough to finish safely
   - G+ semantic underfit updates concepts/entities, source Business Links, truth/conflicts/evidence/proposals/operations/reference, query acceptance, and G+ quality audit without rewriting unrelated source summaries
7. When the same update affects both requirement/source evidence and implementation/code evidence, treat source refinement and code traceability refresh as one integrated update pass:
   - refine stale affected source pages first
   - immediately update affected `wiki/code/capabilities/` and `wiki/code/traceability/` rows against the refined requirement evidence
   - re-check evidence strength after both sides are updated
   - do not present these as separate optional next commands unless the user explicitly asked to stop after one layer
8. Continue automatically through all low-risk update completion work:
   - affected source AI refinement
   - affected concept/entity/layer page refresh
   - affected codebase and capability page refresh
   - affected code traceability rows
   - G+ semantic expansion when deterministic diagnostics report underfit and the needed facts are already present in source pages
   - broken wikilink fixes
   - health and graph rebuild
9. Preserve manual edits and refined prose unless directly stale.
10. Re-run health after AI-native edits, not only after deterministic build.
11. Rebuild graph after AI-native edits when wikilinks changed.
12. Run optional traceability anchor check when traceability pages changed.
13. Update `staging/refinement-status.md`.
14. Treat validation as part of update completion:
   - run `tools/check_refinement.py` before health when `staging/refinement-plan.json` says semantic refinement is required
   - run health before final reporting when `tools/health.py` exists or the project has an equivalent health check
   - rebuild graph before final reporting when `tools/build_graph.py` exists or wikilinks changed
   - run `tools/anchor_check.py` when traceability pages or code anchors changed
   - if validation fails and the fix is low-risk and in scope, fix it before final reporting
   - if validation fails and cannot be fixed safely, report the blocker and recommend the smallest safe continuation
15. For status-sensitive projects, read `staging/cjira-registry/active.json` and `archive.json` during update / doctor / query:
   - `doctor` should report stale Jira fetches and low-confidence primary selections
   - `query` should use registry state when answering whether a requirement is `idea`, `in_progress`, or `frozen`
   - unknown or failed Jira lookups must remain active and must not be promoted to `frozen`

Project command convention:

- If the repo has `tools/update_wiki.py`, prefer it over manually chaining `build_wiki.py`, `health.py`, and `build_graph.py`.
- A template-installed project should also have `scan_code.py`, `graphify_code.py`, `build_traceability.py`, and `anchor_check.py`; use them for 0-1 builds involving code evidence.
- If the repo does not have a local update command, use the standard deterministic build order and create a brief impact report before AI-native edits.
- Local scripts may scan files, compare hashes, build manifests, and validate links; semantic summary, entity normalization, and implementation judgment must happen in Codex-native work, not through local model SDK calls.

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
- readiness: healthy / usable-with-gaps / blocked, with the reason
- remaining stale or missing evidence

Recommendation rule:

- Do not recommend `llm-wiki update` as the next step when the current `llm-wiki update` can safely finish the remaining source refinement, capability, traceability, health, or graph work. Finish it in the current command.
- If affected source pages remain stale and affected code traceability also needs refresh but a hard blocker prevents completion, report the blocker and checkpoint, then recommend one combined continuation: `llm-wiki update` to resume the integrated source refinement plus traceability refresh.
- Traceability-only and source-only refinements still stay under `llm-wiki update`; do not route to separate commands.
- When validation fails, recommend the smallest safe continuation or fix, phrased as a command the user can run (`llm-wiki update`, `llm-wiki doctor`, or `llm-wiki image`) rather than a script chain.
- When validation passes and there are no blockers, say the KB is ready to use or ready for the owner's normal git/release process.
- Do not call a KB fully ready when `gplus_quality.status=needs_attention`; describe it as structurally healthy but semantically underfit, and either complete the G+ expansion in the current update or report the smallest blocker that prevents it.

## `llm-wiki backfill`

Purpose: upgrade an existing LLM Wiki project built with older skill versions by re-scanning historical evidence and then absorbing newly available evidence into the refined wiki layers.

Use when:

- The project predates newer deterministic evidence features such as draw.io text extraction, Cjira/Jira/IDEA registry, source metadata v2, or query-routing agent rules.
- The user wants a hotfix for many existing KBs without manually rebuilding from scratch.
- A doctor/update report says historical evidence exists but backfill artifacts are missing.
- A newly released deterministic feature requires re-reading old `raw/`, `wiki/sources/`, or `staging/` files.

Default order:

1. Read `BUSINESS_CONTEXT.md` when present, but do not block deterministic backfill solely because it is incomplete; report the issue before semantic absorption.
2. Refresh engine-owned tools and agent rules from the installed skill:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
   ```

3. Run the backfill pipeline:

   ```bash
   uv run python tools/backfill.py
   ```

   If `uv` is unavailable but project dependencies are already satisfied, fall back to `python3 tools/backfill.py`.

4. Read `staging/backfill/latest.json` and `latest.md`.
5. If `refinement_absorption_required=true`, continue directly with `llm-wiki update` semantics over `refinement_scope`:
   - update affected `wiki/sources/*` summaries and Business Links
   - refresh related concepts/entities
   - refresh truth/conflicts/evidence/proposals/operations/reference
   - refresh query acceptance and G+ quality audit
   - run health, graph, and anchor checks when relevant
6. If no deterministic evidence changed, run or recommend `llm-wiki doctor` for a read-only confirmation.

Current deterministic passes:

- `drawio`: converts historical `.drawio` / `.dio` files into Mermaid-backed Markdown evidence and links that evidence from raw page indexes.
- `source_metadata`: patches existing `wiki/sources/*` with Delivery Tracking and Source Metadata without rewriting refined summaries.
- `cjira`: rebuilds `staging/cjira-registry/` from historical raw Jira/Cjira/IDEA signals.
- `agent_rules`: patches missing project query-routing rules.

Extensibility rule: future features that need to re-scan historical documents should become a new `tools/backfill.py` pass and feed `refinement_scope`, instead of being hidden inside query or doctor.

Do not:

- Treat backfill as a full rebuild.
- Rewrite `raw/` source text, except deterministic evidence-link sections managed by the backfill pass.
- Stop after deterministic backfill when new evidence changed source/G+ behavior; continue into refinement absorption unless blocked.
- Silently ignore Jira auth failures. Offline key extraction can continue, but status refresh blockers must be reported.

Final report:

- backfill passes run and changed counts
- source/raw/evidence pages in `refinement_scope`
- semantic absorption performed after backfill
- health / graph / G+ quality results
- blockers and remaining missing evidence

## `llm-wiki update-skill`

Purpose: update the installed llm-wiki skill bundle itself. Use only when the user explicitly asks to update the skill, skill bundle, installed skill, or global llm-wiki tooling.

Update source:

- The updater first prefers a local llm-wiki-skill bundle checkout, using that checkout's configured git upstream.
- If no local checkout can be inferred, the updater may clone the canonical GitLab source `https://git.guazi-corp.com/c2b-fe/llm-wiki.git` into `~/.cache/llm-wiki-skill/llm-wiki`, then install from that cached checkout.
- Override the fallback Git URL with `--git-url` or `LLM_WIKI_SKILL_GIT_URL`; override the cache parent with `--cache-dir` or `LLM_WIKI_SKILL_CACHE_DIR`.
- If GitLab credentials are missing, create a Personal Access Token at `https://git.guazi-corp.com/profile/personal_access_tokens` with the `read_repository` scope.
- A GitHub remote may exist as a mirror, but do not switch to it unless the user explicitly asks or the local checkout is configured that way.
- If the installed skill was copied and no source checkout can be inferred, use the GitLab cache fallback unless the user requested offline mode with `--no-download`.

Default behavior:

1. Prefer the bundled updater when available:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --client auto --backup
   ```

2. If the installed skill was copied and the updater cannot infer the source checkout, it clones/pulls the GitLab fallback. To force a known local bundle checkout:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --source /path/to/llm-wiki-skill --client auto --backup
   ```

3. The updater runs `git pull --ff-only` in the bundle checkout when it is a git worktree, then runs `install.sh` with backup semantics.
4. Do not use `--force` unless the user explicitly accepts discarding the previous installed copy.
5. After updating the installed skill, if the current directory is an LLM Wiki KB project and the user wants project tooling refreshed too, run:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
   ```

Stop when:

- No bundle checkout is available, GitLab clone/pull fails, and the user has not provided `--source`.
- `git pull --ff-only` fails because the bundle checkout has local conflicts or diverged history.
- installation reports destination conflicts without `--backup` or `--force`.

## `llm-wiki add-wiki`

Purpose: add another document/wiki directory or wiki URL to the current LLM Wiki as business or requirement evidence.

Use when:

- The user has another exported wiki, Markdown directory, Confluence export, live wiki URL, or document folder that should become part of `raw/`.
- The current project should answer questions across multiple document sources.
- The added material is business/requirement evidence, not source code.

Default order:

1. Read `BUSINESS_CONTEXT.md`, existing `docs/build-and-maintenance.md`, and current `staging/refinement-status.md`.
2. Inspect the provided source directory or wiki URL and identify its document unit pattern.
3. If the input is a live wiki URL, attempt deterministic RSS/feed discovery from URL structure and platform metadata.
4. If RSS/feed discovery succeeds, record the discovered RSS/feed URL in the same `upstream/wiki-sources.json` source object with the source provenance. Prefer `uv run python tools/discover_wiki_feeds.py --project "$PWD" --input upstream/wiki-sources.json --write-upstream` when doing deterministic feed discovery.
5. If RSS/feed discovery fails, explicitly tell the user that the RSS URL cannot be inferred, ask the user to manually provide the RSS URL, and explain that automatic future update work for that source cannot be completed without it. If the user does not provide one, leave the RSS/feed field empty.
6. If the user specifies page filters such as "only docs updated after YYYY-MM-DD", persist them under that source's `filters` object, e.g. `filters.updated_since`.
7. Confirm whether the input can be copied, linked, downloaded, or synced into `raw/`; do not rewrite or normalize source evidence in place.
8. Preserve provenance: original path, source URL when present, RSS/feed URL when known, RSS/feed status, imported_at, source collection name, and relationship role.
9. Place imported documents under a stable `raw/` subdirectory naming scheme that will not collide with existing page IDs.
10. Run the project update command when available, such as `uv run python tools/update_wiki.py`.
11. AI-native refine only affected source, concept, entity, and layered pages.
12. Run health and graph.

Stop for confirmation when:

- The user did not provide a source path or wiki URL.
- The input has ambiguous ownership or should not be copied into this project.
- The import would overwrite existing `raw/` directories.
- Canonical entity rules need to change to accommodate the new corpus.
- A live wiki URL needs automatic future updates but no RSS/feed URL can be inferred; ask for the manual RSS URL, and leave it empty if the user does not provide one.

Final report:

- source input: directory, export, document folder, or wiki URL
- import method: copied, linked, downloaded, synced, or blocked
- source URL, RSS/feed URL when known, and RSS/feed status: discovered, provided, missing, or not applicable
- imported document count
- affected wiki pages
- validation results
- remaining normalization or entity questions

## `llm-wiki add-code`

Purpose: add another project codebase under `raw-code/<codebase_id>/` and build or refresh the code wiki layer.

Use when:

- The user points to another local project, repo clone, or source tree.
- The project should answer implementation questions using that codebase.
- The added material is implementation evidence, not business requirements.

Default order:

1. Read `BUSINESS_CONTEXT.md` and existing `wiki/code/index.md` when present.
2. Inspect the provided code path, detect repo root, stack, entry points, docs, and whether it is a git repository.
3. Choose a stable `codebase_id` from the repo or directory name; ask only if it collides or is misleading.
4. Add the codebase under `raw-code/<codebase_id>/` as an engine-managed git checkout or git worktree. Do not mix it into `raw/`.
   - this is the only supported onboarding model
   - if repository access is missing, stop immediately and tell the user to obtain permission before retrying
5. Scan the codebase for README, AGENTS, OpenSpec, API contracts, routes, controllers, services, jobs, messages, data access, and config.
6. If `docs/wiki` is present, adapt upstream topics, concepts, and source maps before deciding whether graphify is needed.
7. Run graphify only if available and useful for structure evidence; otherwise record why it was skipped.
8. Create or update `wiki/code/codebases/<codebase_id>/`, candidate artifacts, and affected `wiki/code/capabilities/`.
8. If relevant requirements already exist, add or refresh `wiki/code/traceability/` rows with conservative evidence strength.
9. Run health and graph.

Stop for confirmation when:

- The source path is missing.
- The target `raw-code/<codebase_id>/` already exists.
- The current machine cannot read or clone the repository.
- The existing managed target is dirty and cannot be safely reused.

Final report:

- codebase_id
- repository source and managed checkout path
- detected stack and entry points
- pages created or updated
- capability and traceability coverage
- validation results
- missing evidence

## `llm-wiki doctor`

Purpose: read-only diagnosis and quality review of the whole LLM Wiki site. Use it when the user asks “现在状态如何”, “还缺什么”, “下一步干什么”, “这个 wiki 健康吗”, “帮我审查一下这个 wiki”, or wants a project-level operating recommendation.

Read:

1. `BUSINESS_CONTEXT.md`
2. `wiki/index.md`
3. `wiki/overview.md`
4. `docs/retrieval-playbook.md`
5. `docs/build-and-maintenance.md`
6. `staging/refinement-status.md`
7. `staging/health/latest.json`
8. `graph/summary.md`
9. `wiki/code/index.md`
10. `wiki/code/traceability/index.md`
11. `docs/query-acceptance.md`
12. `docs/gplus-quality-audit.md`
13. `staging/image-notes/` and `staging/refinement-status.md` image evidence fields when present

If any file is missing, report it as a signal. Do not create or modify files.

Optional read-only checks:

- Count `raw/*/index.md` and `wiki/sources/*.md`.
- Review entry usability, semantic consistency, source coverage, evidence strength, traceability quality, stale pages, health, and graph quality.
- Check G+ semantic thickness with the same heuristic used by update: source count vs non-index concept/entity pages, source-to-concept/entity coverage, manual concept/entity placeholders, index-only or low-density G+ layers, stale query acceptance / quality audit counts.
- Surface P0/P1/P2 findings directly in `主要问题`; do not require a separate `audit` command.
- Count image assets under `raw/**/assets/` and image notes under `staging/image-notes/`.
- When image assets exist without a completed image evidence pass, list prioritized image refinement candidate pages, using signals such as flow diagrams, state screenshots, money/account/risk/permission terms, launch tables, test conclusions, data tables, tracking, and pages already central to overview/concepts/query acceptance.
- Count generated prototype evidence notes under `raw/**/assets/*.prototype.md`; flag linked zip evidence that has no sidecar note.
- Count `wiki/code/codebases/*`, `wiki/code/capabilities/*.md`, and `wiki/code/traceability/*.md`.
- Inspect latest health status.
- Inspect graph node / edge counts.
- Search for broken or stale markers.
- If traceability pages exist, sample evidence strength distribution.
- If code anchors are used, recommend anchor check when not recently run.

Output shape:

```text
诊断类型：llm-wiki doctor
已使用 BUSINESS_CONTEXT.md：是/否
读取路径：

总体 verdict：

状态画像：
- 输入层：
- 文档层：
- 图片证据层：
- 代码层：
- 追踪矩阵：
- 校验层：
- 发布/维护状态：

主要问题：
- P0 ...
- P1 ...
- P2 ...

建议下一步：
1. ...
2. ...
3. ...
```

Verdict levels:

- `healthy`: health/graph pass, retrieval docs exist, source coverage complete, no urgent gaps.
- `usable-with-gaps`: wiki answers common questions but has traceability, code, image, or stale gaps.
- `needs-maintenance`: health/graph/staleness/coverage problems should be fixed before relying on it.
- `blocked`: missing required inputs or broken core structure.

Recommendation rules:

- If required inputs or entry docs are missing, recommend `llm-wiki init` or `llm-wiki update`.
- If source coverage or refinement is incomplete, recommend `llm-wiki update`.
- If query acceptance or quality audit artifacts are missing, recommend `llm-wiki update` to refresh them.
- If G+ semantic underfit is P1/P2, recommend `llm-wiki update` for Codex-native G+ semantic expansion. This is separate from health: a wiki can be structurally healthy and still need G+ expansion.
- If text/G+ is healthy but `raw/` contains image assets and no image evidence pass is recorded, recommend `llm-wiki image` for selective high-value multimodal refinement. Treat this as a non-blocking evidence gap unless core pages depend on diagrams, table screenshots, state screenshots, money/account/risk/permission flows, launch tables, or test conclusions.
- When recommending `llm-wiki image`, include the top candidate pages from health output or a read-only scan, not only the total image count.
- If code wiki exists but traceability is thin, recommend `llm-wiki update` for existing code evidence or `llm-wiki add-code` when a new codebase must be connected first.
- If files changed recently or stale markers exist, recommend `llm-wiki update`.
- If everything is healthy, say it is reasonable to pause and note what future change should trigger `llm-wiki update`.

## `llm-wiki review-requirement`

Purpose: review a new requirement with evidence from the target requirement, current business wiki, historical raw sources, optional code wiki, frontend requirement rules, images, and zip prototype packages.

Use when:

- The user provides a PRD, Cwiki URL, pageId, Markdown requirement file, exported document, or prototype package and asks for requirement review.
- The user asks whether a requirement is complete, implementable, consistent with history, or missing frontend / interaction details.
- The user wants comments suitable for posting back to Cwiki.

Required reads:

1. `BUSINESS_CONTEXT.md`
2. target `raw/**/index.md` or provided requirement file / URL
3. `docs/retrieval-playbook.md`
4. `wiki/overview.md`, `wiki/index.md`, and relevant `wiki/sources/`
5. relevant `wiki/concepts/`, `wiki/entities/`, `wiki/truth/`, `wiki/conflicts/`, `wiki/evidence/`, `wiki/proposals/`, `wiki/reference/`, and `wiki/operations/`
6. if present, `wiki/code/index.md`, `wiki/code/capabilities/`, and `wiki/code/traceability/`
7. frontend review rules: first read project-local `FE_REQ_REVIEW_SKILL.md` if it exists; otherwise read the bundled copy at `references/fe-req-review-skill.md` inside the llm-wiki skill package
8. if the requirement or project contains images, read nearby Markdown context and perform multimodal analysis of every requirement-relevant image
9. if the requirement or project contains zip files, inspect each relevant zip as a possible HTML prototype

Input handling:

- If the input is an existing `raw/**/index.md`, use it as the target requirement evidence.
- If the input is a Cwiki URL or pageId, extract the pageId and scan `raw/**/index.md` frontmatter for `page_id` and `source_url`.
- If the Cwiki page is not already in `raw/`, actively download or sync it into `raw/` before review when the project has a configured Cwiki/raw sync workflow. Preserve `page_id`, `source_url`, `title`, `space_key`, `version`, `updated_at`, `downloaded_at`, and `source_type` metadata when available.
- If the project has `tools/update_wiki.py`, run the deterministic update after raw sync, usually `uv run python tools/update_wiki.py`.
- Do not rewrite existing `raw/` pages by hand. If a same pageId exists with conflicting version metadata and no safe sync convention is documented, stop and ask before replacing evidence.
- If only a local Markdown or document path is provided, review it directly and, when appropriate, recommend `llm-wiki add-wiki` to preserve it as raw evidence.

Mandatory artifact analysis:

- Images are part of the requirement, not optional decoration. For each requirement-relevant image, capture:
  - where it appears and the surrounding text
  - visible UI, tables, flows, annotations, states, roles, data fields, and constraints
  - inferred requirement facts and what remains uncertain
  - conflicts between image content and text
- Zip files are likely prototype HTML. For each relevant zip:
  - list top-level files and detect HTML entry points, assets, scripts, routes, mock data, and README files
  - inspect HTML text, visible labels, forms, buttons, states, navigation, dialogs, tables, and validation hints
  - open locally only when needed for visual inspection; if starting a local server in a workspace where port collisions are common (e.g. many repos under one parent directory), run the local port registry guard before any dev/preview command
  - treat prototype behavior as evidence with provenance, and distinguish static prototype facts from implemented system facts

Frontend-specific review:

- If the project has frontend code, `wiki/code/` frontend pages, frontend routes, UI screenshots, HTML prototypes, or the requirement mentions pages, buttons, forms, dialogs, H5, app, web, mini program, console, portal, or user interaction, apply the frontend PRD review rules.
- The frontend rules must be applied by page dimension. Main pages count as pages; dialogs, drawers, upload boxes, overlays, and confirmation modals are reviewed inside their owning page.
- Required frontend dimensions: page states, interaction elements, boundary / exception conditions, and click / pageload tracking.
- If the project involves frontend but the requirement has no UI, interaction, page state, or frontend detail, add a prominent finding requiring the product owner to provide frontend scope, page inventory, interaction details, state definitions, and tracking requirements before development.
- If the requirement includes frontend details, judge whether the frontend logic is reasonable when combined with business rules, historical wiki evidence, code capabilities, prototype zip, and image evidence.
- Follow the frontend rule that "current code already has a reasonable implementation but PRD did not mention it" is not a frontend problem finding by itself. Put that only in review notes as: `代码已有实现，建议 PRD 补录与代码对齐`.

Review dimensions:

| Dimension | Checkpoints |
| --- | --- |
| Business baseline | Alignment with `BUSINESS_CONTEXT.md`, canonical entities, long-term product direction |
| User journey | Role, entry, conversion action, rights, upstream/downstream handoff |
| Historical rules | Conflicts with older PRDs, operations rules, experiments, truth/conflicts pages |
| State machine | Create, pending, success, failure, timeout, cancel, recover, retry, rollback |
| Money/accounting | Deduction, freeze, refund, negative balance, reconciliation, idempotency |
| Role/account model | Normal account, KA, parent-child account, store, group, external actor |
| Frontend scope | Pages, buttons, dialogs, disabled/loading/empty/error/success states, routes, tracking |
| Backend capability | API, service, job, message, table, external dependencies, existing gaps |
| Data migration | Old status, new status, compatibility, gray release, rollback |
| Notification/ops | Push, site message, announcement, help center, CS script, manual operation |
| Metrics/monitoring | Business harm, governance value, alerts, anomaly diagnosis, rollback guard |

Findings-first output:

Start with the issues, then context. Use P0/P1/P2:

- P0: unresolved ambiguity blocks unique implementation, creates accounting/rule errors, or carries severe business risk.
- P1: unresolved issue causes inconsistent experience, test ambiguity, operational explanation risk, or frontend flow gaps.
- P2: useful enhancement, monitoring, copy, gray rollout, or documentation alignment.

Each finding must include:

```text
标题：
等级：
证据：
影响：
建议决策：
是否阻塞开发：
```

Full report shape:

```text
一、结论
二、证据范围
三、全局定位
四、前后变化
五、MECE 影响范围
六、P0/P1/P2 问题
七、前端需求完整性审查
八、图片与 zip 原型证据
九、建议目标模型
十、验收清单
十一、指标护栏
十二、待决问题
十三、证据链接
十四、Cwiki 评论版
十五、建议下一步
```

The evidence scope must state:

```text
查询类型：需求评审
已使用 BUSINESS_CONTEXT.md：是/否
目标需求：
raw 状态：已存在 / 本次下载 / 只读外部页面 / 本地文件
图片证据：无 / 已分析 N 个 / 存在但无法读取
zip 原型：无 / 已分析 N 个 / 存在但无法解压或识别入口
前端评审：不涉及 / 已按 FE_REQ_REVIEW_SKILL.md 执行 / 涉及前端但需求缺失
代码证据：未使用 / 已使用 wiki/code / 代码缺失
检索路径：
1. BUSINESS_CONTEXT.md
2. 目标 raw/source 页面
3. concepts/entities
4. conflicts/evidence/proposals/truth/reference
5. 相关历史 sources
6. wiki/code/capabilities
7. wiki/code/traceability
8. 图片与 zip 原型证据
```

Cwiki comment draft:

- Produce a concise Cwiki-friendly comment after the full report.
- Use original Cwiki links for source evidence when available.
- Do not include local paths such as `/Users/...`, `raw/...`, or `wiki/sources/...` in the comment draft.
- Code evidence may be described as "本地代码证据显示", but local paths are only allowed in the full local report, not in the Cwiki comment draft.
- Before offering the comment draft, scan it for local paths and report the scan result.
- Publishing comments is opt-in. If the user explicitly asks to publish, dry-run first with target pageId, title, comment length, link count, and local-path scan result, then publish only when the user's wording clearly authorizes it.

Final report:

- lead with P0/P1/P2 findings
- include exact evidence links or local file references in the full report
- include the frontend per-page review section when frontend is involved
- include image and zip prototype evidence summaries when present
- include a Cwiki-safe comment draft when a source Cwiki URL exists
- end with `建议下一步`

## Other Commands

### `llm-wiki init`

Use the same early stages as `fast`, but stop after the initialized baseline and first-pass plan if the user wants phased work.

When the user supplies a **Confluence/Cwiki URL** (`pageId=`) as the evidence source: install the bundled template (includes **`tools/confluence_sync/`**), run **`uv sync`**, then run **`uv run python tools/confluence_sync/export_obsidian_wiki.py`** with `--project-dir` so pages land under **`raw/<pageId>-<slug>/`**. Sync metadata defaults to **`staging/wiki-export-state/`**, not inside `raw/`. See `references/bootstrapping.md` section「从 wiki URL 拉取 raw」.

### `llm-wiki doctor`

Read-only project status diagnosis and quality review. Never edit files. End with prioritized next commands.

### `llm-wiki add-wiki`

Add another document/wiki directory into the project evidence layer. Preserve provenance, avoid overwriting `raw/`, then run update, health, and graph.

### `llm-wiki add-code`

Add another project codebase as `raw-code/<codebase_id>/`. Build codebase pages, endpoint maps, upstream docs/wiki adapters when present, capability/anchor candidates, optional graphify output, and traceability when relevant.

### `llm-wiki query`

State query type, retrieval path, conclusion, supporting pages, unresolved points, and evidence class.

Default behavior:

- If the question is about business knowledge, product rules, 需求口径, terminology, operations, or document facts, answer from `BUSINESS_CONTEXT.md` and business/requirement wiki layers. Do not include detailed code evidence, code paths, endpoints, services, controllers, classes, tables, jobs, or implementation traces unless they are necessary to avoid a wrong answer.
- If the question is about code implementation, architecture, APIs, source locations, call chains, frontend/backend mapping, testing, or whether a requirement has landed in code, use `wiki/code/` normally.
- If the question is ambiguous, prefer the business-only path and mention that `llm-wiki query-plus` can be used for a full business+code answer.

Read `references/query-logic.md` before answering.

### `llm-wiki query-plus`

Answer with both business/requirement evidence and code implementation evidence. Use this when the user explicitly wants a fuller answer that connects business口径, requirement evidence, implementation status, traceability, and gaps.

Required behavior:

- Read `BUSINESS_CONTEXT.md`, relevant business/requirement wiki layers, and relevant `wiki/code/` layers.
- Distinguish business conclusions, code implementation facts, inferred links, and missing evidence.
- Preserve traceability evidence strength (`strong`, `partial`, `inferred`, `external`, `missing`) and do not upgrade inferred graph or matrix links into source facts.
- Be more detailed than ordinary `query` when useful, but keep the answer organized around the user's question.

Read `references/query-logic.md` before answering.

### `llm-wiki review-requirement`

Review a target PRD or Cwiki page against raw/wiki/code evidence. Include mandatory image multimodal analysis, zip prototype inspection, frontend PRD review via `FE_REQ_REVIEW_SKILL.md`, findings-first issues, acceptance checklist, metric guards, unresolved questions, and a Cwiki-safe comment draft when applicable.

### `llm-wiki image`

Only after text completion or explicit user request. Follow `image-evidence.md`.
Start by inventorying candidate pages and images, then process only high-value evidence by default.
For whole-project, multi-page, or large image scopes, use subagents by default when available. Split by source page or related page bundles, keep each worker's write scope under a unique `staging/image-notes/<source-page-id>/` directory, and let the main agent own final wiki integration, health/graph, and `staging/refinement-status.md`.
Update `staging/refinement-status.md` with `image_evidence_status` and a concise checkpoint.
