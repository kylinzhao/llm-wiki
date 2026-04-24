# 构建与维护

## 1. 标准命令

```text
uv run python tools/build_wiki.py
uv run python tools/health.py --json
uv run python tools/build_graph.py
```

## 2. 各命令职责

### `build_wiki.py`

- 扫描 `raw/`
- 生成 `wiki/` 骨架
- 输出确定性结构

### `health.py`

- 检查结构健康度
- 查缺页、空页、漏索引

### `build_graph.py`

- 解析 wikilink
- 输出 graph 数据

## 3. 什么时候该重建

应该重建：

- 新增 `raw/`
- 更新了 `BUSINESS_CONTEXT.md`
- 修了 taxonomy / entity 规则
- 批量修了 wikilink

不必全量重建：

- 只是回答一个问题
- 只是做质量审查
- 只是修一两个 source page

## 4. 标准增量顺序

1. 更新 `raw/`
2. 更新 `BUSINESS_CONTEXT.md`
3. 跑 `build_wiki.py`
4. 做 AI-native 精修
5. 跑 `health.py`
6. 跑 `build_graph.py`
