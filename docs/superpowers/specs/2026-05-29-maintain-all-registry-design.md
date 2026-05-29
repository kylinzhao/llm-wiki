# Maintain-All Registry Design

Date: 2026-05-29
Status: Draft approved in brainstorming
Scope: local KB project registry, discovery, pruning, and batch `llm-wiki backfill` maintenance

## Summary

This design adds a local registry of LLM Wiki KB projects and a batch maintenance command that can apply the full `llm-wiki backfill` semantic flow across registered KBs.

The command is intentionally explicit:

- KB projects are recorded in `~/.llm-wiki/projects.json`.
- Existing projects can be found with `--discover <dir>`.
- The default batch command is a dry run that prints a plan.
- `--apply` is required before any project is modified.
- Each selected KB runs the same high-level flow as `llm-wiki backfill`: refresh engine-owned tools and agent rules, run deterministic backfill, then continue into update/health/graph closure when required.

The goal is to remove the current per-project manual upgrade burden without making skill upgrades silently rewrite every KB on the machine.

## Problem

`llm-wiki-skill` ships engine-owned project tools under each KB project. When the installed skill is upgraded, old KB projects still contain their previously copied `tools/` and agent rules until each project is refreshed.

That makes fixes and new deterministic backfill passes awkward to roll out:

- upgrading the installed skill does not automatically update existing KB project tools
- users must remember which KBs exist locally
- each KB must be entered and backfilled manually
- old projects can continue showing fixed bugs because their project-local tool copy is stale

Automatically backfilling all KBs after every skill upgrade would be too aggressive. A full backfill/update can trigger Cwiki sync, Jira status refresh, raw-code `git pull --ff-only`, health checks, graph rebuilds, and many local file changes.

The missing piece is a controlled local inventory plus an explicit batch maintenance command.

## Goals

- Track local KB projects in a durable machine-local registry.
- Let historical KB projects be discovered from a workspace directory.
- Provide one explicit command that performs full `llm-wiki backfill` semantics across many KBs.
- Default to dry-run planning so the user can see impact before file changes or network work.
- Prune registry entries for KB paths that no longer exist.
- Keep project failures isolated so one broken KB does not prevent other KBs from being maintained.
- Write machine-readable and human-readable summary reports for the batch run.

## Non-Goals

- Automatically running batch backfill as a side effect of skill installation or upgrade.
- Creating a daemon, scheduler, or background auto-updater.
- Rebuilding raw evidence from scratch.
- Committing KB changes to git or pushing any branches.
- Treating missing auth, dirty worktrees, or broken managed raw-code checkouts as silent skips.
- Maintaining a shared remote registry. The registry is local to one computer.

## Design

## 1. Local Project Registry

The registry lives at:

```text
~/.llm-wiki/projects.json
```

It records KB projects known to this machine. The file is not part of any KB repository and must not store secrets.

### 1.1 Registry Shape

Recommended top-level shape:

```json
{
  "version": 1,
  "projects": [
    {
      "path": "/Users/zhaoliang/guazi/work/dcn-llm-wiki",
      "name": "dcn-llm-wiki",
      "first_seen_at": "2026-05-29T10:00:00+08:00",
      "last_seen_at": "2026-05-29T10:00:00+08:00",
      "last_success_at": "",
      "status": "active",
      "missing_count": 0,
      "last_error": ""
    }
  ]
}
```

Required project fields:

- `path`: absolute project root path
- `name`: display name, defaulting to the final path segment
- `first_seen_at`: first time this machine registered the project
- `last_seen_at`: latest time the path was observed as an LLM Wiki project
- `last_success_at`: latest successful batch maintenance completion
- `status`: `active`, `missing`, or `failed`
- `missing_count`: consecutive reconcile runs where the path did not exist
- `last_error`: short latest error summary, empty on success

### 1.2 Registration Events

The following local operations should register the current project:

- `install_project_template.py --project <path>`
- project-local `tools/update_wiki.py`
- project-local `tools/backfill.py`
- future `maintain-all --discover <dir>`

Registration is best-effort. If the registry cannot be written, the command should warn but not fail the current KB operation.

### 1.3 Identity Rule

The canonical project identity is the resolved absolute path.

If the same path is discovered again:

- keep the original `first_seen_at`
- refresh `name` if it was previously empty
- set `last_seen_at` to now
- set `status=active`
- reset `missing_count=0`

If a KB is moved to a different path, it is treated as a new project. The old path is pruned through the missing-entry policy.

## 2. Discovery

The batch command supports:

```bash
llm-wiki maintain-all --discover /Users/zhaoliang/guazi/work
```

Discovery scans the supplied root for directories that look like LLM Wiki KB projects.

### 2.1 KB Detection

A directory should be considered a KB project when it contains enough stable KB markers, such as:

- `BUSINESS_CONTEXT.md`
- `kb.manifest.yaml`
- `wiki/`
- `staging/`
- `tools/update_wiki.py`

Recommended detection rule:

- strong match: `kb.manifest.yaml` and `tools/update_wiki.py`
- compatible legacy match: `BUSINESS_CONTEXT.md`, `wiki/`, and `staging/`

Discovery should avoid descending into heavyweight or generated directories:

- `.git`
- `.venv`
- `node_modules`
- `raw`
- `raw-code`
- `wiki`
- `staging`
- `.worktrees`
- `worktrees`

### 2.2 Discovery Output

Discovery updates the registry and prints:

- newly registered KBs
- already known KBs
- ignored candidate directories and why, when useful
- missing entries pruned or marked during reconcile

Discovery alone does not run backfill unless `--apply` is also supplied.

## 3. Missing-Entry Reconcile and Pruning

Every `maintain-all` run starts by reconciling the registry.

### 3.1 Existing Paths

If a registered path exists and still looks like a KB:

- set `status=active`
- set `missing_count=0`
- refresh `last_seen_at`

If a registered path exists but no longer looks like a KB:

- keep the entry
- set `status=failed`
- set `last_error` to a concise detection failure
- skip it in batch apply

### 3.2 Missing Paths

If a registered path no longer exists:

- set `status=missing`
- increment `missing_count`
- skip it in batch apply

After `missing_count >= 3`, automatically remove the entry from the registry.

### 3.3 Manual Prune

The command supports:

```bash
llm-wiki maintain-all --prune-missing
```

This immediately removes entries whose paths do not exist, regardless of `missing_count`.

### 3.4 List

The command supports:

```bash
llm-wiki maintain-all --list
```

It prints the registry in a concise table:

- status
- missing count
- last success time
- path
- latest error when present

## 4. Batch Maintenance Command

The primary command is:

```bash
llm-wiki maintain-all
```

Default behavior is dry-run planning. No project files are modified unless `--apply` is present.

### 4.1 Dry-Run Plan

The dry-run plan lists:

- active KBs that would be maintained
- missing KBs that would be skipped
- failed/invalid KBs that would be skipped
- commands that would run per KB
- detected blockers that can be found without modifying the project

The plan should be enough for a user to decide whether to run:

```bash
llm-wiki maintain-all --apply
```

### 4.2 Apply Flow

For each selected active KB, `--apply` runs the full `llm-wiki backfill` semantic flow:

1. Refresh engine-owned tools and agent rules from the installed skill:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$KB" --engine-only --refresh-agent-rules
   ```

2. Run deterministic backfill from the KB root:

   ```bash
   uv run python tools/backfill.py
   ```

   If `uv` is unavailable and dependencies are already satisfied, fall back to:

   ```bash
   python3 tools/backfill.py
   ```

3. Read `staging/backfill/latest.json` and `latest.md`.
4. If `refinement_absorption_required=true`, continue with the existing `llm-wiki backfill` semantic absorption:
   - refresh affected `wiki/sources/*`
   - refresh related concepts/entities and G+ pages
   - run update, health, graph, and anchor checks as required by the current backfill protocol
5. Record success or failure in the registry.
6. Continue to the next KB even if the current KB fails.

### 4.3 Project Selection

The command should support a focused subset:

```bash
llm-wiki maintain-all --project /abs/path/to/kb --apply
llm-wiki maintain-all --name dcn-llm-wiki --apply
```

If no selector is provided, all active registered KBs are included in the dry-run or apply plan.

## 5. Safety Boundaries

Batch maintenance must preserve the same safety rules as single-project backfill/update.

### 5.1 No Silent Auth Bypass

Cwiki auth failures are blockers for the affected KB. The command must not add `--no-auto-raw-sync` or silently skip upstream sync.

If auth is missing:

- mark that KB failed
- store a concise `last_error`
- continue to the next KB
- include the auth setup guidance in the per-KB report

### 5.2 Dirty Git Worktrees

If the KB project is a git worktree and has uncommitted changes before maintenance:

- default behavior: skip the KB and report `dirty_project_worktree`
- optional future flag: `--allow-dirty-projects`, but it should not be part of the first implementation

If a managed `raw-code/<codebase_id>/` checkout is dirty, existing update rules apply and the KB fails with a clear blocker.

### 5.3 No Commits or Pushes

The batch command does not commit or push project changes. It only modifies local KB files through existing project tools.

The final report should remind the user which KB projects have local file changes.

### 5.4 No Background Execution

Skill update may suggest running `maintain-all`, but it must not run batch backfill automatically.

This keeps network access, auth use, and local file edits under explicit user control.

## 6. Reports

Each batch run writes a report under the local registry area:

```text
~/.llm-wiki/maintenance-runs/<run_id>.json
~/.llm-wiki/maintenance-runs/<run_id>.md
```

The JSON report is for automation; the Markdown report is for user review.

### 6.1 Per-KB Result

Each result records:

- project path
- status: `planned`, `success`, `skipped`, or `failed`
- skip or failure reason
- whether tools were refreshed
- backfill report path
- update/health/graph summary when available
- elapsed time

### 6.2 Final Summary

The final console summary includes:

- total registered KBs
- active planned KBs
- successes
- skipped projects
- failures
- pruned missing entries
- report file path

## 7. Interaction With `llm-wiki update-skill`

`llm-wiki update-skill` remains responsible only for updating the installed skill bundle.

After a successful skill update, it may print a suggestion:

```text
Installed llm-wiki skill updated. Existing KB projects keep their project-local tools until refreshed.
Run `llm-wiki maintain-all` to preview batch backfill/update for registered KBs.
```

It must not invoke `maintain-all --apply` automatically.

## 8. Testing Strategy

Unit tests should cover:

- registry read/write and idempotent registration
- missing path reconcile and automatic removal after three missing runs
- `--prune-missing`
- discovery of strong and legacy KB shapes
- discovery skip rules for heavyweight directories
- dry-run plan generation without project writes
- apply flow continuing after one KB fails
- dirty project worktree skip
- report generation

Integration-style tests should use temporary KB directories with fake `tools/backfill.py` and `tools/update_wiki.py` scripts so the batch runner can verify sequencing without touching real Cwiki/Jira services.

## Open Questions

- Should the command name be exposed as `llm-wiki maintain-all`, `$llm-wiki-maintain-all`, or both?
- Should `maintain-all --apply` prompt for a final interactive confirmation, or is the explicit `--apply` flag enough?
- Should the first implementation include `--project` and `--name`, or start with all active projects plus `--discover`?
