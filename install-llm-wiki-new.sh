#!/usr/bin/env bash
# Install only the experimental llm-wiki-new* bundle. Does not modify existing llm-wiki-* skills.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LLM_WIKI_SKILL_SRC_DIR="$ROOT_DIR/skills-new"

if [[ ! -d "$LLM_WIKI_SKILL_SRC_DIR" ]]; then
  echo "Missing $LLM_WIKI_SKILL_SRC_DIR — run ./scripts/publish_llm_wiki_new.sh first." >&2
  exit 1
fi

# Reuse install.sh with overridden source directory (only llm-wiki-new* names → no conflict)
if (("$#")); then
  exec env LLM_WIKI_SKILL_SRC_DIR="$LLM_WIKI_SKILL_SRC_DIR" \
    "$ROOT_DIR/install.sh" "$@"
fi
exec env LLM_WIKI_SKILL_SRC_DIR="$LLM_WIKI_SKILL_SRC_DIR" \
  "$ROOT_DIR/install.sh" --client "${LLM_WIKI_NEW_CLIENT:-cursor}"
