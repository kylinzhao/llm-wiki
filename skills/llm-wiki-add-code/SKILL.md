---
name: llm-wiki-add-code
description: LLM Wiki 添加代码库入口。用于把另一个本地项目、仓库或源码目录加入当前项目的 raw-code/ 代码证据层，并构建代码 wiki、能力页和必要 traceability。
---

# LLM Wiki Add Code

这是 `$llm-wiki add-code` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md`。
3. 将 `$llm-wiki-add-code` 后面的用户文本作为代码路径和 `llm-wiki add-code` 参数。
4. 代码证据只能通过受管 git checkout 形式落在 `raw-code/<codebase_id>/`，不要混入 `raw/`，也不要复制、软链或登记外部路径来凑协议。
5. 如果发现仓库权限缺失、clone/fetch 无法读取、或目标目录已存在且不干净，必须立即终止，不要写半成品 raw-code。
6. 构建或刷新 `wiki/code/codebases`、`wiki/code/capabilities`、接口映射、graphify 记录和必要的 `wiki/code/traceability`。`build_traceability.py` 必须把新 codebase 的代码锚点候选写入 `Code Anchor Candidates` 和 `staging/traceability-candidates.json`。如果当前 agent 或外部 agent worker 能执行 trace worker contract，则把结果写入 `staging/traceability/runs/<run_id>/proposals.json`，再由 `build_traceability.py` 合并到 `staging/traceability/state.json`；没有模型 worker 输出时，只能记录候选，不能自动宣称 `strong`。
7. 最终报告必须明确说明：当前 codebase 已接成 engine-managed git checkout，后续 `llm-wiki update` 会自动拉取它。
8. 最后输出 `建议下一步`。
