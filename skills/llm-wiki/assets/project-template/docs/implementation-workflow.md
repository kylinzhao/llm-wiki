# Implementation Workflow

## 0-1 Build

1. Put source documents in `raw/`.
2. Put business context in `BUSINESS_CONTEXT.md`.
3. Optionally put source repositories under `raw-code/<codebase_id>/`.
4. Run deterministic seed:

```bash
uv run python tools/update_wiki.py
```

If `config/rss-feeds.yaml` already contains enabled feed URLs, this update command should first refresh `raw/` through `tools/rss_sync.py` automatically.

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

6. Run validation:

```bash
uv run python tools/health.py --json
uv run python tools/build_graph.py
uv run python tools/anchor_check.py
```

## Code Wiki

For code evidence:

```bash
uv run python tools/scan_code.py
uv run python tools/graphify_code.py --all
uv run python tools/build_traceability.py
```

`scan_code.py` provides deterministic facts. `graphify_code.py` provides graph structure. Codex must still write the business capability interpretation.

To force a one-off code refresh across all codebases before rebuilding code wiki:

```bash
uv run python tools/update_wiki.py --code-sync-command git pull --ff-only
```
