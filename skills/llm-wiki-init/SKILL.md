---
name: llm-wiki-init
description: LLM Wiki 分阶段初始化入口。用于从 raw/ 和 BUSINESS_CONTEXT.md 分步初始化新 LLM Wiki 项目，而不是使用一口气初始化模式。
---

# LLM Wiki Init

这是 `$llm-wiki init` 的短入口。

1. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/references/commands.md`。
3. 将 `$llm-wiki-init` 后面的用户文本作为 `llm-wiki init` 参数。
4. 执行分阶段初始化工作流。
5. 最后输出 `建议下一步`。
