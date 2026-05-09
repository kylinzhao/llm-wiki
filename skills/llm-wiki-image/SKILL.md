---
name: llm-wiki-image
description: LLM Wiki 图片证据入口。用于用户明确要求在文本层完成后补充高价值图片、截图、图表、附件证据，或回答特定范围的视觉证据问题。
---

# LLM Wiki Image

这是 `$llm-wiki image` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 读取同包内 `references/image-evidence.md`。
4. 将 `$llm-wiki-image` 后面的用户文本作为 `llm-wiki image` 参数。
5. 只处理范围内高价值图片证据；默认不批量分析低价值截图。
6. 最后输出 `建议下一步`。
