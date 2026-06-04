---
name: llm-wiki-refine
description: LLM Wiki 主动语义精修入口。用于用户明确要求精修 source/concept/entity/wiki 页面、消化 refinement pending 或 G+ 欠拟合；shared 模式默认验证后 commit and push。
---

# LLM Wiki Refine

这是 `$llm-wiki refine` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包内 `references/core-rules.md`（子入口必读；**不要**加载完整 `SKILL.md`）。
2. 读取 `references/commands/_shared.md` 与 `references/commands/refine.md`。
3. 将 `$llm-wiki-refine` 后面的用户文本作为 `llm-wiki refine` 参数。
4. `refine` 是主动语义精修命令；`update` 仍可自动进入 refinement，但用户明确要求“精修/refine/消化 pending refinement/G+ 语义加厚”时可以直接走本入口。
5. 默认 shared 模式：精修前执行 update 同口径 git preflight / pull，精修和 validation 通过后对 allowlisted KB 产物 commit and push。只有用户显式使用 `--local` 或 `LLM_WIKI_UPDATE_MODE=local` 时，才跳过共享发布。
6. 结束前必须输出 `建议下一步`。
