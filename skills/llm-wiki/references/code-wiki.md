# 代码 Wiki 与联合知识层

## 1. 定位

代码 wiki 是 `llm-wiki` 的可选一等证据层。

当项目根目录存在 `raw-code/` 时，`llm-wiki` 应将源码仓库纳入构建、审查和查询协议。代码 wiki 的目标不是替代需求 wiki，而是回答：

- 需求文档说了什么
- 前端/后端代码实际实现了什么
- 代码实现与需求文档如何互相印证
- 哪些结论只是推断
- 哪些证据仍缺失

## 2. 输入约定

```text
raw/
BUSINESS_CONTEXT.md
raw-code/
  <codebase_id>/
```

`raw/` 是业务/需求原始证据层，默认不可变。
`raw-code/*` 的每个一级目录是独立源码库，称为 `codebase_id`。唯一受支持的形态是 `llm-wiki add-code` 创建的 engine-managed git checkout。

不要把源码复制进 `raw/`。
不要把代码图谱输出当作需求文档。
不要把 copy、symlink、外部路径登记或 snapshot 目录当作长期 raw-code 方案；这些形态必须迁移后才能参与标准 update。

## 3. 输出约定

```text
wiki/code/
  index.md
  codebases/
    <codebase_id>/
      index.md
  capabilities/
    <capability>.md
  traceability/
    index.md
    <capability>.md
staging/code-graph/
  <codebase_id>/
    graphify-out/
    manifest.json
    endpoint-map.json
```

`codebases/<codebase_id>/` 记录单仓库事实。
`capabilities/` 记录跨需求、前端、后端、异步任务和技术设计的业务能力实现链路。
`traceability/` 记录需求点到实现证据的审计矩阵。

## 4. codebase 识别

开始代码 wiki 前，先识别每个 codebase：

- 技术栈
- 入口文件
- 构建配置
- 目录结构
- 本地 README / AGENTS / OpenSpec / docs
- 对外接口形态
- 主要业务模块

常见前端信号：

- `package.json`
- `src/pages`
- `src/services`
- route 配置
- API URI 字符串

常见后端信号：

- `pom.xml` / `build.gradle`
- controller
- API contract
- service / service impl
- manager / client
- dao / mapper / repository
- kafka consumer / producer
- job / scheduler
- OpenSpec / 技术设计

## 5. graphify 使用

可以使用 graphify 作为代码结构增强层。

推荐用法：

1. 每个 codebase 单独运行 graphify 或单独归档输出
2. 优先使用模板脚本：`uv run python tools/graphify_code.py --all`
3. 输出放在 `staging/code-graph/<codebase_id>/graphify-out/`
4. 读取 graphify 的 `graph.json`、报告、调用关系和聚类结果
5. 将结果转成 `wiki/code/` Markdown 页面
6. 在能力页中引用 graphify 支持的代码结构，但不要把推断边当作直接事实

操作顺序：

1. 先检查是否已有 `staging/code-graph/<codebase_id>/graphify-out/`。
2. 再检查项目或全局环境是否存在 `graphify` / `graphifyy` 命令。
3. 从 `raw-code/<codebase_id>/` 或拆分后的模块目录运行，不从 wiki 根目录直接扫所有代码。
4. 将 stdout、report、`graph.json`、HTML 或 assets 统一归档到 `graphify-out/`。
5. 记录 `graphify-status.json`：命令、工作目录、退出码、覆盖范围、输出路径、失败原因。
6. 如果 graphify 失败，保留失败记录，继续做确定性代码扫描和 Markdown 页面，不伪造 graphify 输出。

依赖说明必须写清楚：

- 必需：Python 3.10+、`uv`
- 可选：`graphify`，提供 `graphify update <path>` 命令
- graphify 缺失时，`graphify_code.py` 记录 skipped；仍继续使用 `scan_code.py` 生成确定性代码事实

大型 codebase 拆分策略：

- 按语言拆：前端、后端、脚本、配置分开。
- 按模块拆：API、service、manager、dao、job、OpenSpec 分开。
- 按目录拆：选择业务相关目录，跳过构建产物、依赖目录、测试快照和生成代码。
- 超时或内存失败时缩小 scope，记录 partial coverage。
- 多个 graphify 输出可以在 codebase index 汇总，不要求合成一个巨型 graph。

graphify 适合回答：

- 哪些文件/类/函数是结构热点
- 模块之间如何调用
- 哪些概念在代码中聚成一个社区
- 哪些代码与文档可能相关

graphify 不负责：

- 规范业务实体
- 判断历史需求版本的优先级
- 替代 `BUSINESS_CONTEXT.md`
- 替代 `wiki/sources/`
- 替代最终的 Markdown wiki

## 6. 并发构建策略

代码 wiki 构建默认应并发推进。

推荐拆分：

- 每个 `raw-code/*` codebase 一个或多个 subagent
- 前端 codebase 可分为 routes/pages/services/components
- 后端 codebase 可分为 controllers/api-contracts/domain-services/managers/data-access/async/jobs/openspec
- graphify 可按 codebase 独立运行
- 能力页可按 capability 拆分，但最终跨层命名和链接由主 agent 统一

简单任务可以打包：

- 一个 subagent 可以同时处理多个小页面、多个小组件、多个 endpoint 映射或多个 OpenSpec 摘要
- 打包条件是同类、低风险、输出边界清晰
- 不要让多个 subagent 同时写同一文件

主 agent 保留职责：

- 业务实体规范
- `wiki/code/capabilities/` 命名和去重
- 前后端 URI 映射确认
- 需求证据与代码证据的最终合并
- 推断/事实/缺失证据的口径校准

跨仓库写入边界：

- 一个 subagent 可以拥有一个 codebase scan。
- 一个 subagent 可以拥有一个 codebase 子层，例如 controllers、routes 或 OpenSpec。
- 一个 subagent 可以草拟一组 capability 页面，但最终命名、去重和 cross-link 由主 agent 合并。
- 主 agent 拥有 `wiki/code/index.md`、顶层 capability 命名、endpoint-map 汇总和最终验证。

## 7. 前端抽取

前端 codebase 优先生成：

```text
routes.md
pages/<page>.md
services/<service>.md
components/<component>.md
```

页面页至少包含：

- 路由名
- 源码路径
- 入口参数
- 调用的 service / API URI
- 关键状态和交互
- 关联组件
- 关联业务能力
- 关联需求/概念/实体
- 前端无法证明的规则

service 页至少包含：

- 源码路径
- 导出的函数
- HTTP method
- URI
- 请求/响应线索
- 调用页面
- 对应后端 endpoint

## 8. 后端抽取

后端 codebase 优先生成：

```text
endpoints.md
api-contracts/
controllers/
dubbo-services/
domain-services/
managers/
data-access/
async/
jobs/
ops-tools/
openspec/
```

controller 页至少包含：

- base path
- endpoint
- method
- request / response
- 调用的 service
- 关联前端 URI
- 关联业务能力

domain service 页至少包含：

- 类/接口路径
- 关键方法
- 上游调用方
- 下游 manager / dao / kafka / job
- 主要业务规则
- 关联需求/概念/实体
- 推断与缺失证据

OpenSpec / 技术设计页属于代码侧技术设计证据，不应混入 `raw/`。

## 9. 能力页模板

`wiki/code/capabilities/<capability>.md` 推荐结构：

```text
# <能力名>

## 业务语义

## 需求文档证据

## 前端实现证据

## 后端实现证据

## 异步任务 / 消息 / 定时任务

## 数据访问 / 状态持久化

## 技术设计证据

## 跨端链路

## 已证实事实

## 推断

## 缺失证据与未决点
```

能力页应链接：

- `wiki/concepts/*`
- `wiki/entities/*`
- `wiki/sources/*`
- `wiki/code/codebases/*`

命名与去重：

- 优先复用 `wiki/concepts/*` 的规范概念名。
- slug 使用小写 kebab-case；中文标题放在 H1。
- 同义能力合并到一个页面，并在 `Aliases` 或“别名”小节记录历史叫法。
- 当一个 capability 只是概念的一种实现链路时，保留单独 capability 页并链接回概念页。
- 不用英文近义词重复建页，例如 `negotiation` / `bargaining` / `price-negotiation` 应先判定是否同一业务能力。
- 如果业务范围不同，必须在标题和“边界”小节写清楚差异。

## 10. 跨端映射

前端 service URI 与后端 controller endpoint 是最强映射证据。

优先级：

1. 完整 URI 精确匹配
2. base path + method path 匹配
3. request / response 类型匹配
4. 能力页与命名相似
5. graphify 社区或相似关系

只有前两类可以写成“代码实现证明”。
后几类必须写成“推断”。

## 11. 追踪矩阵

当用户需要测试追踪、实现审计、需求落地核对或“某个需求到底在哪些代码里实现”时，优先维护：

```text
wiki/code/traceability/
  index.md
  <capability>.md
```

追踪矩阵不替代 source 页、capability 页或 codebase 页。它把三者连成一张可审计表。

矩阵字段：

```text
需求点 | 需求来源 | 前端页面/组件 | 前端 URI | Controller/Dubbo | Service/Method | 配置 | 表/字段 | 消息/任务 | 证据强度 | 缺口
```

证据强度：

- `strong`：需求证据和实现证据能通过精确 URI、Controller/Dubbo、Service、表或消息名称连上。
- `partial`：需求能连到代码模块或服务族，但方法、字段、消息体或运行时条件尚未完全证明。
- `inferred`：只能从命名、相邻证据或 graphify 关系推断，作为事实引用前还需要直接证据。
- `external`：关键闭环在当前 `raw-code/` 未包含的外部系统。
- `missing`：已有需求证据，但当前 wiki/code 还没有找到实现证据。

每个追踪矩阵页推荐包含：

- `## 覆盖范围`
- `## 追踪矩阵`
- `## 关键代码锚点`
- `## 外部系统边界`
- `## 缺失证据与下一步`

关键代码锚点应尽量覆盖：

- 前端页面和 service URI。
- HTTP Controller 和 Dubbo 入口。
- 核心 Service / Method。
- 配置常量、Etcd 读取、枚举。
- DO、Mapper、关键字段。
- Kafka consumer、topic、XXL job。

锚点必须已验证文件存在；如果标行号，行号不能越界。无法闭环证明时保留 `partial`、`external` 或 `missing`，不要为了好看升级成 `strong`。

## 12. 证据优先级与冲突

OpenSpec / 技术设计属于代码侧设计证据，不属于 `raw/` 需求证据。

证据类型边界：

- `raw/` PRD / 需求文档：证明业务诉求、规则意图和历史决策。
- OpenSpec / 技术设计：证明设计意图，不证明当前实现已生效。
- 前端页面 / service：证明可见流程、参数传递和 API 调用，不证明后端业务规则。
- 后端 controller：证明 endpoint 入口，不一定证明完整领域规则。
- domain service / manager / dao：证明实现逻辑、下游调用和持久化线索。
- jobs / consumers：证明异步入口，不证明上游事件语义完整。
- API contract / SDK：证明契约形状，不证明服务实现。
- graphify：证明结构关系线索，不证明业务语义。

冲突处理：

- PRD 与 OpenSpec 不一致：标注为“需求意图 vs 技术设计漂移”。
- OpenSpec 与代码不一致：标注为“设计 vs 当前实现漂移”。
- 代码与 PRD 不一致：标注为“当前实现与需求证据冲突”，不要直接判断谁正确。
- archived / stale / superseded 的 OpenSpec 必须在页面中标注状态。
- 当前代码可以证明“现在怎么实现”，不能单独证明“业务应该如此”。

## 13. checkpoint 与 freshness

长任务状态至少记录：

- `codebase_id`
- `scan_scope`
- `graphify_status`
- `graphify_output_path`
- `generated_page_paths`
- `endpoint_map_path`
- `capability_coverage_status`
- `last_integrated_subagent_result`
- `blocked_reason`
- `resume_from`
- `next_action`

代码 wiki stale 触发：

- source 文件修改时间晚于 wiki 页面。
- graphify 输出早于源代码树。
- endpoint map 早于前端 service 或后端 controller。
- OpenSpec 被归档或 superseded。
- capability 页引用的代码路径删除或重命名。
- traceability 页引用的 source 或 code anchor 失效、行号越界或证据强度变化。

发现 stale 时，不要立即全量重做；先标注 stale 范围，再刷新受影响 codebase、endpoint map 和 capability 页。

## 14. 安全与敏感配置

- 不复制 `.env`、cookie、token、password、secret、private key、access key。
- 部署、网关、数据库、消息队列等配置只描述用途和配置项类别。
- 必要值用 `<redacted>` 表示，并说明已脱敏。
- generated graph 和 Markdown 不应包含敏感值。
- 内网 host、账号、凭据组合、签名密钥等默认敏感。

## 15. 最低可用首轮

代码 wiki 的 minimum useful first pass 至少包含：

- 每个 `raw-code/*` 都有 `wiki/code/codebases/<codebase_id>/index.md`。
- 每个 codebase 有技术栈、入口、模块边界、主要本地文档。
- 前端 routes / pages / services / API URI 已抽取，或说明不存在前端。
- 后端 endpoints / controllers / API contracts 已抽取，或说明不存在后端。
- 至少一个 frontend-backend endpoint map，或明确无法映射的原因。
- 初始 capability 页覆盖最核心业务能力。
- 对最高价值能力建立初始 traceability 页，或明确留待下一轮。
- graphify 输出已记录，或明确 skipped / failed 原因。
- final gap report 列出缺失证据和下一轮范围。

推荐报告形状：

- stage completed
- codebases discovered
- graphify status
- pages created or updated
- capability coverage
- frontend-backend mappings
- requirement evidence linked
- code evidence linked
- inference-only links
- missing evidence
- validation results
- recommended next pass

## 16. 质量检查

代码 wiki 审查至少检查：

- 每个 `raw-code/*` 是否有 codebase index
- 前端 service URI 是否能映射到后端 controller
- controller 是否能追到 service / manager / dao
- 能力页是否链接需求文档、概念、实体和代码事实
- 是否把推断误写成事实
- 是否存在断链或空页
- 是否标注缺失证据
- OpenSpec 是否作为技术设计证据单独标注
- 是否存在敏感配置泄露
- graphify 输出路径和覆盖范围是否记录
- generated pages 是否没有 broken wikilinks
- traceability 证据强度是否合理
- traceability 代码锚点是否存在且未越界

如果只有前端没有后端，必须标注后端缺失。
如果前端和后端都存在，必须优先做跨端 URI 映射。

## 17. 当前项目类型示例

常见模式：

- React Native + Web 前端：优先抽取 routes、pages、services、API URI、交互状态。
- Java Spring Boot 后端：优先抽取 controller、Dubbo API、service impl、manager、dao、Kafka、jobs。
- OpenSpec 目录：作为代码侧设计证据，标注 active / archived / stale / superseded。
- `/dcncenter/...` URI：优先尝试映射到后端 controller；精确 URI 或 base path + method path 才能作为强代码证据。
