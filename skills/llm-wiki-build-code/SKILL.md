---
name: llm-wiki-build-code
description: LLM Wiki 代码 wiki 构建入口。用于扫描或刷新 raw-code/*，生成 wiki/code/codebases、wiki/code/capabilities、接口映射、graphify 记录和代码证据页。
---

# LLM Wiki Build Code

这是 `$llm-wiki build-code` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-build-code` 后面的用户文本作为 `llm-wiki build-code` 参数。
4. 保持 raw 需求证据和 raw-code 实现证据分层。
5. 最后输出 `建议下一步`。
