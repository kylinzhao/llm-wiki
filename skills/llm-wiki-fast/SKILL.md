---
name: llm-wiki-fast
description: LLM Wiki 一口气初始化入口。用于从 raw/ 和 BUSINESS_CONTEXT.md 初始化文件型 LLM Wiki，并在一轮内完成首轮精修、可选 raw-code 代码 wiki、健康检查和图谱收口。
---

# LLM Wiki Fast

这是 `$llm-wiki fast` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-fast` 后面的用户文本作为 `llm-wiki fast` 参数。
4. 端到端执行 `llm-wiki fast` 工作流。
5. 最后输出 `建议下一步`。
