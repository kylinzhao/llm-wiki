# Implementation Workflow

## 0-1 Build

1. Put static source documents in `raw/`, or declare live wiki/RSS sources in `upstream/wiki-sources.json`.
2. Put business context in `BUSINESS_CONTEXT.md`.
3. Optionally put source repositories under `raw-code/<codebase_id>/`.
4. Run deterministic seed:

```bash
uv run python tools/update_wiki.py
```

`upstream/wiki-sources.json` is the single source of truth for upstream wiki relationships. It stores the 0-1 root wiki, later added wiki sources, relationship role, depth, RSS URL, output/metadata paths, and filters such as `filters.updated_since`.

If `upstream/wiki-sources.json` contains enabled Cwiki or RSS sources, this update command should first refresh `raw/` automatically. Legacy `config/rss-feeds.yaml` is only a migration input.

If `raw-code/<codebase_id>/` contains clean git worktrees, the same update command should also refresh them by default before `scan_code.py` and `build_traceability.py`. If a codebase needs a non-default refresh flow, configure `kb.manifest.yaml` `overrides.raw_code_update_commands`.

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

`scan_code.py` provides deterministic facts. `graphify_code.py` provides graph structure. Codex must still write the business capability interpretation.

To force a one-off code refresh across all codebases before rebuilding code wiki:

Use `llm-wiki update` for the normal end-to-end pass; only the engine should decide when it needs to invoke a specific sync command under the hood.
