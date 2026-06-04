## `llm-wiki refine`

Purpose: let the user 主动触发 source/concept/entity/wiki semantic refinement without waiting for another raw, code, or BUSINESS_CONTEXT change.

`llm-wiki update` may still automatically run source refinement when deterministic reports expose pending, stale, or `needs_refinement` work. `llm-wiki refine` is the explicit command for the same agent-native refinement class: start from the refinement plan and quality signals, update only the semantic pages that are in scope, then validate and publish.

Default mode:

- Shared mode is the default, matching `llm-wiki update`.
- Run the same KB git preflight as update before editing: clean worktree, upstream configured, evidence caches ignored, skip flags rejected, and fast-forward synchronization when available.
- After refinement and hard validation pass, stage only allowlisted KB outputs and commit and push the shared KB baseline.
- `llm-wiki refine --local` or `LLM_WIKI_UPDATE_MODE=local` is allowed for a local-only trial; local mode does not pull, commit, or push unless the user explicitly asks for local git publishing.

Read:

1. `BUSINESS_CONTEXT.md`
2. `staging/refinement-plan.json`
3. `staging/refinement-status.md`
4. `staging/update/latest.json`
5. `staging/health/latest.json`
6. `graph/summary.md`
7. affected `wiki/sources/*`, `wiki/concepts/*`, `wiki/entities/*`, and G+ pages

Refinement scope:

- Prioritize source pages marked pending, stale, deterministic seed, missing completed status, or `needs_refinement`.
- If the user names a source, concept, entity, capability, or traceability area, restrict the first pass to that scope and its direct dependents.
- If `gplus_quality.status=needs_attention`, include concepts/entities/truth/conflicts/evidence/proposals/operations/reference pages needed to make the semantic layer useful.
- Do not rewrite unrelated refined prose, manual edits, raw evidence, credentials, local caches, or unmanaged `raw-code/`.

Execution:

1. Resolve shared vs local mode.
2. In shared mode, perform update-style git preflight and synchronization before writing.
3. Run the lightweight historical refinement-state reconcile if the standard tooling is present.
4. Process the refinement queue with the current agent or available workers. For more than 10 pending pages, use disjoint worker slices when the host exposes worker support.
5. Update `wiki/sources/*` prose, Business Links, dependent concept/entity/G+ pages, and `staging/refinement-status.md`.
6. Re-run refinement contract checks, health, graph, and anchor checks when traceability/code anchors changed.
7. In shared mode, publish with a normal git commit and push. If push fails after commit, report in Chinese that the KB is committed locally but unpublished; when permission-related, tell the user to request write access or check SSH Key / Git credentials.

Do not:

- Treat `refine` as a read-only diagnosis command; use `doctor` for that.
- Rebuild the whole wiki unless the refinement evidence proves the current structure is invalid.
- Ask the user to run `update` again for refinement work that can be completed now.
- Leave allowlisted generated KB artifacts dirty in shared mode after validation passes merely because image evidence or a remaining semantic queue is checkpointed.

Final report:

- trigger and requested scope
- pages refined
- dependent pages updated
- pages intentionally left untouched
- validation results
- source refinement contract status
- G+ semantic quality status
- shared publish status: pulled / committed / pushed, or local-only
- readiness: healthy / usable-with-gaps / blocked
- remaining queue or blocker

Recommendation rule:

- If shared mode commit and push succeeded and no P0/P1 remains, say the KB is ready for use.
- If validation passes but a large queue remains due to tool/context/user stop, report the checkpoint as `usable-with-gaps` and state the exact remaining queue.
- If hard validation fails, recommend the smallest safe continuation, usually `llm-wiki refine` for semantic-only gaps or `llm-wiki update` when raw/code evidence must be refreshed.
