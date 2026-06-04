---
name: llm-wiki-new-doctor
description: LLM Wiki 只读诊断与质量审查入口。用于判断 wiki 项目是否健康、缺什么、哪里过期、有哪些质量问题、下一步做什么，或输出站点级健康画像。（实验包 llm-wiki-new；与全局 llm-wiki 并行，验证通过后再合并）
---

# LLM Wiki Doctor

这是 `$llm-wiki-new doctor` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki-new** skill 包内 `references/core-rules.md`（子入口必读；**不要**加载完整 `SKILL.md`）。
2. 读取 `references/commands/_shared.md` 与 `references/commands/doctor.md`。
3. 将 `$llm-wiki-new-doctor` 后面的用户文本作为 `llm-wiki-new doctor` 参数。
4. 只做只读检查，不修改项目文件。
5. 集合原 audit 能力：检查入口可用性、语义一致性、来源页覆盖、证据强度、traceability、health、graph 和过期页面；问题按 P0/P1/P2 进入 `主要问题`。
6. 必须检查 G+ semantic thickness：source 数与非 index concepts/entities 数、source-to-concept/entity 覆盖率、manual concept/entity placeholder、truth/evidence/proposals/operations/reference 是否 index-only 或低密度、query acceptance / quality audit 是否过时。health pass 不能抵消 G+ 欠拟合；P1/P2 时建议 `llm-wiki-new update` 做 G+ semantic expansion。
7. 必须检查 `staging/refinement-plan.json` 和 `staging/refinement-status.md`。required source page 仍 pending、缺 status record、仍是 deterministic seed page 或缺 raw path evidence 时，作为 P1 `source_refinement_pending` 报告，并明确这是 `llm-wiki-new update` 的自动精修任务，不是用户手工后续。
8. 如果没有 P0/P1，但存在重要 P2（图片证据 unknown、Cjira 状态质量、orphan source、G+ 薄层等），把重要 P2 提权为 P1，并说明 `promoted_from=P2`，保证低优先级债务逐轮被消化。
9. **Drawio vs 图片分离**：状态画像中 drawio 和图片证据必须分开报告。drawio 由 `drawio_repair.py` 确定性流水线自动处理；仅当 `missing_evidence_count > 0` 时提及 drawio。推荐 `llm-wiki image` 时，不得将 drawio 图表计入图片候选列表。
10. 最后输出 `建议下一步`。
