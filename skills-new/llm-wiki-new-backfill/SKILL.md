---
name: llm-wiki-new-backfill
description: LLM Wiki 存量知识库历史证据补全入口。用于老版本 skill 构建的 KB 重新扫描历史 raw/wiki/staging，补齐新版确定性证据能力，并默认触发后续精修吸收。（实验包 llm-wiki-new；与全局 llm-wiki 并行，验证通过后再合并）
---

# LLM Wiki Backfill

这是 `$llm-wiki-new-backfill` 的短入口，语义等价于 `llm-wiki-new backfill`。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

## 目标

用于已经存在的 LLM Wiki 项目，特别是用旧版 skill 构建过、但缺少新版历史证据派生能力的项目。它不是普通增量同步，也不是全量重建；它先对历史证据层做确定性补全，再把新增证据吸收到知识层。

## 执行顺序

1. 读取 **llm-wiki** 包内 `references/core-rules.md`、`references/commands/_shared.md` 与 `references/commands/backfill.md`（不要加载完整 `SKILL.md`）。
2. 解析当前安装的 `llm-wiki-new` skill 包根目录，不要写死个人本机路径。
3. 先刷新项目 engine-owned 工具和 agent rules：

   ```bash
   python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
   ```

4. 运行项目内 backfill 工具：

   ```bash
   uv run python tools/backfill.py
   ```

   如果项目没有 uv 环境，可回退：

   ```bash
   python3 tools/backfill.py
   ```

5. 读取 `staging/backfill/latest.json` 和 `latest.md`。
6. 如果 `refinement_absorption_required=true`，默认继续执行 `llm-wiki-new update` 语义，吸收新增证据：
   - 精修受影响 `wiki/sources/*`。
   - 刷新相关 concepts/entities。
   - 刷新 truth/conflicts/evidence/proposals/operations/reference。
   - 刷新 query acceptance 和 G+ quality audit。
   - 运行 health、graph 和必要 anchor checks。
7. 如果 backfill 没有产生证据变化，运行或建议 `llm-wiki-new doctor` 做只读确认即可。

## Backfill 范围

`tools/backfill.py` 使用 pass registry。当前内置 pass 包括：

- `drawio`：历史 `.drawio` / `.dio` 附件转 Mermaid 结构化证据，并回链 raw 页面。
- `source_metadata`：补齐旧 source page 的 Delivery Tracking 与 Source Metadata。
- `refinement_state_reconcile`：只做确定性状态收口；当 `wiki/sources/*` 已有完整精修结构且没有种子/待补标记时，把旧的 `pending` / `applied` / `complete` 状态规范为 `refined`，并补 `staging/refinement-status.md` 的 `reconciled_from_existing_content` 记录。
- `cjira`：扫描历史 raw 中的 Jira/Cjira/IDEA 信号，刷新 `staging/cjira-registry/`。
- `agent_rules`：补齐老 KB 的 Query Routing 规则。
- `wiki_export_state`：修复老 KB 的 Cwiki 导出控制状态；把 legacy `raw/export-state.json`、`raw/progress/*.json`、`staging/wiki-export/**` 复制到 canonical `staging/wiki-export-state/`，供 Gateway 临时 worktree 和其他用户本地 update 续跑。

后续凡是“需要重新扫历史文档才能补齐的新确定性能力”，都应新增为 backfill pass，而不是塞进普通 query 或只读 doctor。

## 边界

- 不重写 `raw/` 原文正文；只允许追加或刷新确定性 evidence 链接区。
- 不取消 `raw/` 的 Git ignore，也不把 `raw/**` 作为可提交内容；其他用户本地 raw 更新应通过 wiki-export/sync，而不是 Git pull raw 正文。
- 不把确定性 backfill 当成语义完成。只要新增证据影响 source/G+，必须继续精修吸收。
- 不把 Jira 鉴权缺失当成 draw.io/source metadata 的阻塞；离线能补的先补。
- 不建议用户再手动跑一串脚本；本入口应完成 backfill 到 update 收口的连续流程，除非遇到硬阻塞。

## 最终报告

报告必须区分：

- 确定性 backfill 增改了什么。
- 哪些 source/raw/evidence 页面进入 refinement scope。
- 精修吸收更新了哪些 wiki 层。
- health / graph / G+ quality 结果。
- 仍然阻塞或缺失的证据。
