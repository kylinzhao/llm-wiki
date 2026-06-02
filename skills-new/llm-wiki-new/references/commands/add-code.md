## `llm-wiki-new add-code`

Purpose: add another project codebase under `raw-code/<codebase_id>/` and build or refresh the code wiki layer.

Use when:

- The user points to another local project, repo clone, or source tree.
- The project should answer implementation questions using that codebase.
- The added material is implementation evidence, not business requirements.

Default order:

1. Read `BUSINESS_CONTEXT.md` and existing `wiki/code/index.md` when present.
2. Inspect the provided code path, detect repo root, stack, entry points, docs, and whether it is a git repository.
3. Choose a stable `codebase_id` from the repo or directory name; ask only if it collides or is misleading.
4. Add the codebase under `raw-code/<codebase_id>/` as an engine-managed git checkout or git worktree. Do not mix it into `raw/`.
   - this is the only supported onboarding model
   - if repository access is missing, stop immediately and tell the user to obtain permission before retrying
5. Scan the codebase for README, AGENTS, OpenSpec, API contracts, routes, controllers, services, jobs, messages, data access, and config.
6. If `docs/wiki` is present, adapt upstream topics, concepts, and source maps before deciding whether graphify is needed.
7. Run graphify only if available and useful for structure evidence; otherwise record why it was skipped.
8. Create or update `wiki/code/codebases/<codebase_id>/`, candidate artifacts, and affected `wiki/code/capabilities/`.
8. If relevant requirements already exist, add or refresh `wiki/code/traceability/` rows with conservative evidence strength.
9. Run health and graph.

Stop for confirmation when:

- The source path is missing.
- The target `raw-code/<codebase_id>/` already exists.
- The current machine cannot read or clone the repository.
- The existing managed target is dirty and cannot be safely reused.

Final report:

- codebase_id
- repository source and managed checkout path
- detected stack and entry points
- pages created or updated
- capability and traceability coverage
- validation results
- missing evidence
