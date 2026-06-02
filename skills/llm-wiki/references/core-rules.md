# LLM Wiki Core Rules（子入口必读）

各 `$llm-wiki-*` 短入口 skill 加载本文件 + 对应 `references/commands/<command>.md`，**不要**再加载完整 `SKILL.md`（约 30KB）。仅当用户直接调用 `$llm-wiki` 且无明确子命令、或任务跨多条命令时，才读取包根目录 `SKILL.md`。

## 语言要求

- 面向用户的过程说明、诊断、查询回答、审查报告和最终输出默认使用中文。
- agent 生成或改写的 `wiki/`、`docs/`、`staging/` Markdown 默认中文。
- 代码标识符、命令、路径、API、配置键与原始证据引用可保留原文。

## Skill 包路径

`README.md`、`references/...`、`scripts/...` 相对于 **llm-wiki skill 包根目录**。禁止写死个人本机绝对路径。安装与 `install_project_template.py` 用法见主 `SKILL.md`「Skill 包路径」（仅在该节需要时读取）。

## 续跑优先级

非空项目默认续跑而非重建。开始前优先读：

1. `BUSINESS_CONTEXT.md`
2. `staging/refinement-status.md`
3. `staging/health/latest.json`
4. `graph/summary.md` 或 `staging/graph/latest.json`
5. `wiki/overview.md`

续跑：保留已有 `wiki/`、精修与 `wiki/code/`；仅 `raw/`、`BUSINESS_CONTEXT.md`、taxonomy 或大批量 wikilink 变化时才考虑宽范围重建。

## 阶段模型（摘要）

A 输入检查 → B 骨架 → C 确定性构建 → D health → E source 精修 → F 代码 wiki（有 `raw-code/` 时）→ G graph → G+ 综合层 → H 图片（可选）→ I 发布 → M 增量维护。共享发布硬门禁：证据同步、health、graph、anchor、发布范围安全。`refinement_contract.status=needs_refinement` 为 P1 自动精修，非 raw/graph 硬阻断。详情见 `references/stage-model.md`。

## 安全与证据边界

- 可读 `raw/`，**不得修改** `raw/`。
- 默认不提交 `raw/`。
- 语义判断由当前 agent/worker 完成；本地脚本仅做确定性扫描与校验。
- 不把 token、cookie、密码、私钥或完整敏感配置写入 wiki。

## 自动继续与停机

可自动继续：source 精修、G+、health/graph 收口、低风险 wikilink/index 修复。须停等用户：改 canonical 实体/业务口径、无法由证据支撑的业务判断、大批量低价值图片、是否提交 `raw/`、覆盖远端仓库。

## 每条命令收尾

必须以 **`建议下一步`** 结束：1–3 条项目相关动作，必要时给出下一条 `llm-wiki-*` 命令；说明可暂停条件或何种变更应触发 `update`。

## 按需扩展阅读

| 场景 | 文件 |
| --- | --- |
| 构建/维护流水线 | `references/build-and-maintenance.md` |
| 代码 wiki / graphify | `references/code-wiki.md` |
| 查询路由 | `references/query-logic.md` |
| Subagent 分片 | `references/subagent-handoff.md` |
| 图片证据 | `references/image-evidence.md` |
| 输出格式模板 | `references/output-formats.md` |
