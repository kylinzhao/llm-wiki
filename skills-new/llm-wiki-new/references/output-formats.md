# 输出要求

### 构建任务

至少说明：

1. 当前处于哪个阶段
2. 缺什么输入
3. 先执行哪些命令
4. 首轮是否包含全量 summary / AI-native 精修
5. 是否存在 `raw-code/`，会纳入哪些 `codebase_id`
6. 是否使用 `graphify`，输出位置在哪里
7. 哪些需求页面、代码页面和能力页面会在本轮被一口气做完，哪些只能明确留待后续
8. 当前是否是续跑；如果是，说明从哪个 checkpoint 或状态文件继续

### 查询任务

至少说明：

1. 查询类型
2. 检索路径
3. 结论
4. 支撑页面
5. 未决点
6. 如果涉及代码，区分“需求文档证明”“代码实现证明”“推断”“缺失证据”

### 审查任务

必须 findings first。

### Doctor 任务

只读诊断，至少说明：

1. 当前阶段和整体 verdict
2. 输入层：`raw/`、`BUSINESS_CONTEXT.md`、`raw-code/`
3. 文档层：sources、layered pages、concepts、entities、G+ 产物
4. 代码层：codebases、capabilities、traceability、graphify
5. 校验层：health、broken links、graph、可选 anchor check
6. 风险与缺口
7. 优先级建议和下一步命令
8. 图片证据层：`raw/` 图片资产数量、`staging/image-notes/` 状态、是否应进入阶段 H、优先候选页面
9. G+ semantic thickness：source 数与非 index concepts/entities 数、source-to-concept/entity 覆盖率、manual concept/entity placeholder、truth/evidence/proposals/operations/reference 是否 index-only 或低密度；这些问题按 P1/P2 报告，不因 health pass 而忽略
10. P2 消化规则：如果 doctor / update 当前没有 P0/P1，重要 P2（图片证据 unknown、Cjira 状态质量、orphan source、G+ 薄层等）应提权为 P1，避免长期沉底

### G+ 任务

至少说明：

1. source 精修是否已完成
2. concepts/entities/truth/conflicts/evidence/proposals/reference/operations 的二次校准状态
3. `docs/query-acceptance.md` 状态
4. `docs/gplus-quality-audit.md` 状态
5. health / broken wikilinks / graph 状态
6. 图片证据层是否仍待阶段 H；若待处理，给出 `llm-wiki-new image` 作为建议下一步
7. 如果 `tools/update_wiki.py` 或 `tools/doctor.py` 报 `gplus_quality.status=needs_attention`，必须说明是 P1/P2 语义层欠拟合还是可接受的窄域薄层；P1/P2 时优先在本轮 update 完成 G+ semantic expansion。若没有其他 P0/P1，重要 P2 欠拟合提权为 P1 处理

### 代码 wiki 任务

至少说明：

1. codebases discovered
2. graphify status
3. pages created or updated
4. capability coverage
5. frontend-backend mappings
6. requirement evidence linked
7. code evidence linked
8. inference-only links
9. missing evidence
10. validation results

### 追踪矩阵任务

至少说明：

1. 覆盖的业务能力和需求点
2. 需求来源
3. 前端页面 / 组件 / URI
4. Controller / Dubbo / Service / Method
5. 配置 / 表字段 / 消息 / 任务
6. 证据强度：`strong`、`partial`、`inferred`、`external`、`missing`
7. 关键代码锚点
8. 外部系统边界和缺口
