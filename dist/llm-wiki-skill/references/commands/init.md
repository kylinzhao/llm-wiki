## `llm-wiki init`

Use the same early stages as `fast`, but stop after the initialized baseline and first-pass plan if the user wants phased work.

When the user supplies a **Confluence/Cwiki URL** (`pageId=`) as the evidence source: install the bundled template (includes **`tools/confluence_sync/`**), run **`uv sync`**, then run **`uv run python tools/confluence_sync/export_obsidian_wiki.py`** with `--project-dir` so pages land under **`raw/<pageId>-<slug>/`**. Sync metadata defaults to **`staging/wiki-export-state/`**, not inside `raw/`. See `references/bootstrapping.md` section「从 wiki URL 拉取 raw」.
