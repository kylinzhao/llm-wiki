# Traceability Contract

Traceability has two layers:

- Deterministic tooling scans code, records code anchor candidates, merges worker proposals, preserves decisions, and renders Markdown.
- A trace worker, either the current agent or an external engine worker, reads requirements and code evidence and emits structured proposals.

The trace worker must not edit `wiki/code/traceability/*.md` directly. It writes proposal files only:

```text
staging/traceability/runs/<run_id>/proposals.json
```

`tools/build_traceability.py` merges proposal files into the single long-lived state file:

```text
staging/traceability/state.json
```

## Minimal Proposal Format

```json
{
  "links": [
    {
      "id": "tr_9f2a31c0",
      "requirement": "审批通过后同步数仓",
      "source": "wiki/sources/approval-sync.md",
      "code": [
        "raw-code/procurement/src/ApprovalController.java#ApprovalController.approve",
        "raw-code/procurement/src/ApprovalSyncJob.java#ApprovalSyncJob.syncWarehouse"
      ],
      "strength": "partial",
      "status": "proposed",
      "note": "缺少数仓表名和字段映射配置。"
    }
  ]
}
```

## Link Rules

- `id` should be stable across runs. Prefer `tr_` plus a hash of source, requirement text, and sorted code anchors.
- `requirement` is a concrete requirement point, not just a source page title.
- `source` points to the strongest available requirement page, usually `wiki/sources/<slug>.md`.
- `code` contains code anchors as `raw-code/<codebase_id>/<path>#<symbol>` when a symbol is known, or just the path when it is not.
- `strength` is one of `strong`, `partial`, `inferred`, `external`, or `missing`.
- `status` is usually `proposed`. `confirmed` and `rejected` are preserved by the merger and should only be set by an explicit review workflow or manual state edit.
- `note` must explain why the strength was assigned and what evidence is missing.

## Strength Rules

- `strong`: requirement evidence is explicit; code has both an entry anchor and an implementation anchor; the implementation chain is closed.
- `partial`: code relates to the requirement but a service, job, table, message, config, runtime condition, or other implementation evidence is incomplete.
- `inferred`: naming, adjacency, or graph structure suggests a link, but direct evidence is missing.
- `external`: implementation appears outside available code.
- `missing`: no usable code evidence was found.

Non-`strong` links are still query-visible, but answers must label them as partial evidence, possible related evidence, or gaps.

## Merge Rules

- Same `id`: update generated fields, but preserve `status=confirmed` or `status=rejected`.
- New `id`: append as a new link.
- `rejected` links do not appear in proposed query results unless the user asks about rejected or excluded links.
- The merger renders Markdown from `state.json`; Markdown is not the source of truth.

## Privacy

Proposal files may include paths, symbols, line numbers, and short summaries. They must not include tokens, passwords, cookies, access keys, or complete sensitive configuration values.
