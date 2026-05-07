# 文档结构说明

## 根目录关键文件

### `BUSINESS_CONTEXT.md`

业务语义基线。

### `raw/`

原始输入。

### `raw-code/`

可选源码证据入口。

- `raw-code/*` 的每个一级目录是一个独立 `codebase_id`
- 不要把源码、技术设计和代码图谱输出混进 `raw/`
- 单个 `codebase_id` 可以是前端、后端、脚本仓库、SDK 或工具仓库
- 同一项目可以同时存在多个 codebase，并通过 `wiki/code/capabilities/` 汇聚到业务能力

## wiki 目录

### `wiki/sources/`

主知识页。

### `wiki/proposals/`

方案与规划。

### `wiki/evidence/`

证据与复盘。

### `wiki/reference/`

接口与规则。

### `wiki/operations/`

执行与流程。

### `wiki/conflicts/`

问题与冲突。

### `wiki/truth/`

稳定事实。

### `wiki/concepts/`

主题索引。

### `wiki/entities/`

实体索引。

### `wiki/code/`

可选代码知识层。

推荐结构：

```text
wiki/code/
  index.md
  codebases/
    <codebase_id>/
      index.md
  capabilities/
    <capability>.md
```

`wiki/code/codebases/<codebase_id>/` 只写单仓库内部事实，不直接替代业务需求文档。

前端 codebase 常见结构：

```text
wiki/code/codebases/<frontend-id>/
  index.md
  routes.md
  pages/
  services/
  components/
```

后端 codebase 常见结构：

```text
wiki/code/codebases/<backend-id>/
  index.md
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

`wiki/code/capabilities/` 是跨层聚合页。它连接：

- `BUSINESS_CONTEXT.md` 中的规范实体和术语
- `wiki/concepts/` 与 `wiki/entities/`
- `wiki/sources/` 中的需求、技术方案、分析和会议记录
- 前端页面、前端 service、后端 endpoint、后端 service、异步任务、数据访问和技术设计

能力页必须区分：

- 需求文档证明
- 代码实现证明
- 推断
- 缺失证据

## staging 目录

### `staging/code-graph/`

可选代码图谱中间产物。

推荐结构：

```text
staging/code-graph/
  <codebase_id>/
    graphify-out/
    manifest.json
    endpoint-map.json
```

`graphify-out/` 由 graphify 生成；`manifest.json` 和 `endpoint-map.json` 可以由 Codex 或项目脚本维护，用于记录 codebase 类型、扫描范围、输出路径和跨端 API 映射。
