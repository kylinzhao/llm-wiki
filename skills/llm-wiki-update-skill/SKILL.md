---
name: llm-wiki-update-skill
description: LLM Wiki skill bundle 自更新入口。用于显式更新本机安装的 llm-wiki skills、模板脚本和命令协议；不更新当前 KB 内容。
---

# LLM Wiki Update Skill

这是 `$llm-wiki update-skill` 的短入口。

语言要求：本短入口的用户回答必须默认使用中文，除非用户明确要求其他语言。

1. 读取 **llm-wiki** skill 包根目录下的 `SKILL.md`（路径由当前环境的 skill 安装位置解析，勿写死本机绝对路径）。
2. 读取同包内 `references/commands.md` 的 `llm-wiki update-skill` 小节。
3. 将 `$llm-wiki-update-skill` 后面的用户文本作为 `llm-wiki update-skill` 参数。
4. 只更新已安装的 llm-wiki skill bundle 本体；不要更新当前 KB 的 `raw/`、`wiki/`、`raw-code/` 或项目构建产物。
5. 默认使用安全备份安装语义：`--backup`，不要使用 `--force`，除非用户明确要求丢弃旧安装。备份目录默认落在 `~/.llm-wiki-skill-backups/`（可用 `--backup-dir` 覆盖），避免把备份留在 skills 扫描目录。
6. 更新来源优先级：
   - 如果用户提供了 `--source` 或明确给出本地 bundle checkout，使用该路径。
   - 如果当前 installed skill 是软链或可从脚本路径推断 bundle checkout，使用推断出的本地 checkout，并在其中执行 `git pull --ff-only`。
   - 如果无法推断来源，允许 updater 使用公司 GitLab 默认地址 `https://git.guazi-corp.com/c2b-fe/llm-wiki.git` 下载到本地 cache 后安装；可用 `--git-url` 或 `LLM_WIKI_SKILL_GIT_URL` 覆盖。
   - 只有用户明确要求离线或传入 `--no-download` 时，才在无法推断来源时询问用户提供本地 `llm-wiki-skill` checkout 路径。
7. 默认命令形态：

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --client auto --backup
   ```

   如果需要指定源码 checkout：

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --source /path/to/llm-wiki-skill --client auto --backup
   ```

8. 更新完成后报告：使用的 source/cache、是否执行了 clone 或 `git pull --ff-only`、安装目标 client、备份/覆盖策略、是否还需要对某个 KB 运行 `llm-wiki update` 以刷新项目内工具。
9. 最后输出 `建议下一步`。
