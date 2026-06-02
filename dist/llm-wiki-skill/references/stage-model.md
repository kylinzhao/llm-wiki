# 阶段模型与任务模式

### 1. 阶段模型

默认阶段：

1. 阶段 A：输入与状态检查
2. 阶段 B：项目骨架初始化
3. 阶段 C：确定性构建
4. 阶段 D：health 初检
5. 阶段 E：AI-native source 全量精修
6. 阶段 F：代码 wiki / 联合知识层（当 `raw-code/` 存在且任务需要）
7. 阶段 G：graph 构建与首轮验收
8. 阶段 G+：综合层二次校准、查询验收、质量审查
9. 阶段 H：选择性高价值图片证据补充
10. 阶段 I：发布 / 提交 / 远端同步
11. 阶段 M：后续增量维护

阶段 I 的共享发布硬门禁是证据同步、health、graph、必要 anchor check 和发布范围安全。`check_refinement.py` 的 pending 或 `refinement_contract.status=needs_refinement` 不是 raw/graph/health 硬阻断，但它是 P1 自动精修任务：`update` 必须在同轮进入 agent-native source 精修队列，不能只发布后提醒用户下次处理。pending source 队列超过 10 页时，应默认使用当前环境可用的 subagent / worker 并行分片尽可能处理完整队列，分片只改互不重叠的 `wiki/sources/*`，主 agent 统一写 `staging/refinement-status.md` 并收口验证；不得把 5 页或少量样本当作默认完成策略。只有真实 blocker、工具限制、上下文耗尽或用户要求停止时才允许 checkpoint。图片证据待筛选或已 checkpoint 的语义层待加厚可作为 `usable-with-gaps` 发布。raw-code 权限失败、非受管、损坏、dirty 或不能 fast-forward 是硬阻断，应在写入 raw/wiki/staging 产物前停止，并让用户先修权限/凭证或显式切换本机模式。

### 2. 新项目优先构建，不优先查询

如果项目还没有 `wiki/` 骨架，应先做：

1. 检查 `raw/` 和 `BUSINESS_CONTEXT.md`
2. 初始化目录结构
3. 运行确定性构建
4. 对全量语料完成首轮大模型 summary 与 AI-native 精修
5. 如果存在 `raw-code/`，构建代码 wiki 与需求-代码跨层链接
6. 默认进入阶段 G+：二次校准 concepts/entities/truth/conflicts/evidence/proposals/reference/operations，生成或刷新 query acceptance 与 G+ quality audit
7. 运行健康检查
8. 最后构建 graph

这里的“首轮大模型 summary 与 AI-native 精修”是 0-1 初始化的必要环节，不应只停留在骨架、索引和占位页。
可以按 `sources -> layered pages -> concepts/entities -> G+ 综合层` 分层推进，但默认应在同一轮里一口气完成，而不是把全量精修或 G+ 加厚留到后续再补。只有 hard blocker 或用户显式要求“只建骨架/跳过 G+”时，0-1 才能停在 G+ 之前，并且最终报告必须把 G+ 标为 pending。

## 任务模式

### A. 0-1 初始化

适用于：

- 新项目只有 `raw/`
- 新项目已有 `raw/` 和 `BUSINESS_CONTEXT.md`
- 需要搭一整套 `wiki/graph/staging/tools/docs`
- 需要在首轮里完成全量语料的 summary、分层落位和 AI-native 精修

### B. 增量构建

适用于：

- 新增了一批 `raw/`
- 更新了 `BUSINESS_CONTEXT.md`
- 调整了 taxonomy / entity 规则

### C. 查询问答

适用于：

- 业务问题
- 专题串讲
- 概念/实体解释
- 分层目录解释

### D. 质量审查

适用于：

- 检查 wiki 是否真的可用
- 检查实体/概念冲突
- 检查 layered pages 是否错分
- G+ 阶段必须输出查询验收和质量审查

### E. 代码 wiki / 联合知识层

适用于：

- 项目存在 `raw-code/`
- 需要从前端、后端或多源码仓库生成代码 wiki
- 需要把需求文档、业务概念、接口、页面、服务、异步任务和技术设计打通
- 需要回答“需求说了什么、代码实际怎么实现、还有哪些证据缺口”
