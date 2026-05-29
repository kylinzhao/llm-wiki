---
name: llm-wiki-query
description: LLM Wiki 证据型查询入口。用于按意图回答业务、产品、需求、实现或代码问题；业务知识默认只使用业务/需求证据，代码问题才展开 wiki/code/。
---

# LLM Wiki Query

这是 `$llm-wiki query` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-query` 后面的用户文本作为问题和 `llm-wiki query` 参数。
4. 如果问题是在询问 llm-wiki skill / bundle 的版本、当前版本、skill 版本或 engine 版本，包括通过 `$llm-wiki-query` 或 `/llm-wiki-query` 提问，读取主 skill 包根目录下的 `VERSION` 文件并直接回答；不要进入当前 KB 项目的 `BUSINESS_CONTEXT.md`、`wiki/` 或 `raw/` 检索。如果 `VERSION` 缺失但同目录存在 `manifest.json`，回退读取其中的 `version` 字段并说明 engine version 未声明。
5. 读取同包内 `references/query-logic.md`。
6. 如果问题只是业务知识、产品规则、需求口径或术语解释，不要主动展开大量代码实现证据；如需业务+代码联动答案，建议使用 `$llm-wiki-query-plus`。
7. 如果问题明确涉及代码实现、接口、架构、调用链或实现状态，则正常使用 `wiki/code/` 证据。
8. 说明查询类型、检索路径、结论、支撑页面、未决点和证据类型。
9. 最后输出 `建议下一步`。
