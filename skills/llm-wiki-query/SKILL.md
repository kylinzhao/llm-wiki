---
name: llm-wiki-query
description: LLM Wiki 证据型查询入口。用于按意图回答业务、产品、需求、实现或代码问题；业务知识默认只使用业务/需求证据，代码问题才展开 wiki/code/。
---

# LLM Wiki Query

这是 `$llm-wiki query` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-query` 后面的用户文本作为问题和 `llm-wiki query` 参数。
4. 读取同包内 `references/query-logic.md`。
5. 如果问题只是业务知识、产品规则、需求口径或术语解释，不要主动展开大量代码实现证据；如需业务+代码联动答案，建议使用 `$llm-wiki-query-plus`。
6. 如果问题明确涉及代码实现、接口、架构、调用链或实现状态，则正常使用 `wiki/code/` 证据。
7. 说明查询类型、检索路径、结论、支撑页面、未决点和证据类型。
8. 最后输出 `建议下一步`。
