---
name: llm-wiki-pull
description: LLM Wiki 只拉最新预热入口。用于只同步 KB git 与 raw/raw-code 证据缓存、报告上次更新时间与精修时间，不进入 source/concept/entity/wiki 精修、代码 wiki 重建或 shared publish。
---

# LLM Wiki Pull

这是 `$llm-wiki pull` 的短入口。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包内 `references/core-rules.md`（子入口必读；**不要**加载完整 `SKILL.md`）。
2. 读取 `references/commands/_shared.md` 与 `references/commands/pull.md`。
3. 将 `$llm-wiki-pull` 后面的用户文本作为 `llm-wiki pull` 参数。
4. `pull` 是 local-only 预热命令：只跑 KB git 同步（`git fetch --prune` + `git pull --ff-only`）和 `raw/`（按 `upstream/wiki-sources.json`）+ `raw-code/`（按 `upstream/code-sources.json`）证据同步，**不**修改 `wiki/` / `staging/` / `graph/` / `index/` / `tools/` 产物，**不**进入 shared publish，**不**调用 `tools/update_wiki.py` / `tools/graphify_code.py` / `tools/build_traceability.py` / `tools/doctor.py` 的写模式。
5. 报告必须给出 `last_update_time` 和 `last_refinement_time` 两个时间戳及来源，并按 `now - last_update_time` 是否超过 1 天给出"直接 query"或"建议 update"结论；1 天阈值是软提示，由用户决定是否升级。KB git 分叉、权限失败、`raw-code/` dirty / 未受管等阻断项必须显式列出，不降级为普通 gap。
6. 结束前必须输出 `建议下一步`。
