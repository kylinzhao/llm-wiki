# Cjira Status Registry Design

Date: 2026-05-26
Status: Draft approved in brainstorming
Scope: `llm-wiki` source extraction, update workflow, and query/mapping status semantics

## Summary

This design adds a persistent registry for pages that contain `cjira` references or `idea` signals, and uses that registry to classify each document as one of:

- `idea`
- `in_progress`
- `frozen`

The goal is to make downstream query and mapping behavior depend on document state instead of treating every page as equally stable evidence.

The design keeps the current `llm-wiki` evidence model intact:

- `raw/` remains immutable source evidence.
- `wiki/sources/` remains the normalized source page layer.
- `wiki/` remains the query-facing knowledge layer.
- `staging/` stores machine-readable registry and cache state.

## Problem

In current Cwiki exports, some pages contain `cjira` references that represent the development task behind the requirement. These references can appear in several forms:

- a main issue in a revision table
- a secondary issue in a `【JIRA 编号】`-style section
- a link with placeholder text such as `正在获取问题细节。。。状态`
- a title that explicitly marks the page as `【IDEA】`

Today, `llm-wiki` has no dedicated structure for tracking which pages are bound to which `cjira` issues, whether those issues are still active, and whether a page should be treated as an idea rather than a frozen evidence page.

This causes two concrete gaps:

1. Incremental updates do not know which issue states should be refreshed.
2. Query and mapping flows cannot reliably distinguish stable evidence from in-progress or idea-stage material.

## Goals

- Track all pages that contain `cjira` or `idea` signals in a persistent registry.
- Use the main `cjira` to determine page state by default.
- Treat references explicitly placed under `【JIRA 编号】` as supporting issues, not the main issue, unless the page structure clearly indicates otherwise.
- Avoid pure regex-only extraction; use surrounding structure and context.
- Refresh tracked `cjira` states during build and update.
- Remove frozen `cjira` entries from the active registry after they reach a terminal state.
- Preserve historical `idea` pages so they can later become formal requirements.
- Make query and mapping logic state-aware.

## Non-Goals

- Replacing the source page model with a Jira-only model.
- Inferring full semantic meaning from `cjira` alone.
- Attempting to normalize every possible Jira workflow status across all teams.
- Automatically rewriting source documents to inject `cjira` metadata.

## Proposed Model

## 1. Registry Layers

The design adds two persistent machine-readable layers under `staging/`.

### 1.1 Active registry

Path:

- `staging/cjira-registry/active.json`

Purpose:

- Track pages whose state is not yet frozen.
- Record the page's main issue, supporting issues, idea flag, and last checked state.
- Provide the update workflow with a list of pages that need state refresh.

### 1.2 Archive registry

Path:

- `staging/cjira-registry/archive.json`

Purpose:

- Preserve frozen pages and terminal `cjira` history.
- Keep historical `idea` pages even after they are promoted.
- Avoid losing provenance when an issue transitions out of the active set.

### 1.3 Issue state cache

Path:

- `staging/cjira-registry/cache.json`

Purpose:

- Cache the latest fetched `cjira` status values.
- Reduce repeated lookups during a single update run or across nearby runs.
- Store fetch timestamps and source URLs for auditability.

## 2. Registry Record Shape

Each page record should include at least:

- `page_id`
- `page_path`
- `title`
- `doc_status`
- `primary_cjira`
- `supporting_cjira[]`
- `idea_flag`
- `status_source`
- `primary_cjira_status`
- `primary_cjira_terminal`
- `last_checked_at`
- `source_anchor`
- `confidence`

Recommended status values:

- `doc_status`: `idea` / `in_progress` / `frozen`
- `primary_cjira_terminal`: `true` / `false`

Suggested `confidence` values:

- `high`
- `medium`
- `low`

## 3. Main Issue Selection

The main `cjira` is not chosen by a blind regex pass. The extractor should combine structure and context:

1. Prefer issues that appear in the document's main revision record or main summary block.
2. Prefer issues that are not explicitly labeled as `【JIRA 编号】`.
3. If an issue appears in a section or cell named `JIRA 编号`, treat it as supporting by default.
4. If there are multiple candidates, use page structure and local context to decide which one is primary.
5. If the structure is ambiguous, keep the page in the registry with `confidence=low` rather than guessing silently.

This matches the user's constraint: the page should be bound to a primary `cjira`, but contextual labels such as `【JIRA 编号】` must override naive positional matching.

## 4. `idea` Detection

`idea` is a first-class page state.

### 4.1 Strong signal

If the page title contains `【IDEA】`, mark `idea_flag=true` immediately.

### 4.2 Soft signal

If the title does not contain `【IDEA】`, the page may still be marked as `idea` when the content clearly describes:

- a concept proposal
- an exploration
- an uncommitted direction
- a future candidate requirement

This should be a semantic judgment, not only a string rule.

### 4.3 Interaction with other states

`idea` overrides the outward `doc_status` if the page is still in idea stage, even when a `cjira` exists.

The `cjira` facts are still recorded, because the page may later be promoted into a formal requirement.

## 5. `cjira` Status Classification

The main `cjira` status determines whether the page is frozen or still active.

### 5.1 Terminal states

If the main `cjira` is in a terminal state, the page becomes `frozen`.

The exact terminal state list should be configurable, but the default interpretation is:

- terminal means the issue is done, closed, or otherwise no longer active
- non-terminal means the issue is still active, in progress, or pending work

### 5.2 Non-terminal states

If the main `cjira` is not terminal, the page remains `in_progress`.

### 5.3 Unknown states

If the status lookup fails or returns an unfamiliar workflow state, the page remains active and is marked with lower confidence rather than being misclassified as frozen.

## 6. Update Workflow

The update workflow should operate in this order:

1. Scan source pages and extract candidate `cjira` references plus `idea` signals.
2. Resolve the main `cjira` and supporting `cjira` list for each page.
3. Refresh the status of every `cjira` currently in the active registry.
4. Update each page's `doc_status`.
5. Move frozen pages from `active.json` to `archive.json`.
6. Keep `idea` records in the registry even if no `cjira` has been assigned yet.

This is intentionally stateful. It avoids the failure mode where incrementals only know about changed pages but forget about older linked issues.

## 7. Status Expiration and Deletion

The user requirement is that frozen `cjira` entries can be removed from the active registry.

That means:

- active registry contains only pages that still need refreshing
- frozen pages are archived, not discarded
- cache entries may remain until they age out or are superseded

This preserves history while keeping the active set small enough to refresh efficiently.

## 8. Query and Mapping Semantics

Downstream consumers should treat page state as part of the answer contract.

### 8.1 Query behavior

When a query touches a page with registry data:

- `idea` pages should be described as ideas, proposals, or exploratory evidence
- `in_progress` pages should be described as active requirements or in-progress evidence
- `frozen` pages may be treated as stable evidence

If a query asks for current status, the answer should include both the document status and the main `cjira` status when available.

### 8.2 Mapping behavior

When building query mappings or traceability:

- prefer `frozen` pages for durable mappings
- allow `in_progress` pages as provisional mappings
- mark `idea` pages as candidates, not authoritative implementation targets

This prevents the knowledge base from overstating certainty.

## 9. Failure Handling

If `cjira` lookup fails:

- keep the last known cached status
- mark the fetch as stale
- do not silently upgrade the page to frozen
- surface the failure in update diagnostics

If page structure is ambiguous:

- keep the page in the active registry
- lower confidence
- prefer manual review over silent misclassification

## 10. Testing

The implementation should be validated with cases that cover:

- a page with one main `cjira` in the revision table
- a page with a supporting issue under `【JIRA 编号】`
- a page with multiple issue references and one primary candidate
- a page titled `【IDEA】`
- a page whose title lacks `【IDEA】` but whose content is clearly exploratory
- a page whose main `cjira` is terminal and moves from active to archive
- a page whose `cjira` lookup fails and must remain active

Recommended checks:

- extraction unit tests for main/supporting issue selection
- registry update tests for active-to-archive transitions
- query formatting tests to ensure state-aware wording
- regression tests for pages with non-standard or noisy characters around `cjira`

## 11. Rollout Notes

The registry should be introduced without breaking existing builds:

- pages without `cjira` or `idea` continue through the current path
- registry population is additive at first
- update can start by recording and caching before any pruning behavior is enabled
- active registry deletion of frozen issues should happen only after archive writes succeed

## 12. Open Questions

- What exact Jira workflow states should count as terminal in this environment?
- Should terminal-state classification be configurable per project?
- Should `supporting_cjira` be retained in archive records after the main issue freezes?
- Should `idea` pages without a `cjira` be promoted automatically once a primary issue appears, or remain as history with a state transition record?

