#!/usr/bin/env bash
set -euo pipefail

MODE="--copy"
DRY_RUN=0
FORCE=0
BACKUP=0
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT_DIR/skills"
DEST_DIR="${CODEX_HOME:-$HOME/.codex}/skills"

usage() {
  echo "Usage: $0 [--copy|--link] [--dry-run] [--force|--backup]" >&2
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
  local target="$DEST_DIR/$name"

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
  local timestamp
  local candidate
  local counter=2

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  candidate="$DEST_DIR/.backups/$name-$timestamp"
  while [[ -e "$candidate" ]]; do
    candidate="$DEST_DIR/.backups/$name-$timestamp-$counter"
    counter=$((counter + 1))
  done
  echo "$candidate"
}

ACTION_VERB="copy"
if [[ "$MODE" == "--link" ]]; then
  ACTION_VERB="link"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  for skill_dir in "$SRC_DIR"/*; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    target="$DEST_DIR/$name"
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
  echo "Dry run complete; no files changed."
  exit 0
fi

conflicts=0
if [[ "$FORCE" -eq 0 && "$BACKUP" -eq 0 ]]; then
  for skill_dir in "$SRC_DIR"/*; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    target="$DEST_DIR/$name"
    if [[ -e "$target" ]]; then
      echo "existing destination: $target (use --force or --backup)" >&2
      conflicts=$((conflicts + 1))
    fi
  done
fi

if [[ "$conflicts" -gt 0 ]]; then
  echo "Refusing to overwrite $conflicts existing skill(s)." >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

for skill_dir in "$SRC_DIR"/*; do
  [[ -d "$skill_dir" ]] || continue
  name="$(basename "$skill_dir")"
  target="$DEST_DIR/$name"
  if [[ -e "$target" ]]; then
    if [[ "$FORCE" -eq 1 ]]; then
      rm -rf "$target"
      install_skill "$skill_dir" "$name"
      echo "replaced $name"
    elif [[ "$BACKUP" -eq 1 ]]; then
      backup_target="$(backup_target_for "$name")"
      mkdir -p "$(dirname "$backup_target")"
      mv "$target" "$backup_target"
      echo "backed up $name to $backup_target"
      install_skill "$skill_dir" "$name"
    fi
  else
    install_skill "$skill_dir" "$name"
  fi
done

echo "Installed llm-wiki skills into $DEST_DIR"
