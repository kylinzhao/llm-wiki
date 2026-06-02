## `llm-wiki fast`

Purpose: one-shot standard build for a new project. Use when the user wants the whole first-pass workflow completed without repeated planning prompts.

Read:

1. `BUSINESS_CONTEXT.md`
2. `raw/`
3. this skill's `bootstrapping.md`
4. this skill's `build-and-maintenance.md`
5. if `raw-code/` exists, `code-wiki.md`

Run order:

1. Validate `raw/` and `BUSINESS_CONTEXT.md`.
2. Install the bundled project template unless equivalent scripts already exist: after bundle install, use your client's skills root (for example Codex: `python3 "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"`), or use `python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"` when the package lives elsewhere (see main `SKILL.md` "Skill 包路径").
3. Run deterministic build with `uv run python tools/update_wiki.py`.
   - when the standard template is installed, this command should auto-refresh enabled RSS/feed raw inputs and engine-managed `raw-code/<codebase_id>/` git checkouts before rebuilding deterministic code outputs
4. If `raw-code/` exists, run the code scan and candidate pipeline first. If a complete `raw-code/<codebase_id>/docs/wiki` exists, use it with scan anchors as the preferred first-pass code navigation layer. Run `uv run python tools/graphify_code.py --all` only when structural graph evidence is missing, stale, explicitly requested, or needed for call/dependency questions.
5. Complete first-pass source summary and AI-native refinement.
6. Build layered pages, concepts, entities, truth, conflicts, evidence, proposals, reference, operations.
7. If `raw-code/` exists, refine codebase indexes, capability pages, and traceability evidence strengths.
8. If implementation review is in scope, create traceability pages for highest-value capabilities.
9. Run G+ readiness checks when feasible: query acceptance and quality audit. For 0-1 builds this is part of the default path, not an optional follow-up: complete concepts/entities/truth/conflicts/evidence/proposals/reference/operations calibration unless a hard blocker appears or the user explicitly asks to stop after the baseline.
10. Inventory raw image assets and image-note status. Do not batch-analyze images by default, but if images exist and no image evidence pass is complete, record phase H as pending and recommend `llm-wiki image`.
11. Include deterministic text sidecars generated from `.zip` prototype attachments in source summary and refinement scope. Treat the sidecar Markdown as source evidence with provenance; do not treat binary zip files or extracted prototype assets as standalone system facts.
12. Run health, graph, and anchor check.
13. Update `staging/refinement-status.md`.

Default behavior:

- Proceed automatically through low-risk steps.
- Use subagents for large independent batches when available.
- Do not process low-value images.
- Do not submit or push unless the user explicitly asks for git publishing and the remote is clear.

Stop only when:

- `raw/` is missing.
- `BUSINESS_CONTEXT.md` is missing, empty, or still contains the bundled TODO placeholder.
- canonical entity rules need business confirmation.
- generated output would overwrite existing manual or refined wiki content.
- secrets or sensitive configs would be exposed.

Final report:

- phase completed
- files created / updated
- codebases included
- traceability coverage
- image evidence status: not applicable / pending high-value screening / complete / skipped by user
- validation results
- blocked items
- recommended next pass
