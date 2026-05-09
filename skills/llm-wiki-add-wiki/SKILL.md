---
name: llm-wiki-add-wiki
description: LLM Wiki 添加文档库入口。用于把另一个导出的 wiki、wiki URL、Markdown 文件夹、Confluence 导出、文档目录或业务/需求语料加入当前项目的 raw/ 原始证据层。
---

# LLM Wiki Add Wiki

这是 `$llm-wiki add-wiki` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-add-wiki` 后面的用户文本作为来源路径、wiki URL 和 `llm-wiki add-wiki` 参数。
4. 如果输入是 wiki URL，先尝试从 URL 和平台元数据推导 RSS/feed URL。
5. 如果无法推导 RSS/feed URL，明确告诉用户需要手动提供对应 RSS；用户不提供时保留为空，并说明该来源无法完成后续自动更新。
6. 保留来源记录，不在原地改写证据。
7. 覆盖现有 `raw/` 目录或改变 canonical entity 前必须停下确认。
8. 最后输出 `建议下一步`。
