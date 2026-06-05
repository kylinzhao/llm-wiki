---
name: llm-wiki-code-trace
description: LLM Wiki 代码追踪入口。用于只做 raw-code 扫描重建、code candidate/traceability units 诊断，以及必须收口的 AI-native code trace 精修。
---

# LLM Wiki Code Trace

这是 `$llm-wiki code-trace` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包内 `references/core-rules.md`（子入口必读；**不要**加载完整 `SKILL.md`）。
2. 读取 `references/commands/_shared.md` 与 `references/commands/code-trace.md`。
3. 将 `$llm-wiki-code-trace` 后面的用户文本作为 `llm-wiki code-trace` 参数。
4. `doctor` 只读诊断；`rebuild` 只做 deterministic raw-code/code candidate/traceability units 重建；`refine` 做 AI-native 代码追踪精修。
5. `refine` 可按 source、unit、capability 或 codebase 分布执行；但只有声明范围内 AI 精修、证据判断、capability 页面和 validation 收口后，才允许报告完成。checkpoint 只能报告为 usable-with-gaps，不能当作完成。
6. 结束前必须输出 `建议下一步`。
