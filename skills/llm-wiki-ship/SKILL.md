---
name: llm-wiki-ship
description: LLM Wiki 发布收口入口。用于将 wiki 工作验证并准备提交、推送或发布，包括健康检查、图谱、可选锚点检查，以及 raw/ 不提交检查。
---

# LLM Wiki Ship

这是 `$llm-wiki ship` 的短入口。

1. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/references/commands.md`。
3. 将 `$llm-wiki-ship` 后面的用户文本作为 `llm-wiki ship` 参数。
4. 发布前先验证，并确保 `raw/` 没有被 staged 或 tracked。
5. 只有 remote 和意图明确时才提交或推送。
6. 最后输出 `建议下一步`。
