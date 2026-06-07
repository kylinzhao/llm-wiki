## `llm-wiki doctor`

Purpose: read-only diagnosis and quality review of the whole LLM Wiki site. Use it when the user asks “现在状态如何”, “还缺什么”, “下一步干什么”, “这个 wiki 健康吗”, “帮我审查一下这个 wiki”, or wants a project-level operating recommendation.

Read:

1. `BUSINESS_CONTEXT.md`
2. `wiki/index.md`（仅读头部：入口链接 + 来源域统计表；不读来源明细列表）
3. `wiki/overview.md`
4. `docs/retrieval-playbook.md`
5. `docs/build-and-maintenance.md`
6. `staging/refinement-status.md`
7. `staging/health/latest.json`
8. `graph/summary.md`
9. `wiki/code/index.md`
10. `wiki/code/traceability/index.md`
11. `docs/query-acceptance.md`
12. `docs/gplus-quality-audit.md`
13. `staging/image-notes/` and `staging/refinement-status.md` image evidence fields when present

If any file is missing, report it as a signal. Do not create or modify files.

Optional read-only checks:

- Count `raw/*/index.md` and `wiki/sources/*.md`.
- Review entry usability, semantic consistency, source coverage, evidence strength, traceability quality, stale pages, health, and graph quality.
- Check G+ semantic thickness with the same heuristic used by update: source count vs non-index concept/entity pages, source-to-concept/entity coverage, manual concept/entity placeholders, index-only or low-density G+ layers, stale query acceptance / quality audit counts.
- Surface P0/P1/P2 findings directly in `主要问题`; do not require a separate `audit` command.
- Count image assets under `raw/**/assets/` and image notes under `staging/image-notes/`.
- When image assets exist without a completed image evidence pass, list prioritized image refinement candidate pages, using signals such as flow diagrams, state screenshots, money/account/risk/permission terms, launch tables, test conclusions, data tables, tracking, and pages already central to overview/concepts/query acceptance.
- Count generated prototype evidence notes under `raw/**/assets/*.prototype.md`; flag linked zip evidence that has no sidecar note.
- Count drawio source pages under `wiki/sources/*.drawio.md` and check `drawio_promotion` status from the health report. When `not_promoted_count > 0`, list the top not-promoted drawio pages and recommend `llm-wiki update` for agent-native drawio knowledge promotion into concept/overview pages.
- Count `wiki/code/codebases/*`, `wiki/code/capabilities/*.md`, and `wiki/code/traceability/*.md`.
- Inspect latest health status.
- Inspect graph node / edge counts.
- Search for broken or stale markers.
- If traceability pages exist, sample evidence strength distribution.
- If code anchors are used, recommend anchor check when not recently run.

Output shape:

```text
诊断类型：llm-wiki doctor
已使用 BUSINESS_CONTEXT.md：是/否
读取路径：

总体 verdict：

状态画像：
- 输入层：
- 文档层：
- drawio 层：`drawio_repair.py` 确定性转换状态（auto-converted X/Y, Z missing）
- 图片证据层：截图/照片 AI 筛选状态（与 drawio 分开报告）
- 代码层：
- 追踪矩阵：
- 校验层：
- 发布/维护状态：

主要问题：
- P0 ...
- P1 ...
- P2 ...

建议下一步：
1. ...
2. ...
3. ...
```

Verdict levels:

- `healthy`: health/graph pass, retrieval docs exist, source coverage complete, no urgent gaps.
- `usable-with-gaps`: wiki answers common questions but has traceability, code, image, or stale gaps.
- `needs-maintenance`: health/graph/staleness/coverage problems should be fixed before relying on it.
- `blocked`: missing required inputs or broken core structure.

Recommendation rules:

- If required inputs or entry docs are missing, recommend `llm-wiki init` or `llm-wiki update`.
- If source coverage or refinement is incomplete, recommend `llm-wiki update`.
- If query acceptance or quality audit artifacts are missing, recommend `llm-wiki update` to refresh them.
- If G+ semantic underfit is P1/P2, recommend `llm-wiki update` for agent-native G+ semantic expansion. This is separate from health: a wiki can be structurally healthy and still need G+ expansion.
- If there is no P0/P1 and important P2 findings remain, promote the highest-value P2 findings to P1 for the next maintenance pass. Use this for recurring debt such as image evidence unknown, Cjira stale/low-confidence status quality, orphan source pages, or G+ thin layers.
- If text/G+ is healthy but `raw/` contains image assets and no image evidence pass is recorded, recommend `llm-wiki image` for selective high-value multimodal refinement. Treat this as a non-blocking evidence gap unless core pages depend on diagrams, table screenshots, state screenshots, money/account/risk/permission flows, launch tables, or test conclusions. **Drawio exclusion**: drawio diagrams are handled by `drawio_repair.py` (deterministic pipeline); only mention drawio in recommendations when `missing_evidence_count > 0`. Never conflate drawio and screenshot/photo status.
- When recommending `llm-wiki image`, include the top candidate pages from health output or a read-only scan, not only the total image count. Do not include drawio diagrams in the image candidate list.
- If code wiki exists but traceability is thin, recommend `llm-wiki update` for existing code evidence or `llm-wiki add-code` when a new codebase must be connected first.
- If files changed recently or stale markers exist, recommend `llm-wiki update`.
- If everything is healthy, say it is reasonable to pause and note what future change should trigger `llm-wiki update`.
