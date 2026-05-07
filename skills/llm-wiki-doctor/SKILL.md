---
name: llm-wiki-doctor
description: LLM Wiki 只读诊断入口。用于判断 wiki 项目是否健康、缺什么、哪里过期、下一步做什么，或输出站点级健康画像。
---

# LLM Wiki Doctor

这是 `$llm-wiki doctor` 的短入口。

1. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/references/commands.md`。
3. 将 `$llm-wiki-doctor` 后面的用户文本作为 `llm-wiki doctor` 参数。
4. 只做只读检查，不修改项目文件。
5. 最后输出 `建议下一步`。
