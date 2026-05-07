---
name: llm-wiki-review-requirement
description: LLM Wiki 需求评审兼容入口。用于用户仍以 llm-wiki 方式调用需求 review 时，转向独立的 requirement-review skill，对 PRD、Cwiki 页面、Markdown 需求、图片、zip/HTML 原型和前端交互说明做 evidence-first review。
---

# LLM Wiki Review Requirement

这是兼容入口。真正的需求评审能力已独立到 `$requirement-review`。

1. 读取 `/Users/zhaoliang/.codex/skills/requirement-review/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/requirement-review/references/review-protocol.md`。
3. 若涉及前端，读取 `/Users/zhaoliang/.codex/skills/requirement-review/references/fe-prd-review.md`。
4. 将 `$llm-wiki-review-requirement` 后面的用户文本作为 `$requirement-review` 的目标需求参数。
5. 如果当前项目是 LLM Wiki 项目，可以把 `BUSINESS_CONTEXT.md`、`raw/`、`wiki/`、`raw-code/`、`wiki/code/` 作为证据层；不要再依赖 `$llm-wiki` 主 skill 的命令协议。
6. 输出 findings-first 完整报告、前端需求完整性审查、图片与 zip 原型证据、验收清单、待决问题、Cwiki 评论版和 `建议下一步`。
