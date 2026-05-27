# LLM Wiki Semantic Refinement Contract

This contract is shared by local `llm-wiki update/refine` work and Gateway Cursor SDK maintenance.

## Required Inputs

- Read `BUSINESS_CONTEXT.md`.
- Read `staging/update/latest.json` when present.
- Read `staging/refinement-plan.json`.
- Read `staging/refinement-status.md` when present.
- Read every raw/source/dependent page listed in the refinement plan before editing.

## Write Scope

- Treat `raw/**` and `raw-code/**` as read-only evidence.
- Write only paths listed in `allowed_write_paths`.
- Preserve manual edits and existing refined prose unless the plan marks that page stale.
- Record completed and skipped work in `staging/refinement-status.md`.

## Source Page Shape

Affected source pages must include:

- `Summary`
- `Key Facts`
- `Business Links`
- `Evidence Notes`

Do not leave deterministic placeholders such as `Pending AI-native summary`.

## Evidence Rules

- Record evidence paths, especially the raw path for every required source page.
- Do not present inference as fact.
- Do not turn code existence into business policy.
- Keep requirement evidence and code evidence distinct.

## Final Report

Return changed files, evidence paths, skipped reasons, and remaining gaps.
