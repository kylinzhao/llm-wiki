---
name: llm-wiki-query-plus
description: LLM Wiki 联合查询入口。用于在同一个问题中同时回答业务/需求口径与代码实现证据，适合需要更详尽的业务+代码联动分析。
---

# LLM Wiki Query Plus

这是 `$llm-wiki query-plus` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md` 和 `references/query-logic.md`。
3. 将 `$llm-wiki-query-plus` 后面的用户文本作为问题和 `llm-wiki query-plus` 参数。
4. 同时检索业务/需求证据与 `wiki/code/` 代码证据，区分业务口径、代码实现、推断和缺失证据。
5. 回答可以比普通 `query` 更详尽，但必须保留证据强度，不要把推断写成源码事实。
6. 最后输出 `建议下一步`。
