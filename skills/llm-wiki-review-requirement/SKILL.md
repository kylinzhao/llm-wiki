---
name: llm-wiki-review-requirement
description: LLM Wiki 需求评审兼容入口。用于用户仍以 llm-wiki 方式调用需求 review 时，转向独立的 requirement-review skill，对 PRD、Spec、Cwiki 页面、Markdown 需求、图片、zip/HTML 原型和前端交互说明做 evidence-first review、产品评审、评分概览、16 维度评审和多角色评审。
---

# LLM Wiki Review Requirement

这是兼容入口。真正的需求评审能力已独立到 `$requirement-review`。

语言要求：本兼容入口的用户回答必须默认使用中文；如果把评审结果写入 LLM Wiki 文档，也必须使用中文，除非用户明确要求其他语言。

1. 读取 **requirement-review** skill 包根目录下的 `SKILL.md`（路径由环境解析，勿写死本机绝对路径）。
2. 读取同包内 `references/review-protocol.md` 和 `references/output-template.md`。
3. 按评审模式读取同包内参考文档：
   - 完整评审 / 快速评审涉及角色视角时：`references/multi-role-review.md`。
   - 需求涉及字段/表结构、业务规则、枚举/配置、报表口径、数据展示或查询条件时：`references/historical-data-analysis.md`。
4. 若涉及前端，读取同包内 `references/fe-prd-review.md`（文内「关联规范」要求先读仓库根目录 `references/fe-req-signal-noise.md`，须一并遵循；有 UI 变更时同时遵循 `references/fe-req-design-deliverables.md`）。
5. 将 `$llm-wiki-review-requirement` 后面的用户文本作为 `$requirement-review` 的目标需求参数。
6. 如果当前项目是 LLM Wiki 项目，可以把 `BUSINESS_CONTEXT.md`、`raw/`、`wiki/`、`raw-code/`、`wiki/code/` 作为证据层；不要再依赖 `$llm-wiki` 主 skill 的命令协议。
7. 支持 `$prd-review` 合入后的四种模式：
   - `完整评审`：16 维度 + 6 角色 + 已有实现差异 + 触发式历史数据探查。
   - `产品评审`：产品经理视角，覆盖维度 1、2、3、5、6、7、13、14、15、16。
   - `快速评审`：按用户指定维度、关注领域或角色裁剪。
   - `评分概览`：输出维度评分卡和统计，不展开细节。
   用户已指定模式时直接执行；未指定时由 `$requirement-review` 按请求目标推断，不要因为模式选择中断评审。
8. 输出 findings-first 完整报告、评审模式与维度评分卡、多角色/产品视角评审、已有实现差异、历史数据分析、前端需求完整性审查、图片与 zip 原型证据、验收清单、待决问题、Cwiki 评论版和 `建议下一步`。
