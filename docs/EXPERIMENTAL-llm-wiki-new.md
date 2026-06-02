# llm-wiki-new（实验包，未合并 main）

与全局 `llm-wiki-*` **并行安装**，用于验证上下文瘦身改动；通过验证前不要替换生产 skill。

## 位置

| 项 | 路径 |
| --- | --- |
| 源码 worktree | `~/.config/superpowers/worktrees/llm-wiki-skill/optimize-skill-context` |
| 生成 bundle | `skills-new/`（由脚本生成，勿手改） |
| Cursor 安装 | `~/.cursor/skills/llm-wiki-new*`（symlink → worktree `skills-new/`） |

## 命令

```bash
cd ~/.config/superpowers/worktrees/llm-wiki-skill/optimize-skill-context

# 1. 从当前 skills/ 生成 llm-wiki-new*
./scripts/publish_llm_wiki_new.sh

# 2. 安装到 Cursor（不覆盖 llm-wiki-*）
./install-llm-wiki-new.sh --link --force --client cursor

# 3. 验证（pytest + 上下文预算 + dcn KB doctor）
./scripts/validate_llm_wiki_new.sh
```

验证 KB 默认：`/Users/zhaoliang/guazi/work/multi-knowledge-base-space/dcn-llm-wiki`  
可覆盖：`LLM_WIKI_NEW_VALIDATION_KB=/path/to/kb ./scripts/validate_llm_wiki_new.sh`

## Agent 入口

- `$llm-wiki-new-doctor` / `$llm-wiki-new-update` / `$llm-wiki-new-query` 等
- 子入口**不**加载 30KB 主 `SKILL.md`；加载 `core-rules.md` + `commands/_shared.md` + 单命令文件

## 卸载实验包（保留生产 llm-wiki）

```bash
rm -f ~/.cursor/skills/llm-wiki-new*
```

## 合并门槛

1. `validate_llm_wiki_new.sh` 通过  
2. 在 dcn（或目标 KB）上完成至少一轮 `$llm-wiki-new-doctor` + 必要时 `$llm-wiki-new-query` 人工验收  
3. 再 cherry-pick / merge `optimize-skill-context` → `main`（届时可去掉 `-new` 后缀或保留双轨一段时间）
