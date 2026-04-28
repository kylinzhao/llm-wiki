# Image Evidence

Use this reference only after the requested text layer is complete, or when the user explicitly asks for image evidence.

## Default Policy

- Text first.
- Do not proactively analyze all `raw/**/assets/*`.
- Do not use images as the default retrieval path.
- Store image notes in `staging/image-notes/`.
- Reference raw image paths; do not copy raw images into wiki outputs.

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
