# Shared KB Update Design

Date: 2026-05-28
Status: Draft approved in brainstorming
Scope: `llm-wiki update`, shared KB git baseline, local evidence cache restore, and user-facing failure prompts

## Summary

`llm-wiki update` should default to collaborative operation.

In collaborative mode, update is not only a local maintenance command. It is a shared baseline operation:

1. sync the latest KB repository baseline
2. restore local evidence caches from declared upstream sources
3. run the normal deterministic and semantic update pipeline
4. validate the result
5. publish the updated KB baseline back to the shared git repository

`raw/` and `raw-code/` remain local evidence caches and are not committed to the KB repository. The repository must instead carry enough source declarations to restore those caches on any operator machine or gateway runner.

## Problem

The same KB can currently be updated in two places:

- in the cloud, where gateway update refreshes the KB and commits the git repository
- on a user's computer, where the skill updates the KB locally and does not commit the git repository

Over time, this creates divergent baselines:

- user-local KB output drifts from the cloud KB output
- the next operator repeats work that another machine already completed
- cloud and local update behavior can disagree about what "current" means
- a cloned KB repository is not enough to rebuild because `raw/` and `raw-code/` are intentionally not committed

The current model also gives users too much operational burden. They must remember when to pull, how to restore evidence, when to push, and whether their local result is now the shared baseline.

## Goals

- Make collaborative update the default behavior for `llm-wiki update`.
- Keep `raw/` and `raw-code/` out of the KB git repository.
- Make evidence cache restore reproducible through committed upstream declarations.
- Align local skill update and cloud gateway update around the same protocol.
- Publish successful KB updates so the next operator starts from the same baseline.
- Use Chinese for user-facing update status, errors, and choice prompts.
- Detect git permission failures and tell users to obtain repository access.
- Offer local mode only for shared git synchronization failures that happen before update modifies KB outputs, not when evidence, validation, or publish-after-update fails.

## Non-Goals

- Committing `raw/` or `raw-code/` into the KB repository.
- Automatically merging or rebasing complex KB output conflicts.
- Hiding shared git permission problems by silently falling back to local mode.
- Continuing after raw sync, raw-code sync, build, or health failures.
- Replacing the existing deterministic update pipeline.

## Design

## 1. Command Modes

`llm-wiki update` has two modes.

### 1.1 Shared mode

Shared mode is the default.

In shared mode, `llm-wiki update` means:

- pull the shared KB repository baseline
- refresh declared upstream evidence into local caches
- update and validate the KB outputs
- commit and push managed KB outputs

The default user mental model should be:

```text
llm-wiki update = 同步并发布共享知识库
```

### 1.2 Local mode

Local mode is an escape hatch for local-only work.

Supported entry points:

```bash
llm-wiki update --local
LLM_WIKI_UPDATE_MODE=local llm-wiki update
```

Local mode does not pull, commit, or push the shared KB repository. It still runs evidence refresh and validation because the local result must not be based on stale or broken evidence unless the user explicitly chooses existing lower-level skip flags such as `--no-auto-raw-sync`.

Evidence skip flags are local-mode only.

Shared mode must reject evidence skip flags such as `--no-auto-raw-sync` or `LLM_WIKI_NO_AUTO_RAW_SYNC=1` with a Chinese error. A shared baseline must not be published from intentionally skipped upstream evidence.

The user mental model should be:

```text
llm-wiki update --local = 只在我电脑试跑，不发布共享仓库
```

Local mode still requires a clean KB worktree before it modifies files.

Local mode preflight:

1. if the project is a git repository, run evidence cache git hygiene first, then require the remaining worktree to be clean before update
2. if the project is not a git repository, allow local mode but report that no shared baseline protection is available
3. never continue over a dirty git worktree unless the user separately resolves or commits the local changes

Rationale: local mode avoids shared pull/push, but it still rewrites KB outputs. Running it over user edits can mix generated changes with manual changes and make the result harder to review.

Dirty-worktree shared preflight may offer local mode only as a way to rerun after the user resolves the dirty state. It must not switch into local mode and continue immediately over the dirty worktree.

When a shared-mode failure offers local mode and the user accepts, the command restarts from local mode preflight step 1. Local-mode fallback never resumes from the middle of shared preflight and never skips evidence cache hygiene or dirty-worktree checks.

In noninteractive execution, local-mode fallback fails closed. The command must stop unless local mode was requested explicitly with `--local` or `LLM_WIKI_UPDATE_MODE=local`.

## 1.3 Interfaces and Ownership

The implementation is split into small units with explicit ownership.

| Unit | Responsibility | Owner |
| --- | --- | --- |
| Shared git preflight | Detect repo, branch tracking, dirty worktree, ahead/diverged state, and pull eligibility | update orchestration layer |
| Permission classifier | Classify git stderr as read permission, write permission, or non-permission failure | shared helper used by preflight and publish |
| Evidence restore | Refresh `raw/` and managed `raw-code/` caches from committed declarations | existing project template tools |
| Update pipeline invocation | Run deterministic update, semantic refinement, and validation in the existing order | existing `llm-wiki update` command flow |
| Managed output publish | Stage allowlisted outputs, commit, and push | update orchestration layer after validation |
| User prompt/reporting | Produce Chinese status, failure, and local-mode choice text | skill command protocol and orchestration layer |

The first implementation should keep git preflight and publish outside `tools/update_wiki.py`.

Rationale:

- `tools/update_wiki.py` owns deterministic project maintenance and evidence refresh.
- AI-native semantic refinement happens in the agent after deterministic tooling.
- Publishing must happen after both deterministic and semantic validation, so it belongs to the higher-level update orchestration layer.
- Gateway update can use the same orchestration state machine with service credentials, while local skill update uses the user's credentials.

If a future gateway needs a pure CLI entry point, add a thin orchestrator command that wraps `tools/update_wiki.py`; do not move semantic publishing responsibility into the deterministic builder.

## 2. Shared Git Preflight

Shared mode requires the KB directory to be a git repository.

Preflight order:

1. verify `.git` exists or `git rev-parse --show-toplevel` succeeds
2. verify the current branch has an upstream tracking branch
3. run evidence cache git hygiene checks for `raw/` and expected `raw-code/`
4. verify the remaining worktree is clean before update
5. run `git fetch`
6. inspect local branch divergence from its upstream
7. if the branch is behind only, run `git pull --ff-only`
8. if the branch is ahead only, inspect the ahead commits before starting a new update
9. if the branch has diverged, stop and do not merge or rebase automatically

Preflight ordering is normative:

| Mode | Order |
| --- | --- |
| Shared mode | git repo -> upstream branch -> evidence cache hygiene -> dirty worktree -> fetch/divergence -> pull/publish-ahead recovery |
| Local mode in git repo | evidence cache hygiene -> dirty worktree -> evidence restore -> update/validation, with no fetch/pull/push |
| Local mode outside git repo | report no shared baseline protection -> evidence restore -> update/validation |

Evidence cache hygiene runs before the general dirty-worktree check. This ensures an unignored or tracked `raw/` / `raw-code/` reports `evidence_cache_ignore_failed` or `evidence_cache_tracked_failed`, not a generic dirty-worktree blocker.

If the worktree is dirty before update, stop before modifying project files. Do not try to infer whether the user's edits are safe.

Recommended Chinese prompt:

```text
当前无法同步共享 KB：工作区存在未提交改动。

请先提交、暂存或清理这些改动，然后重新运行 `llm-wiki update`。

如果你只是想临时在本机更新，不发布到共享仓库，可以在清理工作区后运行 `llm-wiki update --local`。
```

If `git pull --ff-only` fails because the remote contains non-fast-forward history, stop and offer local mode. Do not auto-merge or auto-rebase.

Shared mode publishes to the current branch's configured upstream. It does not force `main`.

Ahead-only commits are not automatically pushed unless they are recognizable unpublished update commits.

Recognizable unpublished update commits must satisfy all of the following:

- every ahead commit subject matches `Update <kb-name> knowledge base`
- every ahead commit body contains `Actor: local-skill` or `Actor: gateway`
- the combined file diff from upstream to `HEAD` touches only the managed output allowlist and no explicit exclusions

If any ahead commit fails that check, stop before update and explain:

```text
当前分支存在尚未推送的本地提交，但这些提交无法确认是 llm-wiki update 生成的未发布基线。

为避免误发布用户自己的提交，本轮不会自动 push。
请先手动检查并处理这些提交，然后重新运行 `llm-wiki update`。
```

Only recognizable unpublished update commits may be pushed automatically during preflight. If that push succeeds, continue with the normal shared update. If it fails, follow the publish-failure rules.

If the current branch has no upstream tracking branch, stop and explain that shared update needs an upstream branch before it can pull or push:

```text
当前无法同步共享 KB：当前 Git 分支没有配置上游分支。

请先为当前分支配置远端上游，例如 `git branch --set-upstream-to=origin/main`，然后重新运行 `llm-wiki update`。
如果你只是想临时在本机更新，不发布到共享仓库，也可以切换到本机模式继续。
是否切换到本机模式？
```

## 3. Evidence Cache Restore

`raw/` and `raw-code/` are local caches. They are restored from committed source declarations.

The KB repository must ignore evidence cache directories:

```gitignore
raw/
raw-code/
```

Shared update preflight must verify that `raw/` and `raw-code/` are ignored by git when those paths exist or are expected. If either path is not ignored, stop with an evidence-cache ignore migration blocker before restoring evidence.

Rationale: normal evidence restore creates or modifies `raw/**` and `raw-code/**`. Those paths must not appear as tracked or untracked publish candidates. The publish step must not silently filter visible evidence-cache changes because that would hide a repository hygiene problem.

Evidence cache git hygiene algorithm:

1. Always check `raw/`.
2. Check `raw-code/` when any of these are true:
   - `raw-code/` exists
   - `upstream/code-sources.json` exists
   - committed `wiki/code/**` exists
   - committed `staging/code-graph/**` exists
3. For each checked cache path:
   - `git ls-files -- <path>` must return no tracked files
   - `git check-ignore -q <path>` must succeed
4. If tracked files exist under `raw/**` or `raw-code/**`, stop with `evidence_cache_tracked_failed` and tell the operator to remove them from git history/index before shared update.
5. If the path is not ignored, stop with `evidence_cache_ignore_failed` and tell the operator to add the cache path to `.gitignore`.

Local mode enforces the same evidence cache git hygiene when the project is a git repository. Local mode may run without these checks only in a non-git project, where there is no shared publish risk.

### 3.1 `raw/`

`upstream/wiki-sources.json` remains the standard declaration for document evidence.

It records source type, URL, page id, site base, depth, output directories, filters, RSS/feed information, and relationship role. During update, enabled sources are refreshed into `raw/` before deterministic build.

If Cwiki authentication fails, this is an evidence failure, not a shared git failure. Stop and do not offer local mode as a bypass.

### 3.2 `raw-code/`

Code evidence uses a committed source declaration plus the existing engine-managed checkout metadata.

The committed source declaration is:

- `upstream/code-sources.json`

This file is the cross-machine source of truth for restoring `raw-code/` caches. It is committed to the KB repository. `.llm-wiki-codebase.yaml` remains a local managed-checkout metadata file inside `raw-code/<codebase_id>/`, but it is not sufficient for restoration because `raw-code/**` is not committed.

Required `upstream/code-sources.json` shape:

```json
{
  "version": 1,
  "sources": [
    {
      "codebase_id": "sell-taro",
      "repo_url": "git@git.example.com:team/sell-taro.git",
      "origin_ref": "main",
      "default_branch": "main",
      "target_dir": "raw-code/sell-taro",
      "enabled": true,
      "managed": true,
      "sync": {
        "mode": "ff-only"
      }
    }
  ]
}
```

Required source fields:

- `codebase_id`
- `repo_url`
- `origin_ref`
- `default_branch` as metadata only, used by reports and future migrations
- `target_dir`
- `enabled`
- `managed: true`
- `sync.mode: ff-only`

First implementation supports only branch refs for `origin_ref`.

`origin_ref` semantics and validation:

- value is a branch name such as `main` or `release/2026-05`
- not a tag, commit SHA, detached ref, or arbitrary remote ref
- validate with `git check-ref-format --branch <origin_ref>`
- reject values starting with `origin/` or `refs/`
- reject full 40-character hex commit SHAs
- reject values containing `..`, empty path components, or path traversal-like segments
- clone must check out this branch and configure it to track `origin/<origin_ref>`
- refresh uses `git pull --ff-only` on that checked-out tracking branch

If a future codebase needs pinned commit or tag semantics, that should be added as a separate sync mode because `git pull --ff-only` is branch-oriented.

Validation rules for `upstream/code-sources.json`:

- malformed JSON blocks update with `code_source_config_failed`
- missing `version` or non-list `sources` blocks update
- `codebase_id` must be non-empty and a safe single path segment using only letters, digits, `_`, `.`, and `-`
- `repo_url` must be non-empty and must be either an SSH git URL, an HTTP(S) URL, or a local path used only for same-machine migration
- shared mode rejects local `repo_url` values with `code_source_config_failed`
- local `repo_url` values are allowed only when running `llm-wiki update --local` or a migration command that explicitly opts out of shared publishing
- local `repo_url` values must resolve to an existing git repository
- local `repo_url` values must not contain `..`
- repo-relative local `repo_url` values are resolved relative to the KB root
- absolute local `repo_url` values are allowed only for local-mode migration and should not be used for shared KB baselines because they are not cross-machine reproducible
- symlink-expanded local paths must still point at a git repository; the updater does not clone arbitrary non-git directories
- duplicate `codebase_id` blocks update
- duplicate `target_dir` blocks update
- `target_dir` must be exactly `raw-code/<codebase_id>`
- `target_dir` must not be absolute
- `target_dir` must not contain `..` path traversal
- `target_dir` basename must equal `codebase_id`
- `enabled` must be boolean; `true` restores and refreshes the source, `false` disables it
- `managed` must be `true`
- `sync.mode` must be `ff-only`
- `origin_ref` must be a non-empty branch name accepted by `git check-ref-format --branch`
- `origin_ref` must not start with `origin/` or `refs/`
- `origin_ref` must not be a full 40-character hex commit SHA
- `origin_ref` must not contain `..`, empty path components, or path traversal-like segments

Configuration failures are evidence configuration failures, not git permission failures. They stop update and do not offer local mode.

All `upstream/code-sources.json` entries must be validated before any raw-code clone or pull starts. If any source entry is invalid, update stops with `code_source_config_failed` and must not mutate `raw-code/`.

`llm-wiki add-code` must write or update both:

- `upstream/code-sources.json`, committed source declaration
- `raw-code/<codebase_id>/.llm-wiki-codebase.yaml`, local checkout metadata

Each codebase under `raw-code/<codebase_id>/` must be a clean managed git checkout created by `llm-wiki add-code` and carrying `.llm-wiki-codebase.yaml`.

The metadata interface is:

```yaml
codebase_id: sell-taro
managed: true
repo_url: git@git.example.com:team/sell-taro.git
origin_ref: main
default_branch: main
managed_path: raw-code/sell-taro
created_by: llm-wiki-add-code
```

Required fields:

- `codebase_id`
- `managed: true`
- `repo_url`
- `origin_ref`
- `default_branch`
- `managed_path`
- `created_by: llm-wiki-add-code`

Discovery rules:

- if `upstream/code-sources.json` exists, it drives clone/pull restore for every source with `enabled: true`
- disabled sources are ignored by restore, but if committed `wiki/code/codebases/<codebase_id>/` exists for a disabled source the update must report a code evidence configuration conflict
- if a declared target directory is missing, clone `repo_url` into `target_dir` and write `.llm-wiki-codebase.yaml`
- if a declared target directory exists, verify it is a git checkout with matching metadata, then `git pull --ff-only`
- no `upstream/code-sources.json` and no `raw-code/` means there is no code evidence to refresh unless committed `wiki/code/codebases/*/` directories indicate code evidence is expected
- `raw-code/<codebase_id>/` without a matching `upstream/code-sources.json` source is a legacy unmanaged state and blocks update when code evidence is expected
- metadata with `managed: false` is not supported by shared update and blocks until migrated or removed
- metadata whose `managed_path` does not match the directory blocks update
- committed `wiki/code/codebases/<codebase_id>/` directories without a matching `upstream/code-sources.json` source block update and tell the operator to run `llm-wiki add-code` or migrate the code source declaration

During update:

1. read `upstream/code-sources.json` when present
2. restore missing enabled declared codebases by cloning their `repo_url` into `target_dir`
3. verify each declared directory is a git checkout
4. verify each worktree is clean
5. refresh each with `git pull --ff-only`
6. continue into code scan, capability update, traceability, health, graph, and anchors

If raw-code access fails because of repository permission, stop and tell the user to obtain code repository access. Do not offer local mode as a meaningful fix because the local update would still be based on unreliable code evidence.

## 4. Managed Output Publishing

After update and validation succeed, shared mode publishes managed KB outputs.

Required publish sequence:

```bash
git status --porcelain=v1 -z
git add -- <computed-allowed-changed-paths>
git commit -m "Update <kb-name> knowledge base" -m "Actor: <local-skill|gateway>"
git push
```

Publish decision order:

1. inspect all changed files
2. if any changed file is outside the managed output allowlist or inside the explicit exclusion set, stop before staging anything and report the unexpected files
3. if no files changed, report that the shared KB is already current and do not create an empty commit
4. if only allowlisted files changed, stage them
5. if `git add` fails, stop with `stage_failed_dirty_result`
6. commit with the required message
7. if `git commit` fails, stop with `commit_failed_dirty_result`
8. push the new commit

This means "already current" is only valid when there are no changed files at all. If only non-allowlisted files changed, the result is an unexpected local change blocker, not "already current."

Staging mechanics:

- compute changed paths from `git status --porcelain=v1 -z`
- parse NUL-delimited porcelain output; do not parse human-quoted non-`-z` porcelain output
- treat adds, modifications, deletions, renames, copies, type changes, and untracked files as changed paths
- for renames and copies, both old and new paths must pass allowlist/exclusion checks
- stage exact computed paths with `git add -- <paths>` rather than staging broad allowlist globs
- stage deletions with the same exact-path command; if a deletion path is allowlisted and not excluded, it is publishable
- if the computed path list is empty after status parsing, do not commit
- commit hooks run normally; hook failure is reported as `commit_failed_dirty_result`

The commit message format is shared by local skill and gateway:

```text
Update <kb-name> knowledge base

Actor: <local-skill|gateway>
```

`<kb-name>` is the repository directory name unless `kb.manifest.yaml` later defines a stronger display name. The actor value identifies the environment without changing the main subject line.

### 4.1 Managed output allowlist

Automatic publish must only stage managed KB files.

Allowlist ownership:

| Pattern | Ownership |
| --- | --- |
| `kb.manifest.yaml` | managed declaration |
| `BUSINESS_CONTEXT.md` | user-maintained but publishable canonical context |
| `upstream/**` | managed source declarations |
| `wiki/**` | managed KB output |
| `docs/retrieval-playbook.md` | managed KB operations doc |
| `docs/build-and-maintenance.md` | managed KB operations doc |
| `docs/implementation-workflow.md` | managed KB operations doc |
| `docs/query-acceptance.md` | managed KB quality doc |
| `docs/*quality-audit*.md` | managed KB quality doc |
| `docs/*tooling*.md` | managed KB operations doc |
| `staging/**` listed below | managed update state |
| `graph/**` | managed graph output |
| `index/**` | managed index output |

`BUSINESS_CONTEXT.md` is included because it is the shared canonical business context for the KB. If it changes during an update, publishing it is intentional; if a user has unrelated manual edits before update, dirty-worktree preflight blocks first.

Required include set:

- `kb.manifest.yaml`
- `BUSINESS_CONTEXT.md`
- `upstream/**`
- `wiki/**`
- `docs/retrieval-playbook.md`
- `docs/build-and-maintenance.md`
- `docs/implementation-workflow.md`
- `docs/query-acceptance.md`
- `docs/*quality-audit*.md`
- `docs/*tooling*.md`
- `staging/update/latest.*`
- `staging/refinement-status.md`
- `staging/refinement-plan.json`
- `staging/source-manifest.json`
- `staging/code-graph/**`
- `staging/traceability/**`
- `graph/**`
- `index/**`

Required explicit exclusions:

- `raw/**`
- `raw-code/**`
- `.env`
- `.env.*`
- `**/.env`
- `**/.env.*`
- `*.pem`
- `*.key`
- `*.crt`
- `*.p12`
- `*.pfx`
- `*.cookie`
- `*.cookies`
- `*cookie*`
- `*token*`
- `*secret*`
- `.llm-wiki/**`
- `.venv/**`
- `venv/**`
- `node_modules/**`
- `*.log`

Exclusion takes precedence over inclusion. For example, `raw/.env` must never be staged even if a broad future include pattern could match it.

First implementation uses path-based exclusion, not content-based secret scanning. A future secret scanner can add another blocking layer, but publish safety for this design depends on concrete path globs above.

Path matching rules:

- match against repo-relative paths normalized to POSIX `/` separators
- matching is case-sensitive
- a pattern without `/` matches any path segment basename, so `*token*` blocks both `token.txt` and `config/api-token.json`
- a pattern with `/` matches the full repo-relative path, so `raw/**` blocks everything under `raw/`
- exclusions are evaluated before inclusions

If files outside the allowlist changed, stop before commit and report them. Do not guess whether they should be published.

If allowlisted and non-allowlisted files changed together, stage nothing and stop. This prevents partial publish from making a mixed local state look shared.

## 5. Failure Taxonomy

Update failures are classified into three groups.

### 5.1 Shared synchronization failures

These happen before local evidence or KB outputs are modified:

- KB is not a git repository
- current branch has no upstream tracking branch
- `git fetch` fails
- `git pull --ff-only` fails
- remote is unreachable
- remote history requires merge or rebase

Behavior:

- explain the reason in Chinese
- if the failure is permission-related, tell the user to obtain repository access first
- offer local mode as a temporary choice, but continue only after explicit user confirmation

Dirty worktree is a separate safety blocker, not a local-mode fallback case. It must use `dirty_worktree_blocked` and ask the user to resolve the worktree before either shared or local update.

For permission failures, the prompt must lead with access repair and present local mode as a temporary escape hatch:

```text
当前无法同步共享 KB：没有 Git 仓库读取权限。

请先确认你已经获得该 KB 仓库的读取权限，并且本机 Git 凭证或 SSH Key 已配置正确。
权限修复后，可以重新运行 `llm-wiki update`。

如果你只是想临时在本机更新，不发布到共享仓库，也可以切换到本机模式继续。
是否切换到本机模式？
```

The tool must not silently switch to local mode. The user must explicitly answer yes, or rerun with `llm-wiki update --local`.

### 5.2 Evidence, build, and validation failures

These mean the KB result is unreliable:

- Cwiki/RSS raw sync failure
- raw-code sync failure
- missing raw-code permission
- dirty managed raw-code checkout
- deterministic build failure
- semantic refinement blocker
- health failure
- graph or anchor validation failure

Behavior:

- stop
- explain the blocker in Chinese
- do not offer local mode as a bypass
- do not commit or push

### 5.3 Shared publish failures

These happen after update succeeds locally:

- push is rejected
- branch protection prevents push
- write permission is missing
- remote moved after the local commit

Behavior:

- explain that the local result exists but is not shared
- if the failure is permission-related, tell the user to obtain write permission
- report the state as an unpublished local baseline
- do not auto-merge, auto-rebase, or retry complex publication

Recommended Chinese prompt:

```text
KB 已在本机更新并通过校验，但无法发布到共享仓库。

失败原因：缺少共享 KB 仓库写入权限。
请申请该仓库的写入权限，或检查本机 Git 凭证 / SSH Key 配置。

当前结果只是本机未发布基线，其他人暂时不会看到这次更新。
权限修复后，可以重新运行 `llm-wiki update` 或手动完成推送。
```

### 5.4 Unpublished local baseline recovery

An unpublished local baseline is represented by git state, not by a committed marker file.

Detection:

- worktree is clean
- current branch is ahead of its upstream
- current branch is not behind upstream

Next shared update behavior:

1. run `git fetch`
2. detect the branch is ahead-only
3. verify all ahead commits are recognizable update commits using the Section 2 subject/body and allowlisted-diff rules
4. if any ahead commit is unrecognized, stop with `ahead_unrecognized_commits`
5. if all ahead commits are recognizable, attempt `git push` for the existing local commit or commits
6. if push succeeds, run `git fetch` again and re-check divergence
7. if the branch is now synchronized, continue with a normal shared update from the synchronized baseline
8. if the branch is behind only, run `git pull --ff-only` before continuing
9. if the branch has diverged, stop and do not merge or rebase automatically
10. if push fails because of permission, report missing write permission

If `git commit` failed during publish, the state is not an unpublished local baseline. It is a dirty local update result. The next shared or local update must stop at dirty-worktree preflight until the user resolves, commits, or discards the dirty result.

No `staging/update/unpublished.*` marker is required in the first implementation because it creates awkward commit ordering after a push failure. If later diagnostics need a visible marker, it must be untracked or explicitly excluded from automatic publish.

### 5.5 Terminal state table

| Terminal state | Changed files | Commit state | Push state | User message | Local-mode fallback |
| --- | --- | --- | --- | --- | --- |
| `published` | only allowlisted | new commit created | pushed | shared KB baseline updated | no |
| `no_changes` | none | no commit | no push | shared KB already current | no |
| `unexpected_local_changes` | any non-allowlisted or excluded path | no commit | no push | report paths and ask user to resolve | no immediate fallback |
| `dirty_worktree_blocked` | pre-existing dirty git worktree | no commit | no push | report dirty files and ask user to resolve before shared or local update | no immediate fallback |
| `ahead_unrecognized_commits` | clean worktree, branch ahead | existing local commits remain | no push | report unrecognized local commits and refuse automatic publish | no immediate fallback |
| `shared_sync_failed` | unchanged | no commit | no push | explain git sync failure in Chinese | yes, only with explicit confirmation |
| `evidence_cache_ignore_failed` | unchanged | no commit | no push | explain `raw/` or `raw-code/` must be ignored | no |
| `evidence_cache_tracked_failed` | tracked evidence files exist | no commit | no push | explain evidence cache files must be removed from git tracking | no |
| `code_source_config_failed` | unchanged | no commit | no push | explain malformed or unsafe `upstream/code-sources.json` | no |
| `evidence_failed` | may include raw/raw-code cache changes | no commit | no push | explain evidence blocker in Chinese | no |
| `validation_failed` | may include managed outputs | no commit | no push | explain build/health/graph blocker in Chinese | no |
| `stage_failed_dirty_result` | managed outputs remain in worktree | no commit | no push | explain staging failed and no files were published | no automatic fallback |
| `commit_failed_dirty_result` | managed outputs may be staged or unstaged | no commit | no push | explain local dirty update result | no automatic fallback |
| `unpublished_local_baseline` | clean worktree | local commit exists | push failed | explain result is not shared; mention permission if relevant | no; retry publish after repair |

## 6. Permission Detection

Git permission failures must be recognized and reported separately from ordinary sync failures.

Detection should match common git stderr fragments, including:

- `Permission denied`
- `Authentication failed`
- `Repository not found`
- `403`
- `remote: You are not allowed`
- `Could not read from remote repository`
- `The requested URL returned error: 403`
- `HTTP Basic: Access denied`
- `fatal: Authentication failed`
- `remote: HTTP Basic: Access denied`

Read-side failures from `fetch` or `pull` should say the user needs read permission.

Write-side failures from `push` should say the user needs write permission.

Example read permission prompt:

```text
共享 KB 同步失败：`git pull --ff-only` 执行失败。

失败原因：没有远端仓库读取权限。
原始错误：Permission denied (publickey).

请先申请该 KB 仓库的读取权限，或检查本机 SSH Key / Git 凭证配置。
如果你只是想临时在本机更新，不发布到共享仓库，也可以切换到本机模式继续。
是否切换到本机模式？
```

Example write permission prompt:

```text
共享 KB 发布失败：`git push` 执行失败。

失败原因：没有远端仓库写入权限。
原始错误：remote: You are not allowed to push code to this project.

请先申请该 KB 仓库的写入权限，或检查本机 SSH Key / Git 凭证配置。
当前结果只是本机未发布基线，其他人暂时不会看到这次更新。
```

## 7. Gateway Alignment

Cloud gateway update and local skill update should use the same protocol:

1. start from latest shared git baseline
2. restore evidence caches from committed upstream declarations
3. run update pipeline
4. validate
5. publish shared KB baseline

The gateway may have service credentials for KB and evidence repositories. The local skill uses the user's credentials. Permission failures are therefore expected to differ by environment, but the state machine and reports should remain consistent.

Gateway implementation is an integration consumer of this protocol, not part of the first local skill implementation plan.

The shared interface between local and gateway is:

- the state machine in this spec
- the git permission classification rules
- the raw and raw-code evidence restore contracts
- the managed output allowlist
- the terminal state categories in Section 5.5

Gateway-specific credential injection, job scheduling, and repository checkout management remain outside this spec.

## 8. User-Facing Language

All user-facing update status, failure explanations, and choice prompts must be written in Chinese.

Commands, file paths, git stderr snippets, and machine-readable status fields may remain in English.

Good:

```text
共享 KB 同步失败：`git fetch` 执行失败。
失败原因：远端仓库暂时不可访问。
```

Bad:

```text
Shared update failed because fetch failed.
```

## 9. State Machine

```text
start shared update
  -> shared git preflight
     -> permission failure: explain permission, offer local mode only with explicit confirmation
     -> non-permission shared failure: explain, offer local mode only with explicit confirmation
     -> ahead-only recognizable update commits: push existing commits, then continue
     -> ahead-only unrecognized commits: stop, no automatic push
     -> diverged branch: explain sync failure, offer local mode only with explicit confirmation
  -> restore raw evidence
     -> failure: stop, no local-mode bypass
  -> restore raw-code evidence
     -> failure: stop, no local-mode bypass
  -> deterministic update
     -> failure: stop, no publish
  -> semantic refinement and validation
     -> failure: stop, no publish
  -> publish managed outputs
     -> permission failure: explain write permission, mark unpublished local baseline
     -> non-permission publish failure: mark unpublished local baseline
  -> shared baseline published
```

## 10. Rollout

Recommended implementation order:

1. document the shared update protocol in `commands.md` and `$llm-wiki-update`
2. add git preflight and permission classification helpers to the project template update tooling
3. add managed-output allowlist and publish reporting
4. add tests for shared preflight, permission messages, local-mode fallback prompts, and publish failures
5. document gateway as a consumer of the shared state machine
6. update release notes and migration guidance
