# 查询逻辑

## 1. 默认顺序

1. 判断问题类型
2. 读取 `BUSINESS_CONTEXT.md`
3. 提取关键词与近义词
4. 选择优先目录层
5. 扩展 `concepts / entities`
6. 回到 `sources`
7. 必要时回 `raw/`

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

## 3. 实体规范

- `C1` = 卖车 C 端用户
- `C2` = 购车 C 端用户
- `车主` = `C1` 的历史别名

如果 `BUSINESS_CONTEXT.md` 有更明确的定义，以它为准。
