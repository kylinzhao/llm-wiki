#!/usr/bin/env bash
set -euo pipefail

MODE="--copy"
DRY_RUN=0
FORCE=0
BACKUP=0
CLIENT="auto"
DEST_OVERRIDE=""
BACKUP_DIR_OVERRIDE=""
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT_DIR/skills"
DEPRECATED_SKILLS=(
  "llm-wiki-audit"
  "llm-wiki-build-code"
  "llm-wiki-code-trace"
  "llm-wiki-refine"
  "llm-wiki-resume"
  "llm-wiki-ship"
)

usage() {
  cat <<'EOF' >&2
Usage: install.sh [--copy|--link] [--dry-run] [--force|--backup]
                  [--client auto|codex|claude|cursor|all]
                  [--dest <skills_dir>]
                  [--backup-dir <dir>]

Defaults:
  --client auto
  --copy

Client default destinations:
  codex  -> ${CODEX_HOME:-$HOME/.codex}/skills
  claude -> ${CLAUDE_HOME:-$HOME/.claude}/skills
  cursor -> ${CURSOR_HOME:-$HOME/.cursor}/skills

Backup default destination (when --backup):
  ${LLM_WIKI_SKILL_BACKUP_DIR:-$HOME/.llm-wiki-skill-backups}
EOF
}

contains() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

default_dest_for_client() {
  local client="$1"
  case "$client" in
    codex)
      printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/skills"
      ;;
    claude)
      printf '%s\n' "${CLAUDE_HOME:-$HOME/.claude}/skills"
      ;;
    cursor)
      printf '%s\n' "${CURSOR_HOME:-$HOME/.cursor}/skills"
      ;;
    *)
      echo "Unsupported client: $client" >&2
      exit 2
      ;;
  esac
}

resolve_clients() {
  local clients=()
  case "$CLIENT" in
    auto)
      [[ -n "${CODEX_HOME:-}" || -d "$HOME/.codex" ]] && clients+=("codex")
      [[ -n "${CLAUDE_HOME:-}" || -d "$HOME/.claude" ]] && clients+=("claude")
      [[ -n "${CURSOR_HOME:-}" || -d "$HOME/.cursor" ]] && clients+=("cursor")
      if ((${#clients[@]} == 0)); then
        clients=("codex")
      fi
      ;;
    all)
      clients=("codex" "claude" "cursor")
      ;;
    codex|claude|cursor)
      clients=("$CLIENT")
      ;;
    *)
      echo "Unsupported --client value: $CLIENT" >&2
      exit 2
      ;;
  esac

  printf '%s\n' "${clients[@]}"
}

resolve_destinations() {
  local clients=()
  local resolved=()
  local client
  local dest

  while IFS= read -r client; do
    [[ -n "$client" ]] || continue
    clients+=("$client")
  done < <(resolve_clients)

  for client in "${clients[@]}"; do
    if [[ -n "$DEST_OVERRIDE" ]]; then
      dest="$DEST_OVERRIDE"
    else
      dest="$(default_dest_for_client "$client")"
    fi
    if ((${#resolved[@]} == 0)); then
      resolved+=("$dest")
    elif ! contains "$dest" "${resolved[@]}"; then
      resolved+=("$dest")
    fi
  done

  printf '%s\n' "${resolved[@]}"
}

while (($#)); do
  case "$1" in
    --copy|--link)
      MODE="$1"
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --force)
      FORCE=1
      ;;
    --backup)
      BACKUP=1
      ;;
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
    --backup-dir)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --backup-dir" >&2; exit 2; }
      BACKUP_DIR_OVERRIDE="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
  shift
done

if [[ "$FORCE" -eq 1 && "$BACKUP" -eq 1 ]]; then
  echo "Choose only one of --force or --backup." >&2
  exit 2
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Missing skills directory: $SRC_DIR" >&2
  exit 1
fi

install_skill() {
  local skill_dir="$1"
  local name="$2"
  local dest_dir="$3"
  local target="$dest_dir/$name"

  case "$MODE" in
    --copy)
      cp -R "$skill_dir" "$target"
      echo "copied $name"
      ;;
    --link)
      ln -s "$skill_dir" "$target"
      echo "linked $name"
      ;;
  esac
}

backup_target_for() {
  local name="$1"
  local backup_dir="$2"
  local timestamp
  local candidate
  local counter=2

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  candidate="$backup_dir/$name-$timestamp"
  while [[ -e "$candidate" ]]; do
    candidate="$backup_dir/$name-$timestamp-$counter"
    counter=$((counter + 1))
  done
  echo "$candidate"
}

backup_dir_for_dest() {
  local dest_dir="$1"
  if [[ -n "$BACKUP_DIR_OVERRIDE" ]]; then
    printf '%s\n' "$BACKUP_DIR_OVERRIDE"
  elif [[ -n "${LLM_WIKI_SKILL_BACKUP_DIR:-}" ]]; then
    printf '%s\n' "$LLM_WIKI_SKILL_BACKUP_DIR"
  else
    printf '%s\n' "$HOME/.llm-wiki-skill-backups"
  fi
}

ACTION_VERB="copy"
if [[ "$MODE" == "--link" ]]; then
  ACTION_VERB="link"
fi

check_conflicts_for_dest() {
  local dest_dir="$1"
  local conflicts=0
  for skill_dir in "$SRC_DIR"/*; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    target="$dest_dir/$name"
    if [[ -e "$target" ]]; then
      echo "existing destination: $target (use --force or --backup)" >&2
      conflicts=$((conflicts + 1))
    fi
  done
  printf '%s\n' "$conflicts"
}

run_dry_for_dest() {
  local dest_dir="$1"
  local deprecated
  local target
  echo "dry-run: destination $dest_dir"
  for deprecated in "${DEPRECATED_SKILLS[@]}"; do
    target="$dest_dir/$deprecated"
    if [[ -e "$target" ]]; then
      if [[ "$FORCE" -eq 1 ]]; then
        echo "dry-run: would remove deprecated $deprecated"
      elif [[ "$BACKUP" -eq 1 ]]; then
        echo "dry-run: would back up deprecated $deprecated"
      else
        echo "dry-run: would leave deprecated $deprecated (use --backup or --force to prune)"
      fi
    fi
  done
  for skill_dir in "$SRC_DIR"/*; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    target="$dest_dir/$name"
    if [[ -e "$target" ]]; then
      if [[ "$FORCE" -eq 1 ]]; then
        echo "dry-run: would replace $name"
      elif [[ "$BACKUP" -eq 1 ]]; then
        echo "dry-run: would back up $name then $ACTION_VERB"
      else
        echo "dry-run: would skip existing $name (use --force or --backup)"
      fi
    else
      echo "dry-run: would $ACTION_VERB $name"
    fi
  done
}

prune_deprecated_for_dest() {
  local dest_dir="$1"
  local backup_dir
  local deprecated
  local target
  local backup_target

  backup_dir="$(backup_dir_for_dest "$dest_dir")"
  for deprecated in "${DEPRECATED_SKILLS[@]}"; do
    target="$dest_dir/$deprecated"
    [[ -e "$target" ]] || continue
    if [[ "$FORCE" -eq 1 ]]; then
      rm -rf "$target"
      echo "removed deprecated $deprecated"
    elif [[ "$BACKUP" -eq 1 ]]; then
      backup_target="$(backup_target_for "$deprecated" "$backup_dir")"
      mkdir -p "$(dirname "$backup_target")"
      mv "$target" "$backup_target"
      echo "backed up deprecated $deprecated to $backup_target"
    fi
  done
}

install_for_dest() {
  local dest_dir="$1"
  local backup_dir
  mkdir -p "$dest_dir"
  backup_dir="$(backup_dir_for_dest "$dest_dir")"
  prune_deprecated_for_dest "$dest_dir"

  for skill_dir in "$SRC_DIR"/*; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    target="$dest_dir/$name"
    if [[ -e "$target" ]]; then
      if [[ "$FORCE" -eq 1 ]]; then
        rm -rf "$target"
        install_skill "$skill_dir" "$name" "$dest_dir"
        echo "replaced $name"
      elif [[ "$BACKUP" -eq 1 ]]; then
        backup_target="$(backup_target_for "$name" "$backup_dir")"
        mkdir -p "$(dirname "$backup_target")"
        mv "$target" "$backup_target"
        echo "backed up $name to $backup_target"
        install_skill "$skill_dir" "$name" "$dest_dir"
      fi
    else
      install_skill "$skill_dir" "$name" "$dest_dir"
    fi
  done
}

DEST_DIRS=()
while IFS= read -r dest_dir; do
  [[ -n "$dest_dir" ]] || continue
  DEST_DIRS+=("$dest_dir")
done < <(resolve_destinations)

if ((${#DEST_DIRS[@]} == 0)); then
  echo "No install destination resolved. Check --client/--dest options." >&2
  exit 2
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  for dest_dir in "${DEST_DIRS[@]}"; do
    run_dry_for_dest "$dest_dir"
  done
  echo "Dry run complete; no files changed."
  exit 0
fi

total_conflicts=0
if [[ "$FORCE" -eq 0 && "$BACKUP" -eq 0 ]]; then
  for dest_dir in "${DEST_DIRS[@]}"; do
    conflicts="$(check_conflicts_for_dest "$dest_dir")"
    total_conflicts=$((total_conflicts + conflicts))
  done
fi

if [[ "$total_conflicts" -gt 0 ]]; then
  echo "Refusing to overwrite $total_conflicts existing skill(s)." >&2
  exit 1
fi

for dest_dir in "${DEST_DIRS[@]}"; do
  install_for_dest "$dest_dir"
done

echo "Installed llm-wiki skills into:"
for dest_dir in "${DEST_DIRS[@]}"; do
  echo "  - $dest_dir"
done
