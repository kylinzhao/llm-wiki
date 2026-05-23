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

## 3. 从 wiki URL 拉取 raw（可选）

若证据在内网 Confluence/Cwiki，可先安装模板并同步依赖，再用内置导出器（来自同一模板下的 `tools/confluence_sync/`，与独立 obsidian-wiki-export 脚本同源能力）：

```bash
python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"
uv sync
COOKIE_HEADER='从浏览器 DevTools 复制的完整 Cookie' \
  uv run python tools/confluence_sync/export_obsidian_wiki.py \
  --url "https://cwiki.example.com/pages/viewpage.action?pageId=369287297" \
  --levels 3 \
  --project-dir "$PWD"
```

- **`--project-dir`**：页面 Markdown 写入 `<项目>/raw/`，每页为 `raw/<pageId>-<slug>/index.md` 及同目录 `assets/`（不再使用中间的 `pages-<rootId>/` 一层）。
- **状态文件**：默认在 `<项目>/staging/wiki-export/`（`export-state.json`、`progress/*.json`、`manifest-*.json`），不在 `raw/`。
- **增量更新**：首次导出后可在项目根执行  
  `COOKIE_HEADER='...' uv run python tools/confluence_sync/export_obsidian_wiki.py --update --project-dir "$PWD"`。

需要手动指定元数据目录时用 **`--metadata-dir`**；否则当输出目录为 `raw/` 时自动使用 `staging/wiki-export/`。

## 4. 初始化顺序

推荐顺序：

1. 检查 `raw/`（可为空；若上一步已从 wiki 拉取则已有页面）
2. 检查 `BUSINESS_CONTEXT.md`
3. 安装随 skill 打包的项目模板：

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD"
   ```

   `$LLM_WIKI_SKILL_ROOT` 为 llm-wiki skill 包根目录，定义见主 `SKILL.md` 的「Skill 包路径」。
   已构建的老 KB 如只需补齐 agent 查询路由规则，运行：

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --agent-rules-only
   ```

   该命令只把模板中的 `## Query Routing` 合并进 `AGENTS.md`，不会覆盖已有项目规则。

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

## 5. 关键判断

### 如果只有 raw，没有 BUSINESS_CONTEXT

可以启动，但要明确告诉用户：

- 后续更容易出现实体歧义
- 建议尽快补业务说明文档

### 如果 raw 和 BUSINESS_CONTEXT 都有

就应该把 `BUSINESS_CONTEXT.md` 作为生成基线，而不是等生成出错后再补。

## 6. 推荐策略

新项目首轮默认：

- 文本优先
- 不做图片多模态，除非文本不足以支撑首轮精修
- 但必须盘点 `raw/` 中是否存在图片资产；文本层完成后若图片存在且没有 image notes，必须把“阶段 H 高价值图片证据补充”写入状态和建议下一步
- 必须完成全量语料的首轮 summary 和 AI-native 精修
- 可以按层推进，但应在同一轮里做完
- 推荐顺序是先完成 `wiki/sources`，再完成 layered pages，最后补 `concepts / entities / graph`

不建议的首轮结束状态：

- 只有目录骨架，没有全量 summary
- 只有 `wiki/sources` 占位页，没有完成首轮精修
- 把“大模型 summary / 精修”整体推迟到后续增量维护阶段
