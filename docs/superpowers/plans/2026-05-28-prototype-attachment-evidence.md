# Prototype Attachment Evidence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert wiki zip prototypes into durable raw evidence notes so normal LLM Wiki source refinement can analyze them with the parent wiki.

**Architecture:** Keep raw evidence reproducible by materializing attachments into Markdown sidecar notes under the page `assets/` directory. The Confluence exporter discovers and downloads evidence; the deterministic wiki builder indexes generated evidence notes as normal text sources.

**Tech Stack:** Python standard library, `requests`, BeautifulSoup, unittest.

---

## Chunk 1: Export Evidence Sidecars

### Task 1: Zip Prototype Evidence

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/confluence_sync/export_confluence_tree.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_export_confluence_prototype_evidence.py`

- [ ] Write a failing unittest that builds a fake Cwiki page with a `.zip` attachment, returns a small zip containing `index.html`, and expects `assets/prototype.zip`, `assets/prototype.zip.prototype.md`, extracted files under `assets/prototypes/prototype/`, and a page Markdown section linking the evidence note.
- [ ] Run that test and verify it fails because the function does not exist or returns no prototype evidence.
- [ ] Implement zip attachment discovery, download, safe extraction, HTML entry point summarization, and Markdown sidecar generation.
- [ ] Run the focused test and verify it passes.

## Chunk 2: Index Generated Evidence

### Task 3: Builder Includes Prototype Evidence Notes

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/build_wiki.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_build_wiki_source_v2.py`

- [ ] Write a failing unittest that places `raw/page/assets/prototype.zip.prototype.md` under raw and expects `build_wiki` to create a source page for it.
- [ ] Run that test and verify it fails if generated evidence is excluded or slugged incorrectly.
- [ ] Adjust source discovery only as needed so generated `.md` evidence notes are indexed while binary zip files remain non-sources.
- [ ] Run the focused build wiki tests and verify they pass.

## Chunk 3: Protocol Documentation And Regression

### Task 4: Document Main Skill Behavior

**Files:**
- Modify: `skills/llm-wiki/SKILL.md`
- Modify: `skills/llm-wiki/references/commands.md`
- Modify if needed: `skills/llm-wiki/references/build-and-maintenance.md`

- [ ] Update normal init/fast/update protocol to say zip prototype evidence sidecars are part of text evidence after export.
- [ ] Keep requirement-review rules stricter: it still performs mandatory detailed prototype/image review.
- [ ] Run install and Python unittest suites.
