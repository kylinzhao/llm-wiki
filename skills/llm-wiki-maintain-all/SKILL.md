---
name: llm-wiki-maintain-all
description: 批量维护本机已注册的 LLM Wiki KB 项目。用于发现本地 KB、查看/清理 KB registry，或对已注册 KB 执行完整 backfill/update 维护。
---

# LLM Wiki Maintain All

这是 `$llm-wiki-maintain-all` 的短入口，语义等价于 `llm-wiki maintain-all`。

语言要求：本短入口的用户回答和生成/改写的 LLM Wiki Markdown 文档必须默认使用中文，除非用户明确要求其他语言。

## 目标

用于维护本机多个已注册 LLM Wiki KB 项目。默认只 dry-run 输出计划；只有用户明确要求执行时才运行 `--apply`。

## 常用命令

```bash
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --discover /Users/zhaoliang/guazi/work
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --list
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --apply
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --prune-missing
```

## 执行规则

- 读取 **llm-wiki** 包内 `references/core-rules.md`、`references/commands/_shared.md` 与 `references/commands/maintain-all.md`（不要加载完整 `SKILL.md`）。
- 先解析当前安装的 `llm-wiki` skill 根目录，不要写死个人路径。
- 默认 dry-run，不修改 KB。
- 用户明确确认后才加 `--apply`。
- Cwiki 鉴权失败、dirty git worktree、raw-code checkout 损坏都必须作为单个 KB 的 blocker 报告，不要静默跳过或加 `--no-auto-raw-sync`。
- 批量执行时一个 KB 失败不阻塞后续 KB。
