---
name: requirement-review
description: LLM Wiki 知识库增强的需求评审。先按项目 raw/wiki/raw-code 检索业务与代码证据，再加载并执行上游 prd-review-max 做 PRD/Spec 业务与 UX 诊断；当用户要求需求 review、产品评审、评分概览、影响范围分析、历史冲突检查、Cwiki 评论稿时使用。
---

# Requirement Review（KB + prd-review-max）

## Overview

本 skill 是 **LLM Wiki 知识库证据层** 与 **上游 `prd-review-max`** 的组合入口：

- **知识库证据**：`BUSINESS_CONTEXT.md`、`raw/`、`wiki/`、`raw-code/`、`wiki/code/` —— 用于影响范围、历史规则冲突、已有实现差异与合理性判断。
- **prd-review-max**：来自 `c2b-fe/pre-code` 的独立 skill，负责 PRD/Spec 通用基础检测、业务评审与 UX 评审。**不得修改其包内任何文件。**

若当前目录不是 LLM Wiki 项目，行为退化为：确保安装 `prd-review-max` → 按其 SKILL.md 执行。

语言：用户可见输出默认中文，除非用户明确要求其他语言。

## 第一步：确保 prd-review-max 可用

1. 检查 Agent 环境 skills 目录是否存在 `prd-review-max/SKILL.md`。
2. 若不存在，在 llm-wiki-skill 仓库根目录执行：

   ```bash
   ./scripts/install_prd_review_max.sh --link --client auto
   ```

3. 安装后再次确认；仍失败则报告上游地址并停止：
   `https://git.guazi-corp.com/c2b-fe/pre-code/tree/master/prd-review-max`

## 第二步：读取本 skill 桥接规则

始终读取：

- `references/kb-evidence-bridge.md`

不要读取本包内已废弃的旧评审协议（`review-protocol.md`、`output-template.md`、`prd-quality-gate.md`、`multi-role-review.md`、`historical-data-analysis.md`、`fe-prd-review.md`）。

## 第三步：按桥接流程执行

严格按 `kb-evidence-bridge.md` 四阶段执行：

1. **阶段 A**：需求证据就位（raw 同步、图片、zip 原型）
2. **阶段 B**：知识库证据检索与「知识库上下文摘要」
3. **阶段 C**：加载并执行 **prd-review-max**（读取其 `SKILL.md` 与 `references/**`，遵守其输出顺序）
4. **阶段 D**：追加 LLM Wiki 专属章节（证据范围、MECE 影响范围、历史冲突、实现差异、Cwiki 评论版、建议下一步）

## 与 llm-wiki 的关系

- 独立 skill：不依赖 `$llm-wiki` 命令协议。
- 兼容入口 `$llm-wiki-review-requirement` 会转向本 skill。
- 当项目是 LLM Wiki 项目时，**必须**完成阶段 B/D；不得只做 prd-review-max 文本评审而跳过知识库检索。

## 评审范围与模式

以 **prd-review-max** 的「评审范围 / 评审模式」为准；桥接层只做说法映射（见 `kb-evidence-bridge.md` 阶段 C 表格）。用户已指定时直接执行，未指定时用 prd-review-max 默认：

- 评审范围：业务评审 + 用户体验评审
- 评审模式：产品

## 安全

- 不修改 `raw/` 与 `prd-review-max` 上游文件
- Cwiki 评论稿不含本地路径
- 本地预览前使用 local-port-registry（多仓库共用工作区时）

## Output

最终输出 = **prd-review-max 按 routing 组织的完整结果** + **阶段 D 知识库增量章节**。

Findings 仍优先 P0/P1/P2；知识库交叉验证的 finding 须在证据字段标明 wiki/raw/code 来源。
