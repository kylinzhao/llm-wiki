---
name: llm-wiki-new-image
description: LLM Wiki 图片证据入口。用于用户明确要求在文本层完成后补充高价值图片、截图、图表、附件证据，或回答特定范围的视觉证据问题。（实验包 llm-wiki-new；与全局 llm-wiki 并行，验证通过后再合并）
---

# LLM Wiki Image

这是 `$llm-wiki-new image` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki-new** skill 包内 `references/core-rules.md`（子入口必读；**不要**加载完整 `SKILL.md`）。
2. 读取 `references/commands/_shared.md` 与 `references/commands/image.md`。
3. 读取同包内 `references/image-evidence.md`。
4. 若候选页面或图片较多，读取同包内 `references/subagent-handoff.md`，并优先使用 subagent 并发处理互不重叠的页面/图片批次。
5. 将 `$llm-wiki-new-image` 后面的用户文本作为 `llm-wiki-new image` 参数。
6. 只处理范围内高价值图片证据；默认不批量分析低价值截图。
7. 主 agent 负责候选排序、任务切分、全局去重、最终合并、health/graph 收口和 `staging/refinement-status.md`；subagent 负责局部页面/图片识别与 note 草稿。
8. 最后输出 `建议下一步`。
