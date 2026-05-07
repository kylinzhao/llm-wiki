# 查询逻辑

## 1. 默认顺序

1. 判断问题类型
2. 读取 `BUSINESS_CONTEXT.md`
3. 提取关键词与近义词
4. 选择优先目录层
5. 扩展 `concepts / entities`
6. 回到 `sources`
7. 必要时回 `raw/`
8. 如果问题涉及代码实现，进入 `wiki/code/`

## 2. 优先目录层

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

## 3. 实体规范

- `C1` = 卖车 C 端用户
- `C2` = 购车 C 端用户
- `车主` = `C1` 的历史别名

如果 `BUSINESS_CONTEXT.md` 有更明确的定义，以它为准。

## 4. 代码证据回答规则

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

## 5. 跨端映射规则

前端到后端的映射优先使用稳定证据：

1. 前端 service 中的 URI 字符串
2. 后端 controller 的 `@RequestMapping` / `@GetMapping` / `@PostMapping`
3. request / response 类型名
4. controller 调用的 service
5. service 调用的 manager / dao / kafka / job

当 URI 能精确对上时，可以标记为“代码实现证明”。
当只能通过命名相似、能力页、graphify 聚类或 OpenSpec 标题关联时，只能标记为“推断”。

## 6. 追踪矩阵优先规则

当问题是实现类、测试追踪类、风险审计类或“需求落到哪里”时，优先查：

1. `wiki/code/traceability`
2. `wiki/code/capabilities`
3. `wiki/code/codebases`
4. `wiki/sources`

回答时保留矩阵中的证据强度，不要把 `partial`、`inferred`、`external`、`missing` 自动升级成确定结论。

## 7. 推荐回答形状

```text
查询类型：
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
