# Commands

# Commands

Use this reference when the user invokes a `llm-wiki` subcommand or when the request maps clearly to one command.

# Shared command protocol

## Command Router

| Command | Use When | Primary Output |
| --- | --- | --- |
| `llm-wiki fast` | New project, user wants the standard path completed in one run | Full first-pass wiki, refinement, validation, status |
| `llm-wiki init` | New project, user wants phased initialization | Skeleton, deterministic build, first-pass plan |
| `llm-wiki doctor` | User wants site status, diagnosis, quality review, or prioritized recommendations | Findings plus health portrait and next steps |
| `llm-wiki version` | User asks for the llm-wiki skill / bundle version, current version, skill version, or engine version | Installed skill bundle version from `VERSION` |
| `llm-wiki update` | Existing KB needs resume, refinement, traceability refresh, source/code updates, or validation after changes | Impact-scoped update, validation, and maintenance report |
| `llm-wiki refine` | User explicitly asks to refine source/concept/entity/wiki semantics without waiting for another input change | Agent-native semantic refinement, validation, and shared publish |
| `llm-wiki backfill` | Existing KB was built with older skill versions and needs historical evidence re-scanned | Deterministic evidence backfill, then refinement absorption through update semantics |
| `llm-wiki maintain-all` | User wants to discover, list, prune, or batch-maintain local registered KB projects | Dry-run plan by default; optional apply runs full backfill/update maintenance per KB |
| `llm-wiki update-skill` | User explicitly asks to update the llm-wiki skill bundle itself, not the current KB content | Pull/reinstall the installed skill bundle, then optionally refresh project tooling |
| `llm-wiki add-wiki` | Add another document/wiki directory or wiki URL as business or requirement evidence | Imported raw evidence, source provenance, RSS/update status, and affected wiki updates |
| `llm-wiki add-code` | Add or refresh implementation evidence, code wiki, capabilities, and traceability | raw-code codebase plus code wiki and mappings |
| `llm-wiki query` | Answer a business or implementation question; business-only questions should not include detailed code evidence by default | Evidence-grounded answer with intent-based evidence scope |
| `llm-wiki query-plus` | Answer with business/requirement evidence and code implementation evidence together | Detailed business+code evidence analysis |
| `llm-wiki review-requirement` | KB-enhanced requirement review: gather wiki/raw/code evidence, run upstream `prd-review-max`, append impact scope and historical conflicts | Findings-first review and Cwiki comment draft |
| `llm-wiki image` | Add high-value image evidence after text completion | image notes and linked facts |

## Skill Version Queries

When the user asks for the llm-wiki skill / bundle version, current version, skill version, or engine version through `llm-wiki`, `/llm-wiki`, `llm-wiki query`, `/llm-wiki query`, `$llm-wiki-query`, or `/llm-wiki-query`, treat it as a skill metadata request, not as a KB query.

Read `VERSION` from the llm-wiki skill package root and answer from that file:

- `version`: llm-wiki skill bundle version.
- `engine_version`: bundled project template / deterministic tooling contract version.

If `VERSION` is missing, fall back to `manifest.json` in the same directory when available and report its `version`; state clearly that `engine_version` is not declared in that fallback.

## Evidence preflight (partial clone / git without raw)

Many teams **commit the built `wiki/`** but keep `raw/` and `raw-code/` as **ignored local evidence caches** restored from `upstream/wiki-sources.json` and `upstream/code-sources.json`. Shared KB must **not** commit `raw-code/` as git submodules or gitlinks; that layout fails shared preflight with `evidence_cache_tracked_failed`. Legacy submodule layouts should be migrated with `uv run python tools/migrate_raw_code.py --apply` before shared update. When evidence caches are missing locally (sparse checkout, fresh clone), deterministic tools **block rebuild/update** until `raw/` / managed `raw-code/` checkouts are restored.

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
- **Drawio completion rule**: `drawio_repair.py` is a deterministic pipeline that auto-converts `.drawio` XML to `.drawio.md` Markdown during every update. When `drawio_repair.missing_evidence_count == 0`, drawio is fully converted and must **not** appear in `建议下一步` or any recommendation. Only mention drawio when `missing_evidence_count > 0`. Never conflate drawio status with screenshot/photo image evidence status.
