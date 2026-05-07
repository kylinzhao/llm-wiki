---
name: llm-wiki-add-code
description: LLM Wiki 添加代码库入口。用于把另一个本地项目、仓库或源码目录加入当前项目的 raw-code/ 代码证据层，并构建对应代码 wiki 页面。
---

# LLM Wiki Add Code

这是 `$llm-wiki add-code` 的短入口。

1. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/SKILL.md`。
2. 读取 `/Users/zhaoliang/.codex/skills/llm-wiki/references/commands.md`。
3. 将 `$llm-wiki-add-code` 后面的用户文本作为代码路径和 `llm-wiki add-code` 参数。
4. 代码证据放在 `raw-code/<codebase_id>/`，不要混入 `raw/`。
5. 覆盖已有代码库或复制密钥/构建产物前必须停下确认。
6. 最后输出 `建议下一步`。
