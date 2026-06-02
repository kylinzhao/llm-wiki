# Image Evidence

Use this reference only after the requested text layer is complete, or when the user explicitly asks for image evidence.

## Default Policy

- Text first.
- Do not proactively analyze all `raw/**/assets/*`.
- Do not use images as the default retrieval path.
- Store image notes in `staging/image-notes/`.
- Reference raw image paths; do not copy raw images into wiki outputs.
- Text-first commands still need an image inventory. If `raw/` contains images and no image evidence pass is complete, report phase H as pending instead of silently skipping it.

## Inventory Before Analysis

Before multimodal analysis, create a small candidate inventory:

1. Count image assets under `raw/**/assets/`.
2. Identify source pages whose surrounding text suggests high-value evidence: flow, 流程图, 状态, 规则, 费用, 保证金, 风控, 权限, 验收, 测试结论, 数据表, 埋点, 上线.
3. Prefer pages already linked from `wiki/overview.md`, concepts, truth/conflicts, evidence, proposals, operations, or query-acceptance cases.
4. Process high-value candidates first. Leave low-value screenshots unprocessed unless the user asks.
5. Update `staging/refinement-status.md` with image asset count, image note count, status, and next action.

## Subagent Execution

For non-trivial image work, use subagents by default when the current environment supports them.

Use subagents when any of these are true:

- More than 5 candidate source pages.
- More than 20 candidate images.
- Multiple independent business areas are present, such as finance, risk, negotiation, listing, marketing, or launch/testing.
- The user asks to complete image evidence for a whole project, topic, or page set rather than one specific image.

Recommended split:

- One subagent owns 1 complex page, or 2-4 related simple pages.
- Each subagent writes only its assigned files under `staging/image-notes/<source-page-id>/`.
- Each subagent may propose wiki page updates, but the main agent owns edits to `wiki/`, indexes, graph, health, and `staging/refinement-status.md`.
- Do not let two subagents write the same image note file or the same source-page note directory.

Main agent responsibilities:

1. Run/read the candidate inventory.
2. Select high-value pages/images and skip obvious low-value screenshots.
3. Assign disjoint batches to subagents with raw page, wiki source page, image paths, surrounding-context requirements, and output directory.
4. Integrate returned notes, remove duplicates, redact sensitive values, and update target wiki facts only when image evidence strengthens a concrete fact.
5. Update `staging/refinement-status.md` with `image_evidence_status`, counts, completed batches, skipped low-value scope, and next action.

Subagent output per assigned page:

```text
image_batch:
  raw_page:
  wiki_source_page:
  output_dir:
  images_reviewed:
  images_skipped:
  notes_created:
  strengthened_facts:
  proposed_wiki_updates:
  conflicts_with_text:
  sensitive_values_redacted:
  confidence:
  remaining_questions:
```

## Value Tiers

High value, process when relevant:

- Organization or permission diagrams.
- Account, wallet, bank card, recharge, refund, penalty, invoice, or deposit flows.
- Membership rights, enterprise rights, QA validation, launch tables, test conclusions.
- Key process diagrams for onboarding, settlement, risk, finance, or account opening.
- Screenshots that prove fields, states, rules, or business outcomes not present in text.

Medium value, process after high-value items:

- Service framework diagrams.
- Transaction disclosure nodes.
- Mortgage car online flow.
- KA service or operation closed-loop diagrams.
- Product flow screenshots with unique state or rule evidence.

Low value, skip by default:

- Ordinary page walkthroughs.
- Repeated UI screenshots.
- Pure UI issue lists.
- Icons, placeholders, decoration, banners.
- Low-resolution images that cannot support a concrete fact.

## Required Context

Never do bare OCR. For each image:

1. Read the `raw/**/index.md` section where the image appears.
2. Capture the paragraph or heading before and after the image.
3. Interpret visual content together with the surrounding text.
4. Mark confidence and what the image actually proves.

## Note Template

```text
# <image name or stable id>

## Image Path

`raw/.../assets/...`

## Surrounding Text Context

- Before:
- After:

## Visual Content

- ...

## Wiki Facts Strengthened

- fact:
  supporting_context:
  confidence: high | medium | low

## Should Update Wiki

- yes | no
- target_pages:

## Limits

- unreadable text:
- inference:
- unresolved:
```

## Wiki Update Rules

- Add image evidence only when it strengthens a specific wiki fact.
- Keep source text evidence visible next to image-derived evidence.
- Do not turn visual guesses into confirmed business rules.
- If image evidence conflicts with text, record a conflict instead of silently merging.
- Do not expose credentials, internal tokens, account numbers, or private personal data from screenshots.
