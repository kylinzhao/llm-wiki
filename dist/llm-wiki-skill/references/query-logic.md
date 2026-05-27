# 查询逻辑

## 1. 默认顺序

1. 判断问题类型
2. 读取 `BUSINESS_CONTEXT.md`
3. 提取关键词与近义词
4. 选择优先目录层
5. 扩展 `concepts / entities`
6. 回到 `sources`
7. 必要时回 `raw/`
8. 只有当问题明确涉及代码实现、系统架构、接口、调用链、落地状态、测试追踪或用户调用 `query-plus` 时，才进入 `wiki/code/`

## 2. 查询模式

### `llm-wiki query`

默认按问题意图分流：

- **业务知识 / 产品规则 / 需求口径 / 术语解释**：只回答业务与需求结论，优先使用 `BUSINESS_CONTEXT.md`、`concepts`、`entities`、`truth`、`reference`、`sources`、`conflicts`、`evidence`、`proposals`、`operations`。不要主动展开代码实现细节；如需说明实现相关性，只用一句话标注“本回答未核验代码实现”或“如需代码落地证据请使用 `llm-wiki query-plus`”。
- **代码实现 / 接口 / 架构 / 调用链 / 源码位置 / 前后端映射 / 实现状态**：正常进入 `wiki/code/`，按代码证据回答规则输出需求证据、代码证据、推断和缺失证据。
- **业务逻辑是否已实现 / 需求落在哪里 / 线上行为和代码是否一致**：这是业务与代码交叉问题，`query` 可以进入 `wiki/code/`，但回答应比 `query-plus` 更克制，只输出完成结论所需的关键代码证据。

判断不清时，默认按业务知识问题处理，避免过度引入代码实现噪音；可以在未决点里提示用户改用 `query-plus` 获取完整业务+代码联动答案。

### `llm-wiki query-plus`

显式要求业务和代码一起回答。无论问题表面偏业务还是偏实现，都应同时检索：

1. `BUSINESS_CONTEXT.md`
2. 业务/需求 wiki 层
3. `wiki/code/traceability`
4. `wiki/code/capabilities`
5. `wiki/code/codebases`
6. 必要时回到 `sources`、`raw/`、`raw-code/`

回答可以更详尽，必须区分：

- 业务/需求口径
- 产品或运营规则
- 代码实现现状
- 前后端/服务/任务/配置等落点
- 需求与实现的一致性、偏差或缺口
- 基于命名、图谱或矩阵的推断

## 3. 优先目录层

### 问题 / 风险

- `conflicts`
- `evidence`
- `proposals`
- `sources`

### 方案 / 规划

- `proposals`
- `sources`

### 证据 / 结果

- `evidence`
- `sources`

### 接口 / 规则

- `reference`
- `truth`
- `sources`

### 操作 / 执行

- `operations`
- `sources`

### 代码实现 / 架构 / 调用链

- `wiki/code/traceability`
- `wiki/code/codebases`
- `wiki/code/capabilities`
- `concepts`
- `entities`
- `sources`

### 业务逻辑的实现状态

- `BUSINESS_CONTEXT.md`
- `concepts`
- `entities`
- `sources`
- `wiki/code/traceability`
- `wiki/code/capabilities`
- `wiki/code/codebases`

## 4. 实体规范

- `C1` = 卖车 C 端用户
- `C2` = 购车 C 端用户
- `车主` = `C1` 的历史别名

如果 `BUSINESS_CONTEXT.md` 有更明确的定义，以它为准。

## 5. 业务知识回答规则

当问题只是业务知识、产品规则、需求口径或术语解释时：

1. 不默认列出 `wiki/code/` 页面
2. 不展开 service / controller / endpoint / class / table / job 等实现细节
3. 不把“代码里有某接口”作为业务结论的主要证据
4. 结论优先来自业务上下文、需求文档、来源页、概念页、实体页、truth/reference/operations 等业务层页面
5. 如业务证据不足，可以说明“业务证据不足”，不要用代码实现补成业务规则
6. 如用户需要实现落地验证，建议改用 `llm-wiki query-plus`

推荐回答形状：

```text
查询类型：业务知识 / 产品规则 / 需求口径 / 术语解释
已使用 BUSINESS_CONTEXT.md：
检索路径：

结论：

业务 / 需求证据：
- ...

未决点 / 证据缺口：
- ...

实现核验：
- 本次 query 未展开代码实现；如需业务+代码联动证据，请使用 llm-wiki query-plus。
```

## 6. 代码证据回答规则

当回答涉及代码时，必须显式说明：

1. 使用了哪些 codebase
2. 使用了哪些 `wiki/code/` 页面
3. 是否回查了需求文档层
4. 哪些结论来自需求文档
5. 哪些结论来自代码实现
6. 哪些只是基于命名、调用关系或图谱的推断
7. 哪些证据仍缺失

不要把前端可见行为写成后端规则。
不要把后端接口存在写成业务一定生效。
不要把 graphify 推断边写成源码直接事实。

## 7. 跨端映射规则

前端到后端的映射优先使用稳定证据：

1. 前端 service 中的 URI 字符串
2. 后端 controller 的 `@RequestMapping` / `@GetMapping` / `@PostMapping`
3. request / response 类型名
4. controller 调用的 service
5. service 调用的 manager / dao / kafka / job

当 URI 能精确对上时，可以标记为“代码实现证明”。
当只能通过命名相似、能力页、graphify 聚类或 OpenSpec 标题关联时，只能标记为“推断”。

## 8. 追踪矩阵优先规则

当问题是实现类、测试追踪类、风险审计类或“需求落到哪里”时，优先查：

1. `wiki/code/traceability`
2. `wiki/code/capabilities`
3. `wiki/code/codebases`
4. `wiki/sources`

回答时保留矩阵中的证据强度，不要把 `partial`、`inferred`、`external`、`missing` 自动升级成确定结论。

## 9. 代码 / `query-plus` 推荐回答形状

```text
查询类型：代码实现 / 业务实现状态 / query-plus
已使用 BUSINESS_CONTEXT.md：
检索路径：

结论：

需求文档证据：
- ...

代码实现证据：
- codebase: ...
- page/service/controller/class: ...

推断：
- ...

缺失证据 / 未决点：
- ...
```
