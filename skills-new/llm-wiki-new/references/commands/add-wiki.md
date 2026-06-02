## `llm-wiki-new add-wiki`

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
