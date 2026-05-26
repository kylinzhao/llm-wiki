# Raw-Code Git-Managed Design

Date: 2026-05-26
Status: Draft approved in brainstorming
Scope: `llm-wiki add-code`, `llm-wiki update`, raw-code sync contract, and legacy KB migration

## Summary

This design removes the current protocol gap between `llm-wiki add-code` and `llm-wiki update`.

After this change, there is only one supported raw-code onboarding model:

- `llm-wiki add-code <repo-or-local-path>` creates an engine-managed git checkout for the codebase under `raw-code/<codebase_id>/`.
- `llm-wiki update` refreshes those managed codebases by running a safe git pull before rebuilding code wiki outputs.
- copy, symlink, recorded external path, and snapshot-style raw-code onboarding are no longer supported.

The user-facing contract is intentionally narrow:

- if a user wants a codebase to participate in code wiki and future automatic refresh, they use `llm-wiki add-code`
- if the repository cannot be accessed because local auth or repository permission is missing, `add-code` stops immediately and tells the user to obtain access first
- if a repository has already been added through the supported model, future `llm-wiki update` runs refresh it without extra parameters

## Problem

The current design allows `raw-code/<codebase_id>/` to be populated in several ways:

- direct copy
- symlink
- recording an existing external path
- placing a git checkout or worktree directly under `raw-code/<codebase_id>/`

But `tools/update_wiki.py` only auto-refreshes codebases when `raw-code/<codebase_id>/` itself is a clean git worktree and can accept `git pull --ff-only`.

This creates a protocol mismatch:

- `add-code` appears to accept several onboarding styles as equally valid
- `update` only performs real upstream sync for one of those styles
- users can believe "the codebase has been added, so update will keep it fresh" when the engine is only rescanning a local snapshot
- old documentation still contains outdated option language, which amplifies that misunderstanding

The end result is incorrect operator expectations and stale implementation evidence.

## Goals

- Reduce raw-code onboarding to one supported contract.
- Make `llm-wiki add-code` a one-command workflow with no large parameter surface.
- Guarantee that a codebase added through `add-code` is updateable by future `llm-wiki update` runs.
- Fail fast when repository access is missing instead of creating half-configured raw-code entries.
- Give old KBs a deterministic migration path to the new contract.
- Keep the contract simple enough that the user does not need to understand internal sync modes.

## Non-Goals

- Preserving copy, symlink, snapshot, or external-path raw-code onboarding.
- Supporting repository refresh through arbitrary per-codebase custom commands.
- Allowing raw-code onboarding to continue after an auth or permission error.
- Maintaining old documentation language for deprecated flags or behaviors.

## Design

## 1. Single Contract

Only one raw-code protocol remains valid.

### 1.1 Supported model

Each managed codebase must satisfy all of the following:

- it lives under `raw-code/<codebase_id>/`
- that directory is an engine-managed git checkout or git worktree
- it has a metadata file written by `llm-wiki add-code`
- it is eligible for automatic refresh during `llm-wiki update`

### 1.2 Unsupported models

The following onboarding methods are rejected:

- copying source trees into `raw-code/`
- symlinking raw-code directories to another location
- storing a reference to an external source path without creating a managed checkout
- snapshot-only raw-code directories

If an existing KB contains those forms, it is considered legacy and must be migrated before it can claim compliance with the new engine contract.

## 2. `llm-wiki add-code`

`llm-wiki add-code` becomes the only supported entry point for attaching a repository to `raw-code/`.

### 2.1 Inputs

Accepted user input stays simple:

- a local repository path
- a remote repository URL

The user should not need to pass sync flags, onboarding mode flags, or explicit refresh commands.

### 2.2 Required behavior

`add-code` must:

1. inspect the provided target and resolve the repository identity
2. verify that the target is a git repository, or can be cloned as one
3. verify that the current machine has permission to access the repository
4. derive a stable `codebase_id` from repository identity
5. create a managed checkout or worktree at `raw-code/<codebase_id>/`
6. write codebase metadata marking the directory as engine-managed
7. build or refresh the code wiki outputs for that codebase
8. report the resulting managed path and future auto-update behavior

### 2.3 Permission rule

Permission errors are hard blockers.

If repository access fails because the machine lacks credentials, auth, or repository authorization:

- stop immediately
- do not create a partial raw-code directory
- do not write misleading metadata
- do not continue with code wiki build
- tell the user that repository access must be obtained first, then the same `add-code` command can be retried

Examples:

- local path points at a repo the current user cannot read
- remote clone requires credentials that are not configured
- git fetch fails because the repository is private and permission is missing

### 2.4 Dirty target rule

If the intended managed target already exists and is dirty:

- stop and ask the user to clean, stash, or migrate it explicitly

This prevents `add-code` from silently reusing a mutated raw-code checkout.

### 2.5 Metadata

Each managed codebase must carry a small machine-readable metadata file.

Recommended path:

- `raw-code/<codebase_id>/.llm-wiki-codebase.yaml`

Required fields:

- `codebase_id`
- `managed: true`
- `repo_url`
- `origin_ref`
- `default_branch`
- `managed_path`
- `created_by: llm-wiki-add-code`

Optional but useful fields:

- `source_input`
- `last_added_at`
- `notes`

The metadata does not describe multiple sync modes. It only records that this codebase is managed by the supported git-based contract.

### 2.6 User-visible report

The final report for `add-code` must always state:

- `codebase_id`
- repository source
- managed raw-code path
- current branch or revision
- that future `llm-wiki update` runs will auto-refresh this codebase

## 3. `llm-wiki update`

`llm-wiki update` no longer tries to infer sync behavior from heterogeneous raw-code directories.

### 3.1 Codebase discovery

The updater only treats a raw-code entry as updateable code evidence when:

- it exists under `raw-code/<codebase_id>/`
- it contains valid `.llm-wiki-codebase.yaml`
- the directory is a git worktree or checkout

Anything else is a legacy or invalid state and should be reported clearly.

### 3.2 Refresh behavior

For each managed codebase:

1. verify the directory still exists
2. verify it is still a git worktree or checkout
3. verify the worktree is clean
4. run `git pull --ff-only`
5. on success, continue into `scan_code.py`, traceability rebuild, health, graph, and related closure checks

No per-codebase custom sync command mechanism is kept in the final contract.

### 3.3 Dirty worktree behavior

If a managed codebase is dirty:

- mark it as blocked
- stop the code sync phase with a clear error
- tell the user to clean or stash the raw-code worktree before retrying

This should remain a hard safety boundary.

### 3.4 Invalid managed state

If metadata exists but the directory is no longer a git checkout or the origin is broken:

- treat the codebase as invalid
- fail the update instead of silently skipping it
- tell the user that the raw-code entry must be repaired or re-added

### 3.5 Reporting

The update report should list every managed codebase with a clear status:

- `refreshed`
- `blocked_dirty`
- `blocked_missing_access`
- `invalid_managed_checkout`
- `pull_failed`

This closes the current ambiguity around whether code was truly refreshed.

## 4. Engine Implementation Changes

The engine changes are intentionally straightforward.

### 4.1 Remove multi-mode sync assumptions

Delete the idea that code sync can be inferred from:

- symlink shape
- copy shape
- external path registration
- manifest-only sync overrides

The engine should not support those as first-class raw-code states anymore.

### 4.2 `tools/update_wiki.py`

Update the code sync phase so it:

- enumerates `raw-code/*`
- reads `.llm-wiki-codebase.yaml`
- validates the checkout shape
- runs `git pull --ff-only` for each managed codebase
- reports structured results

The old `raw_code_update_commands` override mechanism and related documentation should be removed as part of this simplification.

### 4.3 `add-code` deterministic helper

Add or refactor a deterministic helper so `add-code` can:

- inspect a repo source
- validate access
- create a managed checkout under `raw-code/`
- write metadata
- fail cleanly on permission issues

This helper should own the non-AI part of repository onboarding so the skill has a stable implementation path.

## 5. Documentation Changes

The following docs must be updated to match the single-contract model:

- `README.md`
- `skills/llm-wiki/SKILL.md`
- `skills/llm-wiki/references/commands.md`
- `skills/llm-wiki-add-code/SKILL.md`
- `skills/llm-wiki-update/SKILL.md`
- project template docs such as `docs/implementation-workflow.md`
- project template manifest comments and examples

Documentation requirements:

- describe only the managed git onboarding model
- state that `add-code` is the one-command setup path
- state that permission failures stop the command immediately
- remove outdated `--pull-code` references
- remove language that suggests copy, symlink, or recorded path are still valid onboarding styles

## 6. Legacy KB Migration

Old KBs must be actively migrated after the new skill lands.

### 6.1 Migration target

After migration, every codebase that should remain updateable must be:

- represented by a managed git checkout under `raw-code/<codebase_id>/`
- accompanied by `.llm-wiki-codebase.yaml`
- refreshable through the standard `llm-wiki update` flow

### 6.2 Migration helper

Provide a one-time migration tool that scans legacy `raw-code/` entries and classifies them.

Expected legacy shapes:

- copied source tree
- symlinked raw-code directory
- direct local git repo not created by `add-code`

For each entry, the migration tool should either:

- rehydrate it into a managed checkout when repository identity can be resolved safely, or
- stop and ask for the missing repository source if that identity cannot be inferred

The migration tool should not preserve legacy non-git modes as valid end states.

### 6.3 Migration report

The migration output should state:

- which codebases were converted successfully
- which ones are blocked by missing repository identity
- which ones are blocked by missing repository permission
- which ones require manual cleanup before re-adding

## 7. Operational Semantics

The resulting operator model should be simple:

- to add a new codebase: run `llm-wiki add-code`
- to refresh all managed codebases and rebuild the wiki: run `llm-wiki update`
- if add fails with missing access: obtain repository access first, then rerun the same add command
- if update fails with dirty raw-code: clean the managed checkout, then rerun update

No other onboarding or sync mental model should remain in skill documentation.

## 8. Verification

The implementation is complete only when the following are demonstrably true:

1. `add-code` can onboard a readable repository with one command and create a managed checkout under `raw-code/`.
2. `add-code` stops before mutation when repository permission is missing.
3. `update` refreshes a managed codebase through `git pull --ff-only` before code wiki rebuild.
4. `update` blocks on dirty managed raw-code checkouts with an explicit error.
5. documentation, skill wrappers, template comments, and engine behavior all describe the same single contract.
6. at least one legacy KB can be migrated from old raw-code layout to the managed git layout and then updated successfully through the new flow.

## Recommendation

Implement this design exactly as written and do not retain dual-mode compatibility.

The main value of the change is removing ambiguity. A narrower contract is preferable to a flexible one that produces stale code evidence while implying successful upstream sync.
