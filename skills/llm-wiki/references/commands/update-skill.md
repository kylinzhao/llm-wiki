## `llm-wiki update-skill`

Purpose: update the installed llm-wiki skill bundle itself. Use only when the user explicitly asks to update the skill, skill bundle, installed skill, or global llm-wiki tooling.

Update source:

- The updater first prefers a local llm-wiki-skill bundle checkout, using that checkout's configured git upstream.
- If no local checkout can be inferred, the updater may clone the canonical GitLab source `https://git.guazi-corp.com/c2b-fe/llm-wiki.git` into `~/.cache/llm-wiki-skill/llm-wiki`, then install from that cached checkout.
- Override the fallback Git URL with `--git-url` or `LLM_WIKI_SKILL_GIT_URL`; override the cache parent with `--cache-dir` or `LLM_WIKI_SKILL_CACHE_DIR`.
- Git operations first use the machine's existing SSH Key / Git credential helper. If HTTPS GitLab access fails and `~/.llm-wiki/guazi-sso.env` contains `GUAZI_GITLAB_TOKEN`, the updater retries with that token via `GIT_ASKPASS`.
- If GitLab credentials are missing, create a Personal Access Token at `https://git.guazi-corp.com/profile/personal_access_tokens` with the `read_repository` scope, then run `bash "${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/init_auth_env.sh"` and fill the optional GitLab token field.
- A GitHub remote may exist as a mirror, but do not switch to it unless the user explicitly asks or the local checkout is configured that way.
- If the installed skill was copied and no source checkout can be inferred, use the GitLab cache fallback unless the user requested offline mode with `--no-download`.

Default behavior:

1. Prefer the bundled updater when available:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --client auto --backup
   ```

2. If the installed skill was copied and the updater cannot infer the source checkout, it clones/pulls the GitLab fallback. To force a known local bundle checkout:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/update_installed_skill.py" --source /path/to/llm-wiki-skill --client auto --backup
   ```

3. The updater runs `git pull --ff-only` in the bundle checkout when it is a git worktree, then runs `install.sh` with backup semantics.
4. After a successful bundle install, the updater also refreshes the upstream **`prd-review-max`** dependency:

   ```bash
   ./scripts/install_prd_review_max.sh --link --upgrade --client auto
   ```

   This pulls `c2b-fe/pre-code` into `~/.cache/llm-wiki-skill/prd-review-max-upstream/` and keeps the installed skill link current. Pass `--skip-prd-review-max` to `update_installed_skill.py` only when the user explicitly opts out.
5. Do not use `--force` unless the user explicitly accepts discarding the previous installed copy.
6. After updating the installed skill, existing KB projects keep their project-local tools until refreshed. To preview batch refresh/backfill for registered KBs, run:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py"
   ```

   To discover historical KBs first:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --discover /Users/zhaoliang/guazi/work
   ```

7. If the current directory is an LLM Wiki KB project and the user wants only this project refreshed, run:

   ```bash
   python3 "$LLM_WIKI_SKILL_ROOT/scripts/install_project_template.py" --project "$PWD" --engine-only --refresh-agent-rules
   ```

Stop when:

- No bundle checkout is available, GitLab clone/pull fails, and the user has not provided `--source`.
- `git pull --ff-only` fails because the bundle checkout has local conflicts or diverged history.
- installation reports destination conflicts without `--backup` or `--force`.
