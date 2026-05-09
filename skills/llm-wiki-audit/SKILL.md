---
name: llm-wiki-audit
description: LLM Wiki 质量审查入口。用于以“问题优先”的方式审查 wiki 可用性、语义一致性、来源页覆盖、实体冲突、证据强度、追踪矩阵、过期页面、健康检查或图谱质量。
---

# LLM Wiki Audit

这是 `$llm-wiki audit` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-audit` 后面的用户文本作为 `llm-wiki audit` 参数。
4. 问题优先，并保持文件引用精确。
5. 最后输出 `建议下一步`。
