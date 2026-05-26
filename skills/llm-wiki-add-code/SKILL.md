---
name: llm-wiki-add-code
description: LLM Wiki 添加代码库入口。用于把另一个本地项目、仓库或源码目录加入当前项目的 raw-code/ 代码证据层，并构建代码 wiki、能力页和必要 traceability。
---

# LLM Wiki Add Code

这是 `$llm-wiki add-code` 的短入口。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-add-code` 后面的用户文本作为代码路径和 `llm-wiki add-code` 参数。
4. 代码证据只能通过受管 git checkout 形式落在 `raw-code/<codebase_id>/`，不要混入 `raw/`，也不要复制、软链或登记外部路径来凑协议。
5. 如果发现仓库权限缺失、clone/fetch 无法读取、或目标目录已存在且不干净，必须立即终止，不要写半成品 raw-code。
6. 构建或刷新 `wiki/code/codebases`、`wiki/code/capabilities`、接口映射、graphify 记录和必要的 `wiki/code/traceability`。
7. 最终报告必须明确说明：当前 codebase 已接成 engine-managed git checkout，后续 `llm-wiki update` 会自动拉取它。
8. 最后输出 `建议下一步`。
