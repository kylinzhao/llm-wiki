# LLM Wiki 架构与检索说明

本文解释四条核心链路：

1. 需求文档 `raw/` 如何翻译为 wiki 文档
2. 代码 `raw-code/` 如何翻译为代码图谱和 wiki 相关文档
3. 需求查询时系统如何运转
4. 需求查询需要关联代码时系统如何运转

这里的“翻译”不是把原始材料交给脚本做语义理解。LLM Wiki 的基本原则是：

- 本地脚本只做确定性工作：扫描、建索引、抽取候选、生成骨架、检查断链、构建图谱。
- Agent / reviewer 可辅助语义工作：摘要、归类、实体归一、业务能力判断。需求到代码的证据强度必须由确定性候选、可规则匹配信号或直接审计证据支撑，不能依赖模型作为运行时补全步骤。
- `raw/` 和 `raw-code/` 是原始证据层，不应被修改。
- `wiki/` 是面向查询、审查和交接的可读知识层。
- `staging/` 是机器可读中间层，保存 manifest、health、graph、code scan、graphify 输出和 drift 状态。
- `graph/` 是 wiki 文档之间的链接图谱；`staging/code-graph/*/graphify-out/` 是源码结构图谱。

## 1. 需求文档如何翻译为 wiki 文档

需求侧输入主要来自：

- `raw/`：原始需求文档、PRD、会议纪要、运营文档、Cwiki 导出、Markdown、HTML、JSON、CSV 等文本材料。
- `BUSINESS_CONTEXT.md`：业务语义基线，定义核心对象、角色、边界、规范实体和历史别名。

`BUSINESS_CONTEXT.md` 优先级高于单个历史需求文档中的旧称呼。如果两者冲突，应在 wiki 中记录冲突，而不是静默合并。

### 确定性构建

`tools/build_wiki.py` 执行第一步翻译：

- 扫描 `raw/` 中可读文本文件。
- 为每个 source 生成稳定 slug。
- 计算 SHA-256、大小、修改时间。
- 写入 `staging/source-manifest.json`。
- 为每个 source 生成 `wiki/sources/<slug>.md` 种子页。
- 生成基础 layered pages：
  - `wiki/overview.md`
  - `wiki/concepts/index.md`
  - `wiki/entities/index.md`
  - `wiki/truth/index.md`
  - `wiki/conflicts/index.md`
  - `wiki/evidence/index.md`
  - `wiki/proposals/index.md`
  - `wiki/reference/index.md`
  - `wiki/operations/index.md`

这一步只建立“可稳定追踪的来源页”和“可落位的知识结构”。它不会自动完成业务摘要，也不会判断哪些概念重要。

### AI-native 精修

Codex / subagent 接着完成语义翻译：

- 读取 `BUSINESS_CONTEXT.md`，确定当前项目的语义基线。
- 逐页读取 `raw/` 原文和 `wiki/sources/<slug>.md` 种子页。
- 将 source page 从占位内容改为证据型摘要：
  - 文档讲了什么
  - 核心需求点是什么
  - 涉及哪些角色、对象、流程、状态、规则
  - 明确事实、推断、未决点分别是什么
- 将跨 source 的共性内容沉淀到 layered pages：
  - `concepts` 记录稳定业务概念
  - `entities` 记录规范实体、别名和冲突
  - `truth` 记录多个 source 支撑的稳定事实
  - `conflicts` 记录冲突和待确认口径
  - `evidence` 记录关键证据索引
  - `proposals` 记录方案或建议
  - `reference` 记录稳定参考资料
  - `operations` 记录 SOP、运营动作、人工流程

### 增量与漂移

再次运行 `build_wiki.py` 时，脚本不会覆盖已经精修过的 source page。它会：

- 对比 `raw/` 当前 SHA-256 和 source page 记录的旧 SHA-256。
- 将变更记录到 `staging/source-drift.json` 的 `stale_sources`。
- 记录已经没有对应 raw 文件的 `orphan_source_pages`。
- 由 `health.py` 将 stale source 视为需要处理的维护缺口。

需求文档到 wiki 的翻译链路是：

```text
raw 原文
  -> source manifest
  -> source seed pages
  -> Codex 语义摘要和分层落位
  -> health / graph / drift 持续维护
```

## 2. 代码如何翻译为图谱和 wiki 相关文档

代码侧输入来自：

- `raw-code/<codebase_id>/`

每个 `raw-code/*` 一级目录都是独立 codebase。代码证据不能混入 `raw/` 需求证据层。需求证明来自 `raw/` 和 `wiki/sources/`，代码实现证明来自 `raw-code/`、`wiki/code/` 和 `staging/code-graph/`。

### 确定性代码扫描

`tools/scan_code.py` 将 `raw-code/*` 翻译为机器可读代码事实和 codebase wiki 入口。

它会识别：

- 技术栈 marker：`package.json`、`pom.xml`、`build.gradle`、`go.mod`、`pyproject.toml`
- 文件角色：controller、route、service、component、data-access、job、async、api-contract
- endpoint 候选：Java mapping 注解，以及字符串中的 `/api/...`、`/openapi/...`、`/ajax/...` 等 URI
- route 候选
- class / interface / enum / function / def / func 等符号

输出包括：

- `staging/code-graph/<codebase_id>/manifest.json`
- `staging/code-graph/<codebase_id>/endpoint-map.json`
- `wiki/code/codebases/<codebase_id>/index.md`
- `staging/code-graph/summary.json`

这些是“代码事实候选”，不是业务能力解释。比如扫描到 `/api/search/cars` 只能证明代码里有这个 URI 字符串，不能单独证明它实现了“C2 搜索车辆”这个业务能力。

### graphify 代码图谱

`tools/graphify_code.py` 可选调用 `graphify`，将代码结构进一步翻译成源码图谱。

依赖：

- 必需：Python 3.10+、`uv`
- 可选：`graphify`，需要提供 `graphify update <path>`

运行方式：

```bash
uv run python tools/graphify_code.py --all
```

输出：

- `staging/code-graph/<codebase_id>/graphify-out/graph.json`
- `staging/code-graph/<codebase_id>/graphify-out/graph.html`
- `staging/code-graph/<codebase_id>/graphify-out/GRAPH_REPORT.md`
- `staging/code-graph/<codebase_id>/graphify-status.json`

`graphify_code.py` 会把 `raw-code/<codebase_id>` 复制到临时目录再运行 graphify，避免 graphify 在 `raw-code/` 里写入 `graphify-out/`，保持代码证据层不可变。

graphify 主要回答结构问题：

- 哪些文件、类、函数是结构热点
- 模块之间可能如何调用
- 哪些节点相邻
- 哪些文件属于同一结构社区
- 从入口到实现可能经过哪些路径

graphify 不回答业务语义问题：

- 不能证明某个接口满足某条需求
- 不能证明某个字段就是业务上的规范实体
- 不能证明某个流程符合 PRD
- 不能替代 source page 和 traceability 的证据判断

### 代码 wiki 和能力页

代码 wiki 的目标目录是：

- `wiki/code/index.md`
- `wiki/code/codebases/<codebase_id>/index.md`
- `wiki/code/capabilities/`
- `wiki/code/traceability/`

其中：

- `codebases/<codebase_id>/` 记录单个代码库内部事实。
- `capabilities/` 记录业务能力如何跨前端、后端、接口、Service、DAO、消息、任务串起来。
- `traceability/` 记录需求点到代码证据的可审计矩阵。

`tools/build_traceability.py` 生成并增量维护追踪矩阵入口：

- 左侧列出需求 source。
- 右侧列出 codebase scan 候选。
- 从 `staging/code-graph/<codebase_id>/manifest.json` 提取代码锚点候选，写入 `wiki/code/traceability/index.md` 的 `Code Anchor Candidates`，完整候选同时写入 `staging/traceability-candidates.json`。
- 保留 `Verified Traceability` 中已验证的追踪行，避免每次 update 覆盖已确认结论。
- evidence strength 默认为 `missing`、`partial` 等待判断。

候选锚点只有在存在可审计需求证据时才能提升为真实追踪关系：

- 需求来源
- 需求点
- 前端页面 / 组件 / URI
- Controller / Dubbo / Service / Method
- 配置 / 表字段 / 消息 / 任务
- 证据强度
- 关键代码锚点
- 外部系统边界和缺口

代码到 wiki 的翻译链路是：

```text
raw-code 源码
  -> scan_code 确定性事实
  -> codebase wiki 入口
  -> graphify 结构图谱
  -> Codex 业务能力解释
  -> capability pages
  -> traceability matrix
```

## 3. 需求查询时系统如何运转

普通需求查询指用户只问业务、产品、流程、规则、概念或实体，不要求证明代码实现。

标准路径是：

1. 识别问题类型：概念解释、实体定义、业务流程、规则口径、冲突确认、证据追溯、方案综述。
2. 读取 `BUSINESS_CONTEXT.md`。
3. 读取入口页：`wiki/index.md`、`wiki/overview.md`。
4. 按问题类型进入 layered pages：
   - 概念问题查 `wiki/concepts/`
   - 角色/对象问题查 `wiki/entities/`
   - 稳定事实查 `wiki/truth/`
   - 口径冲突查 `wiki/conflicts/`
   - 证据来源查 `wiki/evidence/` 和 `wiki/sources/`
   - SOP / 运营动作查 `wiki/operations/`
5. 通过 wikilink 扩展到相关 source pages。
6. 回到 `wiki/sources/` 核对原始需求证据。

### graph 在普通查询中的作用

`graph/` 是 wiki 文档之间的链接图谱，由 `tools/build_graph.py` 从 `[[wikilink]]` 生成。

它的作用是帮助发现关联页面：

- 从一个概念找到所有相关 source。
- 从一个实体找到相关流程、规则、冲突。
- 从一个 source 找到已沉淀出的 concepts / entities / truth。
- 检查 wiki 是否有孤岛页面或断链。

但普通需求查询的最终答案仍然应落到文本证据：

- `BUSINESS_CONTEXT.md`
- `wiki/concepts/`
- `wiki/entities/`
- `wiki/truth/`
- `wiki/conflicts/`
- `wiki/sources/`

graph 是导航和质量检查工具，不是事实本身。

回答需求查询时应说明：

- 查询类型
- 是否使用 `BUSINESS_CONTEXT.md`
- 检索路径
- 结论
- 支撑页面
- 未决点

如果没有 source 支撑，不能把 layered page 中的总结当作最终事实，应该标注为推断或缺失证据。

## 4. 需求查询需要关联代码时系统如何运转

代码关联查询指用户不仅问“需求是什么”，还问：

- 代码是否实现了这个需求
- 哪个页面或接口实现了这个能力
- 前后端链路是什么
- 某个需求点对应哪个 Service / DAO / 表 / 消息 / 任务
- 代码和需求是否一致
- 哪些需求没有实现证据

### 双证据链

这类查询必须同时走两条证据链：

```text
需求证据链：
BUSINESS_CONTEXT.md
  -> wiki/concepts / wiki/entities
  -> wiki/sources
  -> 需求点

代码证据链：
wiki/code/codebases
  -> staging/code-graph manifest / endpoint-map
  -> graphify-out graph/report
  -> raw-code 代码锚点
  -> 实现候选
```

最后在 `wiki/code/capabilities/` 或 `wiki/code/traceability/` 中合并。

### 关联步骤

1. 先确定需求点。不能直接从代码名反推需求。必须先从 `BUSINESS_CONTEXT.md`、`wiki/sources/`、`concepts`、`entities` 明确业务含义。
2. 查已有能力页。如果 `wiki/code/capabilities/<capability>.md` 已存在，先读它，因为它是已经人工或 Codex 整合过的跨层解释。
3. 查 traceability。如果 `wiki/code/traceability/` 已存在相关矩阵，优先使用其中的 evidence strength 和代码锚点。
4. 查 codebase facts。读取 `wiki/code/codebases/<codebase_id>/index.md`，定位候选 codebase、endpoint、route、module role。
5. 查机器中间层：`manifest.json`、`endpoint-map.json`、`graphify-out/graph.json`、`GRAPH_REPORT.md`。
6. 回到 raw-code 验证代码锚点。最终代码证明必须尽量落到具体文件、类、方法、URI、配置、消息、任务或表字段。
7. 标注证据强度：
   - `strong`：需求有直接来源，代码也有直接锚点。
   - `partial`：能连到模块或服务族，但方法、字段、消息体或运行时条件不完整。
   - `inferred`：只能通过命名、相邻关系或 graphify 聚类推断。
   - `external`：实现边界在外部系统。
   - `missing`：没有找到可用代码或需求证据。

### graphify 在代码关联查询中的真实作用

对 `raw-code` 查询重是有意设计。原因是：

- `raw-code` 是最终代码事实来源。
- `graphify` 只能提供结构线索。
- 业务实现证明必须回到具体代码锚点。

graphify 的价值不在于替代 raw-code，而在于减少盲找：

1. 从入口扩展实现路径：如果扫描发现 `/api/search/cars`，graphify 可以帮助找到它周围的 handler、service、manager、dao、util 等相邻节点。
2. 找结构热点：大代码库里，graphify report 可以提示哪些模块是中心节点，适合作为能力页的候选实现链路。
3. 发现跨文件关系：字符串扫描只能找到 URI 或符号，graphify 可以提供文件结构关联线索。
4. 支撑 `inferred` / `partial` 级别判断：当直接证据不足时，graphify 可以作为推断依据，但不能升级为 `strong`。
5. 审查覆盖缺口：如果 capability 页面只引用了 controller，没有沿 graphify 线索检查 service / data-access，说明追踪可能不完整。

因此，图谱的定位是：

```text
graphify = 代码结构导航 + 候选扩展 + 覆盖审查线索
raw-code = 最终代码事实来源
wiki/code/traceability = 需求到代码的审计结论
```

不能只查 graphify，原因是：

- graphify 的节点和边是结构抽取结果，可能不包含运行时配置、网关映射、Dubbo 注册、消息订阅、数据库字段等完整上下文。
- graphify 不理解 `BUSINESS_CONTEXT.md` 的业务实体规范。
- graphify 边不等于业务调用链，有些只是文件结构、引用或相邻关系。
- 需求验收需要“需求来源 + 代码锚点 + 证据强度”，graphify 只能覆盖其中一部分。

### 一个典型例子

用户问：“C2 搜索车辆这个需求代码实现了吗？”

系统应这样运转：

1. 从 `BUSINESS_CONTEXT.md` 确认 `C2` 是购车 C 端用户。
2. 从 `wiki/sources/` 找到“搜索车辆”的需求来源。
3. 从 `wiki/concepts/` 或 `wiki/entities/` 确认相关概念和对象。
4. 从 `wiki/code/capabilities/` 查是否已有“车辆搜索”能力页。
5. 从 `endpoint-map.json` 找 `/api/search/cars`、`/ajax/car/search` 等候选 URI。
6. 从 codebase page 判断这些 URI 属于哪个前端或后端 codebase。
7. 从 graphify 输出扩展到相邻 service / manager / dao。
8. 回到 `raw-code/` 验证文件、方法和调用关系。
9. 写入或更新 traceability：

   ```text
   需求点: C2 搜索车辆
   需求来源: wiki/sources/...
   前端页面: raw-code/web/...
   API: /api/search/cars
   后端入口: raw-code/backend/...Controller...
   Service: raw-code/backend/...SearchService...
   DAO/索引/外部服务: ...
   证据强度: strong / partial / inferred / missing
   缺口: ...
   ```

10. 回答用户时明确区分：
    - 需求文档证明了什么
    - 代码实现证明了什么
    - 哪些只是推断
    - 哪些证据缺失

## 5. 总结：各层职责

| 层 | 目录 / 文件 | 主要职责 | 不能做什么 |
| --- | --- | --- | --- |
| 需求原文 | `raw/` | 原始需求证据 | 不修改，不提交，不能混入代码证据 |
| 业务基线 | `BUSINESS_CONTEXT.md` | 规范实体、角色、业务边界 | 不替代 source 证据 |
| 需求 wiki | `wiki/sources/` | source 摘要和证据页 | 不凭空扩展需求 |
| 分层 wiki | `wiki/concepts/` 等 | 跨 source 的概念、实体、事实、冲突 | 不替代原始证据 |
| 代码原文 | `raw-code/` | 最终代码事实来源 | 不修改，不把图谱输出写进去 |
| 代码扫描 | `staging/code-graph/*/manifest.json` | 文件角色、endpoint、route、符号候选 | 不证明业务语义 |
| 源码图谱 | `graphify-out/` | 结构关系、热点、候选扩展 | 不证明需求已实现 |
| 代码 wiki | `wiki/code/codebases/` | 单 codebase 事实入口 | 不替代 capability 解释 |
| 能力页 | `wiki/code/capabilities/` | 业务能力到代码链路解释 | 不无证据升级结论 |
| 追踪矩阵 | `wiki/code/traceability/` | 需求到代码的审计结论 | 不隐藏推断和缺口 |
| wiki 图谱 | `graph/` | wikilink 导航和健康检查 | 不作为事实本体 |

核心原则一句话：

```text
raw 和 raw-code 提供事实，脚本提供索引、候选和可规则化的证据分级，graph 提供导航和结构线索，traceability 负责留下可审计结论。模型判断如果参与 traceability，必须作为 trace worker proposal 落到结构化文件，再由确定性工具合并和渲染。
```
