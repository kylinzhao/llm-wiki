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

If `upstream/wiki-sources.json` contains enabled Cwiki or RSS sources, this update command should first refresh `raw/` automatically. Legacy `config/rss-feeds.yaml` is only a migration input.

If `raw-code/<codebase_id>/` contains engine-managed clean git checkouts, the same update command should refresh them by default with `git pull --ff-only` before `scan_code.py` and `build_traceability.py`. If access is missing, the checkout is broken, or the worktree is dirty, update must stop and tell the operator to repair the managed raw-code entry first.

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
