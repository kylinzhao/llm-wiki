# 0-1 初始化

## 1. 最小输入

一个新项目至少应准备：

- `raw/`
- `BUSINESS_CONTEXT.md`

如果这两个都没有，不应该开始构建。

## 2. 最小骨架

0-1 初始化后应具备：

- `wiki/`
- `graph/`
- `staging/`
- `docs/`
- `tools/`
- `AGENTS.md`

## 3. 初始化顺序

推荐顺序：

1. 检查 `raw/`
2. 检查 `BUSINESS_CONTEXT.md`
3. 初始化目录骨架
4. 初始化构建脚本
5. 运行 `build_wiki.py`
6. 运行 `health.py --json`
7. 做 AI-native 文本精修
8. 运行 `build_graph.py`

## 4. 关键判断

### 如果只有 raw，没有 BUSINESS_CONTEXT

可以启动，但要明确告诉用户：

- 后续更容易出现实体歧义
- 建议尽快补业务说明文档

### 如果 raw 和 BUSINESS_CONTEXT 都有

就应该把 `BUSINESS_CONTEXT.md` 作为生成基线，而不是等生成出错后再补。

## 5. 推荐策略

新项目首轮默认：

- 文本优先
- 不做图片多模态
- 先完成 `wiki/sources`
- 再补 layered pages / graph / syntheses / image-notes
