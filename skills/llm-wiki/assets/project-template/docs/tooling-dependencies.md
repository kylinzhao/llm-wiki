# Tooling Dependencies

## Required

- Python 3.10+
- `uv` for the documented command style

Most bundled wiki-build scripts use only the Python standard library (plus PyYAML where noted). They do not call local model SDKs.

The optional **`tools/confluence_sync/`** Confluence exporters require **`requests`** and **`beautifulsoup4`** (declared in `pyproject.toml`). Install with `uv sync` before running wiki download commands.

## Optional: graphify

`graphify` is used only when `raw-code/` exists and code graph extraction is useful.

Expected command:

```bash
graphify update raw-code/<codebase_id>
```

The wrapper archives output under:

```text
staging/code-graph/<codebase_id>/graphify-out/
```

Install or expose `graphify` on `PATH` before running:

```bash
uv run python tools/graphify_code.py --all
```

If `graphify` is missing or fails, the wrapper records `skipped` or `failed` status and the wiki build should continue with deterministic code scanning.

## Capability Boundary

- Scripts scan files, compare hashes, detect project shape, seed Markdown, validate links, and build graph files.
- Codex performs source summaries, concept/entity normalization, capability judgment, requirement-code matching, and evidence strength assignment.
