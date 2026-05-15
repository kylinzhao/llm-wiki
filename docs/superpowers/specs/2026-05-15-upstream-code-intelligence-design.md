# Upstream Code Intelligence Design

Date: 2026-05-15
Status: Draft approved in brainstorming
Scope: `llm-wiki` code-side protocol and command model

## Summary

This design extends `llm-wiki` so a `raw-code/<codebase_id>/` repository may optionally contribute an existing code knowledge layer as a first-class input, without requiring every codebase to have one and without assuming frontend and backend projects share the same structure.

The goal is to let projects like `sell-taro` reuse a mature upstream code wiki such as `docs/wiki`, while preserving the current `llm-wiki` guarantees:

- `raw/` remains business and requirement evidence.
- `raw-code/` remains source-of-truth code evidence.
- `wiki/code/*` remains the normalized output layer owned by `llm-wiki`.
- traceability evidence strength remains conservative and auditable.

## Problem

The current code-side workflow assumes a simple pipeline:

1. read `raw-code/<codebase_id>/`
2. scan source code and optional graphify output
3. generate `wiki/code/codebases/*`
4. generate `wiki/code/capabilities/*`
5. generate `wiki/code/traceability/*`

This works for codebases that only provide source code, but it underuses repositories that already ship a high-quality compiled code knowledge layer. In `sell-taro`, `docs/wiki` already provides:

- topic pages
- concept pages
- schema and navigation conventions
- source maps
- preferred reading order
- coverage and freshness cues

Today this upstream layer is neither modeled nor consumed explicitly by `llm-wiki`. As a result:

- the agent re-derives navigation that already exists
- capability grouping starts from a colder state than necessary
- codebase pages are overly thin
- command responsibilities feel duplicated across `add-code`, `build-code`, and `code-trace`

## Goals

- Treat upstream code knowledge as an optional first-class code input.
- Support auto-detection for a few stable upstream shapes.
- Support explicit registration for heterogeneous frontend and backend codebases.
- Keep projects without upstream knowledge bases on the current scan-only path.
- Make `build-code` the single recommended command for code knowledge construction, including traceability.

## Non-Goals

- Replacing `raw-code/<codebase_id>/` with upstream wiki output.
- Treating upstream wiki statements as equal to direct source-code anchors.
- Requiring every codebase to ship a code wiki.
- Forcing all upstream knowledge bases into the same directory layout.
- Keeping `code-trace` as a parallel top-level workflow.

## Design

## 1. Evidence Layers

The code side is expanded into four explicit layers.

### Layer A: raw source evidence

Path:

- `raw-code/<codebase_id>/`

Meaning:

- original code evidence
- build files
- runtime configuration
- source files
- repository-local docs such as README, AGENTS, OpenSpec, architecture notes

This remains the highest-authority code input.

### Layer B: upstream code intelligence

Meaning:

- codebase-provided derived knowledge artifacts
- example: `docs/wiki` in `sell-taro`
- future examples may be backend code maps, OpenSpec wiki bundles, generated service maps, or domain-oriented code navigation packages

This layer is first-class input, but must be tagged as derived upstream evidence rather than direct source evidence.

### Layer C: llm-wiki staging

Path:

- `staging/code-graph/<codebase_id>/`

Meaning:

- deterministic code scan outputs
- graphify outputs
- upstream discovery and adaptation artifacts
- machine-readable registry records

This layer records how `llm-wiki` interpreted the codebase and what upstream intelligence was used.

### Layer D: normalized code wiki

Path:

- `wiki/code/codebases/*`
- `wiki/code/capabilities/*`
- `wiki/code/traceability/*`

Meaning:

- the final project-facing code knowledge layer
- the only code layer that should be treated as stable project output

Upstream intelligence may inform this layer, but does not replace it.

## 2. Discovery and Registration

`llm-wiki` should support both auto-detection and explicit registration.

### 2.1 Auto-detection

Auto-detection should only cover a small set of high-confidence upstream shapes.

Example stable shape for `sell-taro`-style upstream wiki:

- `docs/wiki/INDEX.md`
- `docs/wiki/CONTEXT.md`
- `docs/wiki/schema.md`
- `docs/wiki/source-map.jsonl`
- `docs/wiki/index.json`

Detection rule:

- only declare a supported upstream type when a sufficiently complete signature is present
- never infer support from a single directory name alone

### 2.2 Explicit registration

Every codebase may optionally have a registry entry describing its upstream code intelligence.

Recommended machine-readable location:

- `staging/code-graph/code-intelligence-registry.json`

Each record should include at least:

- `codebase_id`
- `upstream_type`
- `root`
- `index_path`
- `schema_path`
- `source_map_path`
- `authority`
- `status`
- `discovery_mode`
- `notes`

`discovery_mode` values:

- `explicit`
- `auto-detected`
- `none`

### 2.3 Priority

Priority order:

1. explicit registration
2. stable auto-detection
3. no upstream intelligence, fallback to source scan only

This allows heterogeneous frontend and backend projects to opt into custom shapes without weakening the common path.

## 3. Retrieval and Build Semantics

Upstream code intelligence should accelerate navigation and candidate narrowing, not silently upgrade evidence strength.

### 3.1 Retrieval order for implementation questions

Recommended code-side retrieval order:

1. `BUSINESS_CONTEXT.md`
2. `wiki/concepts`, `wiki/entities`, `wiki/sources`
3. `wiki/code/capabilities`, `wiki/code/traceability`
4. upstream code intelligence
5. `wiki/code/codebases/<codebase_id>`
6. direct source code when anchors must be verified

Rationale:

- business meaning is still defined by the business and requirement layers
- normalized code pages remain the primary project-facing output
- upstream intelligence is used to narrow search and improve module-level orientation
- direct source remains available for anchor verification

### 3.2 `wiki/code/codebases/*`

When upstream code intelligence exists, each codebase index should include dedicated sections such as:

- upstream code intelligence
- preferred navigation entry
- detected topics and concepts
- coverage and freshness
- evidence boundary

This makes pages like `wiki/code/codebases/sell-taro/index.md` much more useful than a pure deterministic scan summary.

### 3.3 `wiki/code/capabilities/*`

Upstream topic pages are valid capability draft inputs.

They may help:

- cluster related modules
- propose capability names
- reveal established repository terminology
- identify likely page, service, route, or module families

But final capability pages must still separate:

- requirement evidence
- code implementation evidence
- upstream intelligence assistance
- inference
- missing evidence

### 3.4 `wiki/code/traceability/*`

Traceability remains conservative.

Upstream intelligence may contribute:

- candidate requirement-to-topic mappings
- candidate page, route, service, API, or task entry points
- candidate terminology and alias normalization

But evidence strength rules do not change:

- `strong`: direct requirement anchor and direct code anchor both verified
- `partial`: source and code family are related, but implementation detail is incomplete
- `inferred`: relation is suggested by naming, adjacency, or upstream grouping only
- `external`: implementation boundary is outside the available codebase set
- `missing`: no reliable mapping yet

An upstream wiki alone is never sufficient to justify `strong`.

## 4. Command Model

The command surface should be simplified.

### 4.1 `llm-wiki add-code`

Purpose:

- connect a new codebase to the wiki project

Responsibilities:

- add or register `raw-code/<codebase_id>/`
- detect upstream code intelligence when present
- create or update the code intelligence registry entry
- record the codebase as available for future builds

Non-responsibilities:

- full capability generation
- full traceability generation
- full code knowledge rebuild

User outcome:

- the project now knows this codebase exists and how to interpret its upstream intelligence, if any

### 4.2 `llm-wiki build-code`

Purpose:

- single recommended command for the full code knowledge pipeline

Responsibilities:

- read `BUSINESS_CONTEXT.md`
- read registry and auto-discovered upstream intelligence
- adapt upstream metadata into staging artifacts
- run deterministic source scan
- run optional graphify
- generate or update `wiki/code/codebases/*`
- generate or update `wiki/code/capabilities/*`
- generate or update `wiki/code/traceability/*`
- run code-side validation and closing checks

Important rule:

- traceability is built inside `build-code`
- `build-code` is the only recommended top-level code knowledge build command

### 4.3 `llm-wiki update`

Purpose:

- impact-scoped incremental maintenance

Responsibilities when code-side inputs changed:

- detect whether source code changed
- detect whether upstream intelligence changed
- detect whether both changed
- refresh only affected codebase pages, capability pages, and traceability rows
- rerun necessary code-side health, graph, and anchor checks

### 4.4 Remove `code-trace` as a top-level command

`code-trace` should not remain a separate top-level workflow.

Reason:

- it duplicates the conceptual surface of `build-code`
- it suggests traceability is independent from codebase and capability construction
- it makes the command model harder to explain and maintain

After this design:

- traceability remains a required output
- but it becomes an internal phase of `build-code`

## 5. Adaptation Artifacts

To keep adaptation deterministic and inspectable, `build-code` should write upstream-derived staging files under:

- `staging/code-graph/<codebase_id>/upstream-discovery.json`
- `staging/code-graph/<codebase_id>/upstream-summary.json`
- `staging/code-graph/<codebase_id>/upstream-topics.json`
- `staging/code-graph/<codebase_id>/upstream-concepts.json`

These artifacts should summarize:

- upstream type
- discovery mode
- entry pages
- topic inventory
- concept inventory
- freshness metadata
- source-map availability
- adaptation warnings

This keeps the final wiki readable while preserving machine-readable provenance.

## 6. Fallback Behavior

Projects without upstream intelligence remain fully supported.

Fallback path:

- no registry entry
- no stable auto-detection hit
- continue with source scan and optional graphify only

This fallback must be treated as normal behavior, not a degraded error state.

## 7. Risks

### Risk: over-trusting upstream wiki content

Mitigation:

- classify upstream intelligence as derived evidence
- require source-code verification for `strong` traceability

### Risk: false positives in auto-detection

Mitigation:

- only support a small number of complete signatures
- prefer explicit registration over detection

### Risk: command sprawl

Mitigation:

- keep `add-code` narrow
- move all traceability generation under `build-code`
- keep `update` as the single incremental orchestrator

### Risk: heterogeneous backend and frontend shapes

Mitigation:

- allow registry-based upstream type declarations
- treat auto-detection as convenience, not as the universal protocol

## 8. Rollout Plan

### Phase 1

- define terminology in `SKILL.md` and references
- define the registry schema
- document `build-code` as the unified code build command
- deprecate top-level `code-trace` in docs

### Phase 2

- support `sell-taro`-style upstream detection and adaptation
- enrich `wiki/code/codebases/*` with upstream sections
- surface upstream status in `doctor`

### Phase 3

- add more upstream adapters for heterogeneous codebase types as they appear
- improve incremental invalidation in `update`

## 9. Open Decisions Resolved During Brainstorming

- upstream code intelligence is a first-class optional code input
- not all `raw-code` projects are expected to provide it
- frontend and backend structures are not assumed to match
- the default mode is mixed: stable auto-detection plus explicit registration
- `add-code` is kept but narrowed to codebase onboarding
- `build-code` becomes the single recommended command for full code knowledge construction
- top-level `code-trace` is removed and absorbed into `build-code`

## 10. Recommended Next Step

Write the implementation plan around these changes in three slices:

1. docs and protocol updates
2. registry and discovery support
3. `build-code` and `update` integration
