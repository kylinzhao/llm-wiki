---
name: llm-wiki-update
description: LLM Wiki 增量维护入口。用于 raw/、BUSINESS_CONTEXT.md、raw-code/、wiki 页面或源码变更后的影响范围更新，也用于续跑、精修、代码 wiki、能力页、追踪矩阵、健康检查和图谱收口。
---

# LLM Wiki Update

这是 `$llm-wiki update` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-update` 后面的用户文本作为 `llm-wiki update` 参数。
4. 优先使用项目内更新入口，例如 `uv run python tools/update_wiki.py`；如果项目已配置可用 RSS/feed，同步原始 wiki 证据应作为 update 的默认前置步骤，而不是等用户额外提醒。只要项目已接入 `raw-code/<codebase_id>/` git worktree，同一次 update 也应默认先安全刷新这些干净 codebase，再继续 code wiki 构建；如有特殊刷新命令，则按项目 manifest 覆盖。
5. 刷新受影响页面；除非直接过期，否则保留人工编辑。
6. 如果同一轮变更同时影响 source 精修和代码追踪，把 source 精修、capability 更新、traceability 刷新作为同一个 update 收口动作。
7. 如果发现当前命令可以安全完成的 pending/stale/source/traceability/health/graph 工作，继续完成，不要建议用户再跑一次同一个 update。
8. update 结束前必须自动执行收口检查：health、graph；如果 traceability 或代码锚点变化，再执行可用的 anchor check。
9. 如果收口检查失败或仍有可安全修复的问题，优先继续修复或建议继续 `llm-wiki update`。
10. 如果收口检查通过且没有阻塞项，在 `建议下一步` 中说明当前 KB 已可使用，并说明未来什么变化应触发下一次 `llm-wiki update`。
11. 最后输出 `建议下一步`。
