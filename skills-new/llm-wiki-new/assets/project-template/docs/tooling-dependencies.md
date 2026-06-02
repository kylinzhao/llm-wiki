# Tooling Dependencies

## Required

- Python 3.10+
- `uv` for the documented command style

Most bundled wiki-build scripts use only the Python standard library (plus PyYAML where noted). They do not call local model SDKs.

The optional **`tools/confluence_sync/`** Confluence exporters require **`requests`** and **`beautifulsoup4`** (declared in `pyproject.toml`). Install with `uv sync` before running wiki download commands.

## Optional: graphify

`graphify` is used only when `raw-code/` exists and code graph extraction is useful. If a codebase already provides a complete `docs/wiki` upstream code-intelligence layer, the default path is to adapt that layer plus deterministic scan anchors first; graphify is then a low-frequency structural enhancer, not a mandatory update step.

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

The deterministic code-side pipeline may also write compact staging files:

```text
staging/code-graph/<codebase_id>/freshness.json
staging/code-graph/<codebase_id>/upstream-topics.json
staging/code-graph/<codebase_id>/upstream-concepts.json
staging/code-graph/<codebase_id>/upstream-source-map.json
staging/code-graph/<codebase_id>/capability-candidates.json
staging/code-graph/<codebase_id>/anchor-candidates.json
staging/code-graph/<codebase_id>/structure-summary.json
```

Old projects without these files remain valid; tools should degrade to manifest, endpoint-map, and traceability-candidates behavior.

## Capability Boundary

- Scripts scan files, compare hashes, detect project shape, seed Markdown, validate links, and build graph files.
- Agent / reviewer work may perform source summaries, concept/entity normalization, and capability judgment. Requirement-code matching and evidence strength assignment must be backed by deterministic candidates or direct audited evidence. When model work is used for traceability, it must follow `docs/traceability-contract.md` and emit structured proposals for deterministic merge.
