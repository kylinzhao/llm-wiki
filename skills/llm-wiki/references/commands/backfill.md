## `llm-wiki backfill`

Purpose: upgrade an existing LLM Wiki project built with older skill versions by re-scanning historical evidence and then absorbing newly available evidence into the refined wiki layers.

Use when:

- The project predates newer deterministic evidence features such as draw.io text extraction, Cjira/Jira/IDEA registry, source metadata v2, or query-routing agent rules.
- The user wants a hotfix for many existing KBs without manually rebuilding from scratch.
- A doctor/update report says historical evidence exists but backfill artifacts are missing.
- A newly released deterministic feature requires re-reading old `raw/`, `wiki/sources/`, or `staging/` files.

Default order:

1. Read `BUSINESS_CONTEXT.md` when present, but do not block deterministic backfill solely because it is incomplete; report the issue before semantic absorption.
2. Refresh engine-owned tools and agent rules from the installed skill:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
   ```

3. Run the backfill pipeline:

   ```bash
   uv run python tools/backfill.py
   ```

   If `uv` is unavailable but project dependencies are already satisfied, fall back to `python3 tools/backfill.py`.

4. Read `staging/backfill/latest.json` and `latest.md`.
5. If `refinement_absorption_required=true`, continue directly with `llm-wiki update` semantics over `refinement_scope`:
   - update affected `wiki/sources/*` summaries and Business Links
   - refresh related concepts/entities
   - refresh truth/conflicts/evidence/proposals/operations/reference
   - refresh query acceptance and G+ quality audit
   - run health, graph, and anchor checks when relevant
6. If no deterministic evidence changed, run or recommend `llm-wiki doctor` for a read-only confirmation.

Current deterministic passes:

- `drawio`: converts historical `.drawio` / `.dio` files into Mermaid-backed Markdown evidence and links that evidence from raw page indexes.
- `source_metadata`: patches existing `wiki/sources/*` with Delivery Tracking and Source Metadata without rewriting refined summaries.
- `refinement_state_reconcile`: repairs historical source refinement state when existing page content is already refined but metadata/status is still pending, applied, complete, or missing a completed record. It records `reconciled_from_existing_content` instead of claiming a new semantic rewrite.
- `cjira`: rebuilds `staging/cjira-registry/` from historical raw Jira/Cjira/IDEA signals. Since legacy `project.guazi-corp.com` is offline, cjira status refresh does not call it; explicit `project.guazi-corp.com/browse/<KEY>` links in raw are treated as offline legacy references for shipped/frozen historical evidence.
- `agent_rules`: patches missing project query-routing rules.

Extensibility rule: future features that need to re-scan historical documents should become a new `tools/backfill.py` pass and feed `refinement_scope`, instead of being hidden inside query or doctor.

Do not:

- Treat backfill as a full rebuild.
- Rewrite `raw/` source text, except deterministic evidence-link sections managed by the backfill pass.
- Stop after deterministic backfill when new evidence changed source/G+ behavior; continue into refinement absorption unless blocked.
- Silently ignore Jira auth failures. Offline key extraction can continue, but status refresh blockers must be reported. Do not hardcode Jira tokens into the skill bundle; use local environment variables or `~/.llm-wiki/guazi-sso.env`.

Final report:

- backfill passes run and changed counts
- source/raw/evidence pages in `refinement_scope`
- semantic absorption performed after backfill
- health / graph / G+ quality results
- blockers and remaining missing evidence
