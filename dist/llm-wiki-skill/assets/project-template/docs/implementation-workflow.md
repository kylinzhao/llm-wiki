# Implementation Workflow

## 0-1 Build

1. Put static source documents in `raw/`, or declare live wiki/RSS sources in `upstream/wiki-sources.json`.
2. Put business context in `BUSINESS_CONTEXT.md`.
3. If the project needs code evidence, add repositories only through `llm-wiki add-code` so each codebase becomes an engine-managed git checkout under `raw-code/<codebase_id>/`.
4. Run deterministic seed:

```bash
uv run python tools/update_wiki.py
```

`upstream/wiki-sources.json` is the single source of truth for upstream wiki relationships. It stores the 0-1 root wiki, later added wiki sources, relationship role, depth, RSS URL, output/metadata paths, and filters such as `filters.updated_since`.

`upstream/code-sources.json` is the single source of truth for code repositories added by `llm-wiki add-code`. It records enough repository metadata to restore `raw-code/<codebase_id>/` as an engine-managed git checkout on another machine.

Evidence cache mapping:

- `upstream/wiki-sources.json` -> `raw/`
- `upstream/code-sources.json` -> `raw-code/`
- `llm-wiki update` -> shared by default
- `llm-wiki update --local` or `LLM_WIKI_UPDATE_MODE=local` -> local-only trial

If `upstream/wiki-sources.json` contains enabled Cwiki or RSS sources, update should first refresh `raw/` automatically. Legacy `config/rss-feeds.yaml` is only a migration input.

If `raw-code/<codebase_id>/` contains engine-managed clean git checkouts, the same update command should refresh them by default with `git pull --ff-only` before raw/wiki/staging outputs are generated, and before `scan_code.py` and `build_traceability.py`. If access is missing, the checkout is broken, or the worktree is dirty, shared update must stop before generating KB outputs and tell the operator to repair the managed raw-code entry first.

In shared mode, `raw/` and `raw-code/` remain ignored local evidence caches. They must not be committed as regular files, git submodules, or gitlinks (`mode 160000`). Code repositories belong in `upstream/code-sources.json` and are restored as engine-managed git checkouts under `raw-code/<codebase_id>/` by `llm-wiki add-code` / `tools/migrate_raw_code.py --apply`, not as KB submodules. The publish step must commit only the shared KB baseline outputs and engine-owned `tools/**` files refreshed from the installed skill template, and must exclude evidence caches, secrets, logs, dependencies, and other unrecognized local files. `--no-auto-raw-sync` is valid only for explicit local mode; shared mode must reject it before any update work starts.

If KB git pull/push or managed code checkout pull fails because of permissions, report the failure in Chinese and tell the operator to request KB/code repository access or check SSH Key / Git credentials. For raw-code permission failures, do not publish a shared baseline built without code evidence; ask the operator to fix access or explicitly switch to local mode for a local-only trial, then rerun local preflight before continuing.

Semantic refinement gaps are not shared-publish blockers. If health, graph, and required anchor checks pass, publish the shared baseline as `usable-with-gaps` and record the remaining refinement/image evidence work for the next update pass.

For temporary clone smoke tests, set `LLM_WIKI_UPDATE_MODE=local` with `LLM_WIKI_CWIKI_SMOKE_MAX_PAGES=<n>` or `LLM_WIKI_CWIKI_SMOKE_RSS_MAX_RESULTS=<n>` to exercise Cwiki login/download without crawling the full tree. These limits are rejected in shared mode so a truncated `raw/` cache cannot be committed as a shared baseline.

5. Use Codex to complete AI-native refinement of:

- `wiki/sources/`
- `wiki/concepts/`
- `wiki/entities/`
- `wiki/truth/`
- `wiki/conflicts/`
- `wiki/evidence/`
- `wiki/proposals/`
- `wiki/reference/`
- `wiki/operations/`
- `wiki/code/capabilities/`
- `wiki/code/traceability/`

6. Finish with `llm-wiki update` style validation and closure: health, graph, and anchor checks are part of the same command, not separate user-facing steps.

## Code Wiki

For code evidence:

The engine may still use deterministic code scanning and graphification internally, but users should continue to think in terms of `llm-wiki update` rather than manual script chains.

`scan_code.py` provides deterministic facts. `graphify_code.py` provides graph structure. Agent / reviewer work may write business capability interpretation. Traceability model work must use `docs/traceability-contract.md` and write proposals under `staging/traceability/runs/<run_id>/`; deterministic tooling owns the long-lived state and Markdown rendering.

To refresh code before rebuilding code wiki, use `llm-wiki update`. The engine should refresh only managed raw-code checkouts and should not expose alternate per-codebase sync modes.
