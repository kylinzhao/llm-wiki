---
name: llm-wiki-fast
description: LLM Wiki 一口气初始化入口。用于从 raw/ 和 BUSINESS_CONTEXT.md 初始化文件型 LLM Wiki，并在一轮内完成首轮精修、可选 raw-code 代码 wiki、健康检查和图谱收口。
---

# LLM Wiki Fast

这是 `$llm-wiki fast` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包内 `references/core-rules.md`（子入口必读；**不要**加载完整 `SKILL.md`）。
2. 读取 `references/commands/_shared.md` 与 `references/commands/fast.md`。
3. 将 `$llm-wiki-fast` 后面的用户文本作为 `llm-wiki fast` 参数。
4. 端到端执行 `llm-wiki fast` 工作流；0-1 默认必须包含阶段 G+（concepts/entities/truth/conflicts/evidence/proposals/reference/operations 二次校准、query acceptance、G+ quality audit），除非 hard blocker 或用户显式要求跳过。
5. 最后输出 `建议下一步`。
