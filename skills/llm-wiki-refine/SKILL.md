---
name: llm-wiki-refine
description: LLM Wiki 精修入口。用于改进来源页、概念页、实体页、分层页面、冲突页或 AI-native 文案，同时保留证据链和确定性构建块。
---

# LLM Wiki Refine

这是 `$llm-wiki refine` 的短入口。

1. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/references/commands.md`。
3. 将 `$llm-wiki-refine` 后面的用户文本作为 `llm-wiki refine` 参数。
4. 除非直接过期，否则保留来源证据、确定性构建块和人工编辑。
5. 最后输出 `建议下一步`。
