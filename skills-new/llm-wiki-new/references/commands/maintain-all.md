## `llm-wiki-new maintain-all`

Purpose: maintain local registered LLM Wiki KB projects in batches without silently modifying every KB after a skill upgrade.

Registry:

- Local KBs are tracked in `~/.llm-wiki-new/projects.json`.
- Project template install, project-local update, and project-local backfill register the current KB best-effort.
- The registry stores paths and maintenance status only; it must not store credentials, cookies, tokens, or KB evidence content.

Common commands:

```bash
python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/maintain_all.py" --discover /Users/zhaoliang/guazi/work
python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/maintain_all.py" --list
python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/maintain_all.py" --prune-missing
python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/maintain_all.py" --apply
```

Behavior:

1. Default invocation is dry-run only. It prints which active KBs would be maintained, which KBs are skipped, and which commands would run.
2. `--discover <dir>` scans for KBs and adds them to the registry before planning.
3. `--list` prints current registry rows.
4. `--prune-missing` immediately removes registry entries whose paths no longer exist. Ordinary reconcile removes entries automatically after `missing_count >= 3`.
5. `--apply` is required before any KB files are modified.
6. Apply runs the full backfill maintenance flow for each planned KB:
   - refresh engine-owned tools and agent rules
   - run `uv run python tools/backfill.py`, falling back to `python3 tools/backfill.py` only when needed
   - when backfill reports `refinement_absorption_required=true`, run project update to absorb evidence and complete health/graph closure
7. A failed KB does not stop later KBs. The batch report records success, skip, and failure details.

Safety boundaries:

- Do not run `--apply` against real KBs unless the user explicitly asks to execute.
- Do not add `--no-auto-raw-sync` to bypass Cwiki auth. Auth failures are per-KB blockers.
- Dirty KB git worktrees are skipped with `dirty_project_worktree` by default.
- Broken managed `raw-code/` checkouts remain hard failures under normal update rules.
- The command does not commit or push KB changes.

Reports:

- Batch reports are written under `~/.llm-wiki-new/maintenance-runs/<run_id>.json` and `.md`.
- Final user reporting must include counts for successes, skipped projects, failures, pruned missing entries, and report paths.
