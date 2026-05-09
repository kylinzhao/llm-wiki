---
name: llm-wiki-update
description: LLM Wiki 增量更新入口。用于 raw/、BUSINESS_CONTEXT.md、raw-code/、wiki 页面或源码变更后，只更新受影响的 wiki、代码 wiki、能力页、追踪矩阵、健康检查和图谱。
---

# LLM Wiki Update

这是 `$llm-wiki update` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-update` 后面的用户文本作为 `llm-wiki update` 参数。
4. 优先使用项目内更新入口，例如 `uv run python tools/update_wiki.py`。
5. 刷新受影响页面；除非直接过期，否则保留人工编辑。
6. 如果同一轮变更同时影响 source 精修和代码追踪，把 source 精修、capability 更新、code-trace 刷新作为同一个 update 收口动作。
7. 如果发现当前命令可以安全完成的 pending/stale/source/code-trace/health/graph 工作，继续完成，不要建议用户再跑一次同一个 update。
8. 最后输出 `建议下一步`。
