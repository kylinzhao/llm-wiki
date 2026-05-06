# Tooling Dependencies

## Required

- Python 3.10+
- `uv` for the documented command style

The bundled project scripts use only the Python standard library. They do not call local model SDKs.

## Optional: upstream wiki RSS/feed discovery

Live wiki sources can be declared in:

```text
upstream/wiki-sources.json
```

Supported shape:

```json
{
  "sources": [
    {
      "source_url": "https://wiki.example.com/pages/viewpage.action?pageId=123",
      "rss_url": ""
    }
  ]
}
```

When this file exists, `uv run python tools/update_wiki.py` runs feed discovery and verification first:

```bash
uv run python tools/discover_wiki_feeds.py --input upstream/wiki-sources.json
```

The check writes:

```text
staging/wiki-feeds/latest.json
staging/wiki-feeds/latest.md
```

Only `discovered_verified` and `provided_verified` are valid for automatic wiki updates. Missing, unreachable, auth-required, invalid, unverified, or empty feeds must be reported to the user; if the user does not provide a working RSS/feed URL, leave the field empty and do not claim automatic updates for that source.

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
