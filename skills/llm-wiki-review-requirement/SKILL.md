---
name: llm-wiki-review-requirement
description: LLM Wiki 需求评审兼容入口。先检索项目 BUSINESS_CONTEXT/raw/wiki/raw-code 知识库证据，再加载上游 prd-review-max 做 PRD/Spec 业务与 UX 评审；支持产品/完整/快速/评分概览及 Cwiki 评论稿。
---

# LLM Wiki Review Requirement

这是兼容入口。评审能力由 **`$requirement-review`** 提供（知识库证据 + **`$prd-review-max`**）。

语言要求：用户回答默认中文；写入 LLM Wiki 文档时也用中文，除非用户明确要求其他语言。

## 执行步骤

1. 读取 **requirement-review** skill 包根目录 `SKILL.md`。
2. 读取同包 `references/kb-evidence-bridge.md`。
3. 若环境中无 **prd-review-max**，在 llm-wiki-skill 根目录运行 `./scripts/install_prd_review_max.sh --link --client auto`，然后读取 **prd-review-max** 的 `SKILL.md` 与其 `references/**`（**勿修改 prd-review-max 包内文件**）。
4. 将 `$llm-wiki-review-requirement` 后的用户文本作为目标需求与评审参数。
5. 当前项目是 LLM Wiki 项目时，**必须**完成知识库检索（`BUSINESS_CONTEXT.md`、`raw/`、`wiki/`、`raw-code/`、`wiki/code/`），并在 prd-review-max 结果后输出影响范围、历史冲突、实现差异与 Cwiki 评论版。
6. 评审范围/模式以 prd-review-max 为准；用户说法映射见 `kb-evidence-bridge.md`。未指定时默认：业务评审 + 用户体验评审，业务模式：产品。

## 输出

- prd-review-max 完整诊断（基础检测 + 业务 + UX，按 routing 顺序）
- 知识库证据范围、MECE 影响范围、历史规则冲突、已有实现差异
- P0/P1/P2 findings、Cwiki 评论版、`建议下一步`
