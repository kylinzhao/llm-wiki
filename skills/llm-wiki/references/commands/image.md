## `llm-wiki image`

Only after text completion or explicit user request. Follow `image-evidence.md`.
Start by inventorying candidate pages and images, then process only high-value evidence by default.
For whole-project, multi-page, or large image scopes, use subagents by default when available. Split by source page or related page bundles, keep each worker's write scope under a unique `staging/image-notes/<source-page-id>/` directory, and let the main agent own final wiki integration, health/graph, and `staging/refinement-status.md`.
Update `staging/refinement-status.md` with `image_evidence_status` and a concise checkpoint.
