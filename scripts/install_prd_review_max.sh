#!/usr/bin/env bash
# Install or upgrade prd-review-max from c2b-fe/pre-code (read-only upstream; do not patch).
set -euo pipefail

REPO_URL="${PRD_REVIEW_MAX_REPO_URL:-https://git.guazi-corp.com/c2b-fe/pre-code.git}"
REPO_REF="${PRD_REVIEW_MAX_REPO_REF:-master}"
SKILL_SUBDIR="prd-review-max"
CLIENT="auto"
MODE="--link"
DRY_RUN=0
FORCE=0
UPGRADE=0
DEST_OVERRIDE=""
AUTH_ENV_FILE="${LLM_WIKI_AUTH_ENV_FILE:-$HOME/.llm-wiki/guazi-sso.env}"
GITLAB_PAT_URL="https://git.guazi-corp.com/profile/personal_access_tokens"

usage() {
  cat <<'EOF' >&2
Usage: install_prd_review_max.sh [--copy|--link] [--upgrade] [--dry-run] [--force]
                                  [--client auto|codex|claude|cursor|qoder|all]
                                  [--dest <skills_dir>]

Installs prd-review-max from:
  https://git.guazi-corp.com/c2b-fe/pre-code/tree/master/prd-review-max

Defaults:
  --client auto
  --link

  --upgrade   Pull latest upstream and refresh install (used by update-skill)
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

target_points_to_staging() {
  local target="$1"
  local expected="$2"
  [[ -L "$target" ]] || return 1
  local resolved
  resolved="$(cd "$(dirname "$target")" && readlink "$(basename "$target")" || true)"
  [[ "$resolved" == "$expected" ]] || [[ "$(readlink -f "$target" 2>/dev/null || true)" == "$(readlink -f "$expected" 2>/dev/null || true)" ]]
}

load_gitlab_token() {
  [[ -n "${GUAZI_GITLAB_TOKEN:-}" ]] && return 0
  [[ -f "$AUTH_ENV_FILE" ]] || return 0
  # shellcheck disable=SC1090
  source "$AUTH_ENV_FILE" || true
}

gitlab_auth_help() {
  cat >&2 <<EOF
GitLab 鉴权失败。请先确认本机 SSH Key / Git 凭据可访问 git.guazi-corp.com；
或到 $GITLAB_PAT_URL 申请 Personal Access Token（scope: read_repository），
再运行 bash "\${CODEX_HOME:-\$HOME/.codex}/skills/llm-wiki/scripts/init_auth_env.sh" 填入 GitLab token 后重试。
EOF
}

with_git_token_retry() {
  "$@" && return 0
  local code=$?
  [[ "$REPO_URL" == https://git.guazi-corp.com/* ]] || return "$code"
  load_gitlab_token
  if [[ -z "${GUAZI_GITLAB_TOKEN:-}" ]]; then
    gitlab_auth_help
    return "$code"
  fi
  local askpass
  askpass="$(mktemp "${TMPDIR:-/tmp}/llm-wiki-git-askpass.XXXXXX")"
  cat > "$askpass" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' oauth2 ;;
  *Password*) printf '%s\n' "$GUAZI_GITLAB_TOKEN" ;;
  *) printf '\n' ;;
esac
EOF
  chmod 700 "$askpass"
  GIT_ASKPASS="$askpass" GIT_TERMINAL_PROMPT=0 "$@"
  code=$?
  rm -f "$askpass"
  if [[ "$code" -ne 0 ]]; then
    gitlab_auth_help
  fi
  return "$code"
}

while (($#)); do
  case "$1" in
    --copy|--link) MODE="$1" ;;
    --upgrade) UPGRADE=1 ;;
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

CACHE_DIR="${PRD_REVIEW_MAX_CACHE_DIR:-$HOME/.cache/llm-wiki-skill/prd-review-max-upstream}"
STAGING="$CACHE_DIR/checkout"
UPSTREAM_SKILL="$STAGING/$SKILL_SUBDIR"

pull_upstream() {
  mkdir -p "$CACHE_DIR"
  if [[ ! -d "$STAGING/.git" ]]; then
    with_git_token_retry git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$STAGING"
  else
    with_git_token_retry git -C "$STAGING" fetch --depth 1 origin "$REPO_REF"
    git -C "$STAGING" checkout "$REPO_REF"
    with_git_token_retry git -C "$STAGING" pull --ff-only origin "$REPO_REF" || true
  fi
  if [[ ! -f "$UPSTREAM_SKILL/SKILL.md" ]]; then
    echo "Missing upstream skill at $UPSTREAM_SKILL/SKILL.md" >&2
    exit 1
  fi
}

print_upstream_version() {
  if [[ -f "$UPSTREAM_SKILL/manifest.json" ]]; then
    python3 - <<'PY' "$UPSTREAM_SKILL/manifest.json"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"prd-review-max version: {data.get('version', 'unknown')}")
PY
  fi
  if [[ -d "$STAGING/.git" ]]; then
    echo "prd-review-max commit: $(git -C "$STAGING" rev-parse --short HEAD)"
  fi
}

install_target() {
  local dest_dir="$1"
  local target="$dest_dir/prd-review-max"

  if [[ -e "$target" ]]; then
    if [[ "$MODE" == "--link" ]] && target_points_to_staging "$target" "$UPSTREAM_SKILL"; then
      echo "prd-review-max link up to date: $target"
      return 0
    fi
    if [[ "$FORCE" -eq 1 ]]; then
      rm -rf "$target"
    else
      echo "Refusing to overwrite existing $target (use --force or --upgrade with --copy)" >&2
      exit 1
    fi
  fi

  case "$MODE" in
    --copy)
      cp -R "$UPSTREAM_SKILL" "$target"
      echo "copied prd-review-max -> $target"
      ;;
    --link)
      ln -s "$UPSTREAM_SKILL" "$target"
      echo "linked prd-review-max -> $target"
      ;;
  esac
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  for dest_dir in "${DEST_DIRS[@]}"; do
    if [[ "$UPGRADE" -eq 1 ]]; then
      echo "dry-run: would pull upstream and refresh prd-review-max in $dest_dir"
    else
      echo "dry-run: would $MODE prd-review-max into $dest_dir/prd-review-max"
    fi
  done
  echo "dry-run: would fetch from $REPO_URL ($REPO_REF)"
  exit 0
fi

if [[ "$UPGRADE" -eq 1 ]]; then
  pull_upstream
  for dest_dir in "${DEST_DIRS[@]}"; do
    install_target "$dest_dir"
  done
  print_upstream_version
  echo "Upgraded prd-review-max from upstream (unchanged content in cache)."
  exit 0
fi

if existing="$(find_existing_prd_review_max "${DEST_DIRS[@]}")"; then
  echo "prd-review-max already installed: $existing"
  echo "Run with --upgrade to pull latest upstream (or use llm-wiki update-skill)."
  exit 0
fi

pull_upstream
for dest_dir in "${DEST_DIRS[@]}"; do
  install_target "$dest_dir"
done
print_upstream_version
echo "Installed prd-review-max from upstream (unchanged)."
