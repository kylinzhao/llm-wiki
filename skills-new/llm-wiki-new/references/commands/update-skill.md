## `llm-wiki-new update-skill`

Purpose: update the installed llm-wiki-new skill bundle itself. Use only when the user explicitly asks to update the skill, skill bundle, installed skill, or global llm-wiki tooling.

Update source:

- The updater first prefers a local llm-wiki-new-skill bundle checkout, using that checkout's configured git upstream.
- If no local checkout can be inferred, the updater may clone the canonical GitLab source `https://git.guazi-corp.com/c2b-fe/llm-wiki-new.git` into `~/.cache/llm-wiki-new-new-skill/llm-wiki-new`, then install from that cached checkout.
- Override the fallback Git URL with `--git-url` or `LLM_WIKI_SKILL_GIT_URL`; override the cache parent with `--cache-dir` or `LLM_WIKI_SKILL_CACHE_DIR`.
- If GitLab credentials are missing, create a Personal Access Token at `https://git.guazi-corp.com/profile/personal_access_tokens` with the `read_repository` scope.
- A GitHub remote may exist as a mirror, but do not switch to it unless the user explicitly asks or the local checkout is configured that way.
- If the installed skill was copied and no source checkout can be inferred, use the GitLab cache fallback unless the user requested offline mode with `--no-download`.

Default behavior:

1. Prefer the bundled updater when available:

   ```bash
   python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/update_installed_skill.py" --client auto --backup
   ```

2. If the installed skill was copied and the updater cannot infer the source checkout, it clones/pulls the GitLab fallback. To force a known local bundle checkout:

   ```bash
   python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/update_installed_skill.py" --source /path/to/llm-wiki-new-new-skill --client auto --backup
   ```

3. The updater runs `git pull --ff-only` in the bundle checkout when it is a git worktree, then runs `install.sh` with backup semantics.
4. Do not use `--force` unless the user explicitly accepts discarding the previous installed copy.
5. After updating the installed skill, existing KB projects keep their project-local tools until refreshed. To preview batch refresh/backfill for registered KBs, run:

   ```bash
   python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/maintain_all.py"
   ```

   To discover historical KBs first:

   ```bash
   python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/maintain_all.py" --discover /Users/zhaoliang/guazi/work
   ```

6. If the current directory is an LLM Wiki KB project and the user wants only this project refreshed, run:

   ```bash
   python3 "$LLM_WIKI_NEW_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
   ```

Stop when:

- No bundle checkout is available, GitLab clone/pull fails, and the user has not provided `--source`.
- `git pull --ff-only` fails because the bundle checkout has local conflicts or diverged history.
- installation reports destination conflicts without `--backup` or `--force`.
