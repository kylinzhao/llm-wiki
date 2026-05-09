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
3. 安装随 skill 打包的项目模板：

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"
   ```

   `$LLM_WIKI_SKILL_ROOT` 为 llm-wiki skill 包根目录，定义见主 `SKILL.md` 的「Skill 包路径」。

4. 运行确定性初始化：

   ```bash
   uv run python tools/update_wiki.py
   ```

5. 如果存在 `raw-code/` 且需要图谱增强，运行：

   ```bash
   uv run python tools/graphify_code.py --all
   uv run python tools/scan_code.py
   uv run python tools/build_traceability.py
   ```

6. 对全量语料完成首轮大模型 summary
7. 对全量语料完成 AI-native 文本精修与分层落位
8. 对代码能力页和 traceability 完成 Codex-native 证据强度判定
9. 运行 `health.py --json`
10. 运行 `build_graph.py`
11. 运行 `anchor_check.py`

模板必须包含完整工程底座，而不是只有最小 demo。目标项目至少应获得：

- `tools/build_wiki.py`
- `tools/scan_code.py`
- `tools/graphify_code.py`
- `tools/build_traceability.py`
- `tools/health.py`
- `tools/build_graph.py`
- `tools/anchor_check.py`
- `docs/tooling-dependencies.md`
- `docs/implementation-workflow.md`
- 项目级 `AGENTS.md`

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
- 不做图片多模态，除非文本不足以支撑首轮精修
- 必须完成全量语料的首轮 summary 和 AI-native 精修
- 可以按层推进，但应在同一轮里做完
- 推荐顺序是先完成 `wiki/sources`，再完成 layered pages，最后补 `concepts / entities / graph`

不建议的首轮结束状态：

- 只有目录骨架，没有全量 summary
- 只有 `wiki/sources` 占位页，没有完成首轮精修
- 把“大模型 summary / 精修”整体推迟到后续增量维护阶段
