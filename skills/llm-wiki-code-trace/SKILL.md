---
name: llm-wiki-code-trace
description: LLM Wiki 需求到代码追踪入口。用于把需求映射到前端页面、URI、后端 Controller/Dubbo/Service 方法、配置、表、消息、任务和证据强度。
---

# LLM Wiki Code Trace

这是 `$llm-wiki code-trace` 的短入口。

1. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/references/commands.md`。
3. 将 `$llm-wiki-code-trace` 后面的用户文本作为 `llm-wiki code-trace` 参数。
4. 使用保守证据标签：`strong`、`partial`、`inferred`、`external`、`missing`。
5. 最后输出 `建议下一步`。
