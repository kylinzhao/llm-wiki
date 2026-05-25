---
name: llm-wiki-init
description: LLM Wiki 分阶段初始化入口。用于从 raw/ 和 BUSINESS_CONTEXT.md 分步初始化新 LLM Wiki 项目，而不是使用一口气初始化模式。
---

# LLM Wiki Init

这是 `$llm-wiki init` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-init` 后面的用户文本作为 `llm-wiki init` 参数。
4. 执行分阶段初始化工作流；如果用户没有要求只停在骨架/基线，0-1 初始化应继续到阶段 G+（concepts/entities/truth/conflicts/evidence/proposals/reference/operations 二次校准、query acceptance、G+ quality audit）。若分阶段暂停在 G+ 之前，最终报告必须标明 G+ pending。
5. 最后输出 `建议下一步`。
