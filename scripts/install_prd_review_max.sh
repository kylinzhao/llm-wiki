#!/usr/bin/env bash
# Install prd-review-max from c2b-fe/pre-code (read-only upstream; do not patch).
set -euo pipefail

REPO_URL="${PRD_REVIEW_MAX_REPO_URL:-https://git.guazi-corp.com/c2b-fe/pre-code.git}"
REPO_REF="${PRD_REVIEW_MAX_REPO_REF:-master}"
SKILL_SUBDIR="prd-review-max"
CLIENT="auto"
MODE="--link"
DRY_RUN=0
FORCE=0
DEST_OVERRIDE=""

usage() {
  cat <<'EOF' >&2
Usage: install_prd_review_max.sh [--copy|--link] [--dry-run] [--force]
                                  [--client auto|codex|claude|cursor|qoder|all]
                                  [--dest <skills_dir>]

Installs prd-review-max from:
  https://git.guazi-corp.com/c2b-fe/pre-code/tree/master/prd-review-max

Defaults:
  --client auto
  --link
EOF
}

default_dest_for_client() {
  local client="$1"
  case "$client" in
    codex) printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/skills" ;;
    claude) printf '%s\n' "${CLAUDE_HOME:-$HOME/.claude}/skills" ;;
    cursor) printf '%s\n' "${CURSOR_HOME:-$HOME/.cursor}/skills" ;;
    qoder) printf '%s\n' "${QODER_HOME:-$HOME/.qoder}/skills" ;;
    *) echo "Unsupported client: $client" >&2; exit 2 ;;
  esac
}

resolve_clients() {
  local clients=()
  case "$CLIENT" in
    auto)
      [[ -n "${CODEX_HOME:-}" || -d "$HOME/.codex" ]] && clients+=("codex")
      [[ -n "${CLAUDE_HOME:-}" || -d "$HOME/.claude" ]] && clients+=("claude")
      [[ -n "${CURSOR_HOME:-}" || -d "$HOME/.cursor" ]] && clients+=("cursor")
      [[ -n "${QODER_HOME:-}" || -d "$HOME/.qoder" ]] && clients+=("qoder")
      ((${#clients[@]} == 0)) && clients=("cursor")
      ;;
    all) clients=("codex" "claude" "cursor" "qoder") ;;
    codex|claude|cursor|qoder) clients=("$CLIENT") ;;
    *) echo "Unsupported --client value: $CLIENT" >&2; exit 2 ;;
  esac
  printf '%s\n' "${clients[@]}"
}

resolve_destinations() {
  local client dest
  local -a resolved=()
  while IFS= read -r client; do
    [[ -n "$client" ]] || continue
    if [[ -n "$DEST_OVERRIDE" ]]; then
      dest="$DEST_OVERRIDE"
    else
      dest="$(default_dest_for_client "$client")"
    fi
    if ((${#resolved[@]} == 0)) || [[ " ${resolved[*]} " != *" $dest "* ]]; then
      resolved+=("$dest")
    fi
  done < <(resolve_clients)
  printf '%s\n' "${resolved[@]}"
}

find_existing_prd_review_max() {
  local dest
  for dest in "$@"; do
    [[ -f "$dest/prd-review-max/SKILL.md" ]] && { echo "$dest/prd-review-max"; return 0; }
  done
  return 1
}

while (($#)); do
  case "$1" in
    --copy|--link) MODE="$1" ;;
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    --client)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --client" >&2; exit 2; }
      CLIENT="$1"
      ;;
    --dest)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --dest" >&2; exit 2; }
      DEST_OVERRIDE="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

DEST_DIRS=()
while IFS= read -r dest_dir; do
  [[ -n "$dest_dir" ]] || continue
  DEST_DIRS+=("$dest_dir")
done < <(resolve_destinations)

if ((${#DEST_DIRS[@]} == 0)); then
  echo "No install destination resolved." >&2
  exit 2
fi

if existing="$(find_existing_prd_review_max "${DEST_DIRS[@]}")"; then
  echo "prd-review-max already installed: $existing"
  exit 0
fi

CACHE_DIR="${PRD_REVIEW_MAX_CACHE_DIR:-$HOME/.cache/llm-wiki-skill/prd-review-max-upstream}"
STAGING="$CACHE_DIR/checkout"

if [[ "$DRY_RUN" -eq 1 ]]; then
  for dest_dir in "${DEST_DIRS[@]}"; do
    echo "dry-run: would $MODE prd-review-max into $dest_dir/prd-review-max"
  done
  echo "dry-run: would fetch from $REPO_URL ($REPO_REF)"
  exit 0
fi

mkdir -p "$CACHE_DIR"
if [[ ! -d "$STAGING/.git" ]]; then
  git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$STAGING"
else
  git -C "$STAGING" fetch --depth 1 origin "$REPO_REF"
  git -C "$STAGING" checkout "$REPO_REF"
  git -C "$STAGING" pull --ff-only origin "$REPO_REF" || true
fi

if [[ ! -f "$STAGING/$SKILL_SUBDIR/SKILL.md" ]]; then
  echo "Missing upstream skill at $STAGING/$SKILL_SUBDIR/SKILL.md" >&2
  exit 1
fi

for dest_dir in "${DEST_DIRS[@]}"; do
  mkdir -p "$dest_dir"
  target="$dest_dir/prd-review-max"
  if [[ -e "$target" ]]; then
    if [[ "$FORCE" -eq 1 ]]; then
      rm -rf "$target"
    else
      echo "Refusing to overwrite existing $target (use --force)" >&2
      exit 1
    fi
  fi
  case "$MODE" in
    --copy)
      cp -R "$STAGING/$SKILL_SUBDIR" "$target"
      echo "copied prd-review-max -> $target"
      ;;
    --link)
      ln -s "$STAGING/$SKILL_SUBDIR" "$target"
      echo "linked prd-review-max -> $target"
      ;;
  esac
done

echo "Installed prd-review-max from upstream (unchanged)."
