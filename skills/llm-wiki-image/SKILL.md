---
name: llm-wiki-image
description: LLM Wiki 图片证据入口。用于用户明确要求在文本层完成后补充高价值图片、截图、图表、附件证据，或回答特定范围的视觉证据问题。
---

# LLM Wiki Image

这是 `$llm-wiki image` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 读取同包内 `references/image-evidence.md`。
4. 若候选页面或图片较多，读取同包内 `references/subagent-handoff.md`，并优先使用 subagent 并发处理互不重叠的页面/图片批次。
5. 将 `$llm-wiki-image` 后面的用户文本作为 `llm-wiki image` 参数。
6. 只处理范围内高价值图片证据；默认不批量分析低价值截图。
7. 主 agent 负责候选排序、任务切分、全局去重、最终合并、health/graph 收口和 `staging/refinement-status.md`；subagent 负责局部页面/图片识别与 note 草稿。
8. 最后输出 `建议下一步`。
