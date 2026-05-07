---
name: llm-wiki-resume
description: LLM Wiki 续跑入口。用于上次 wiki 构建、精修、代码 wiki、追踪矩阵、图片、健康检查或图谱任务中断后，从状态文件或 checkpoint 继续，而不是重头开始。
---

# LLM Wiki Resume

这是 `$llm-wiki resume` 的短入口。

1. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/references/commands.md`。
3. 将 `$llm-wiki-resume` 后面的用户文本作为 `llm-wiki resume` 参数。
4. 从 `staging/refinement-status.md`、health、graph 和 checkpoint 状态续跑。
5. 除非证据已变化，不要重启已完成阶段。
6. 最后输出 `建议下一步`。
