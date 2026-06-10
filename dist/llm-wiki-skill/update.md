# llm-wiki 最近一周更新

统计范围：2026-05-27 至 2026-06-03。

## 版本发布

- 发布 `engine-v1.0.18`，补齐 Cloud 可消费的命令能力 manifest、`pull` / `update` 结果 envelope 契约和 GitLab token 输出脱敏规则。
- 发布 `engine-v1.0.1` 到 `engine-v1.0.6`，同步维护 `VERSION`、`manifest.json`、README 发行记录和 GrapeHub `dist/llm-wiki-skill.zip` 发布包。
- `engine-v1.0.6` 正式产出 `dist/llm-wiki-new-skill.zip` 多入口安装包，zip 内包含 `llm-wiki-new` 主入口和全部 `llm-wiki-new-*` 二级 skill，便于上传公司 skill 平台。
- 新增 `scripts/release_version.py` 与发布脚本约束，发布前统一更新 skill 源目录、dist 目录和 manifest 版本元数据。
- 修正 dist 发布内容，确保 `SKILL.md`、`manifest.json`、`VERSION` 和拆分后的 references 一起进入发布包。

## Shared Update 与发布治理

- 将 `llm-wiki update` 默认升级为 shared mode：更新前检查 KB git upstream、干净工作区、fast-forward 状态、权限和跳过参数，更新后按 allowlist 发布共享 KB 输出。
- 新增 shared update preflight、permission classifier、recognized update commit recovery、managed publish path checks，避免把 `raw/`、`raw-code/`、凭证、日志或非托管文件发布到共享 KB。
- 支持在 source refinement 仍有缺口但硬校验通过时发布 `usable-with-gaps` checkpoint，避免生成物长期滞留在单个本地工作区。
- 加强权限失败提示：Git 拉取、推送和 raw-code 同步权限问题统一以中文说明缺少读取/写入权限，并阻止共享模式继续写出不可信结果。

## raw 与 raw-code 证据管理

- 将 `raw/`、`raw-code/` 明确为本地证据缓存，并补齐模板 `.gitignore` 和 shared publish 排除规则。
- 新增 `upstream/code-sources.json` 管理 raw-code 来源，支持恢复缺失 checkout、校验 source declarations、检查 dirty/unmanaged/damaged/raw-code 状态。
- 新增 raw-code 迁移工具与 backfill 归一化逻辑，可把历史 tracked raw-code gitlink 迁移为受管 code source。
- 修复 update preflight 前 raw 同步顺序，保证 RSS/Cwiki 更新前先恢复 raw cache。

## Cwiki、RSS 与上游同步

- 增强 Confluence/Cwiki 导出：支持完整树 fallback、source path metadata、zip/prototype 证据提取、draw.io 相关证据处理、扁平 raw path 和图片下载限制。
- 支持 Cwiki `exclude-author` 子串过滤，下载时可排除指定作者更新内容，并补充对应测试。
- 新增 Cwiki smoke 限流参数，便于本地小样本验证认证和下载链路，同时在 shared mode 拒绝用截断 raw 作为共享发布输入。
- 改进 wiki source 元数据与 RSS 同步迁移，保留根 wiki、增量 wiki、source role、depth、feed URL、输出路径和 `filters.updated_since` 等关系。

## 鉴权与安装更新

- 补齐 Cwiki Cookie fallback 文档与全局 Cookie fallback 加载逻辑，已有本机 SSO 自动鉴权时不再误报缺少 Cwiki 鉴权。
- 新增 GitLab token fallback：`update-skill` 和 shared update 在 SSH Key / Git credential 不可用时，可使用本机保存的 GitLab PAT；`init_auth_env` 支持可选保存 PAT。
- `llm-wiki update-skill` 支持下载 skill source，并默认联动升级上游 `prd-review-max`，避免需求评审入口和上游评审能力版本脱节。
- 支持 Qoder 与 Trae skill installation，并修正 `llm-wiki-new` 发布与安装脚本。

## 维护多个 KB

- 新增 `llm-wiki maintain-all` 能力，提供本机 `~/.llm-wiki/projects.json` registry、项目自动注册、本地工具注册、发现已注册 KB、dry-run 计划和确认后的批量维护。
- 支持跳过生成的 gateway data，避免 KB discovery 把派生数据误识别为待维护项目。
- dist 中同步 `llm-wiki-maintain-all` 入口和相关脚本、测试、文档。

## 查询、需求评审与 Jira 状态

- 改进 query citation 与 legacy Jira 状态识别：当 Cjira 查询失败但 raw 中存在历史 `project.guazi-corp.com/browse/<KEY>` 链接时，可作为已交付/冻结历史证据处理。
- 升级 query routing playbook，明确业务问题默认使用业务/需求证据，代码问题才展开代码证据，联合问题走 query-plus。
- `requirement-review` 改为委托上游 `prd-review-max`，并增加 KB evidence bridge，让需求评审先检索当前 KB 证据，再进入业务与 UX 评审。
- 精简旧 requirement-review 内置大段参考文档，降低 skill 上下文体积。

## 代码 Wiki、能力候选与追踪矩阵

- 新增 incremental code wiki candidates，支持从源码增量识别能力候选并推动代码 wiki 与 traceability 刷新。
- 加强 traceability worker state contract、proposals/state schema、traceability contract 和代码 anchor 校验流程。
- 当一次更新同时影响需求证据和代码证据时，要求把 source refinement 与代码 traceability refresh 作为一个集成更新闭环处理。

## 质量、健康检查与 G+ 语义

- 修复 health/graph 对 Markdown 代码片段中 `[[...]]` 的误判，以及 `tools/health.py` CLI 统计变量问题。
- 稳定 doctor/health snapshot，增加 BUSINESS_CONTEXT 检查、G+ quality 诊断和失败报告测试。
- 将 refinement gap 提升为 update 自动任务：历史 refinement state 可自动 reconcile，P1 pending source refinement 需要当前 agent 尽量完成，而不是只提示用户下次再跑。
- 要求大批量 source refinement 按 worker capability tier 路由，并尽量并行处理完整队列，而不是默认只抽样少量页面。

## 实验性 llm-wiki-new

- 新增精简协议的 `skills-new/llm-wiki-new` 实验 bundle 与各二级入口，用于降低 skill 上下文成本。
- 新增 `install-llm-wiki-new.sh`、发布脚本、验证脚本和 AB test 文档，用来对比回答质量与上下文占用。
- 将主线认证复用、Cwiki 导出、health、doctor、maintain-all、project registry 等修复同步到 `llm-wiki-new`。
