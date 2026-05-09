---
name: llm-wiki-query
description: LLM Wiki 证据型查询入口。用于回答业务、产品、需求、实现或代码问题，并基于 BUSINESS_CONTEXT.md、wiki/ 和可选 wiki/code/ 证据给出结论。
---

# LLM Wiki Query

这是 `$llm-wiki query` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-query` 后面的用户文本作为问题和 `llm-wiki query` 参数。
4. 说明查询类型、检索路径、结论、支撑页面、未决点和证据类型。
5. 最后输出 `建议下一步`。
