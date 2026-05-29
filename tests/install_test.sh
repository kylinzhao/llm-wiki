#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_file() {
  [[ -f "$1" ]] || fail "expected file: $1"
}

assert_no_path() {
  [[ ! -e "$1" ]] || fail "expected no path: $1"
}

assert_contains() {
  local needle="$1"
  local file="$2"
  local content
  content="$(<"$file")"
  if [[ "$content" != *"$needle"* ]]; then
    echo "---- $file ----" >&2
    printf '%s\n' "$content" >&2
    fail "expected '$needle' in $file"
  fi
}

run_install() {
  local home="$1"
  shift
  HOME="$home" CODEX_HOME="$home" "$ROOT_DIR/install.sh" --client codex "$@"
}

run_install_claude() {
  local home="$1"
  shift
  HOME="$home" CLAUDE_HOME="$home" "$ROOT_DIR/install.sh" --client claude "$@"
}

run_install_cursor() {
  local home="$1"
  shift
  HOME="$home" CURSOR_HOME="$home" "$ROOT_DIR/install.sh" --client cursor "$@"
}

run_install_qoder() {
  local home="$1"
  shift
  HOME="$home" QODER_HOME="$home" "$ROOT_DIR/install.sh" --client qoder "$@"
}

test_default_refuses_existing_skill() {
  local home="$TMP_DIR/default-refuse"
  local skill_dir="$home/skills/llm-wiki"
  mkdir -p "$skill_dir"
  echo "local edit" >"$skill_dir/local.txt"

  if run_install "$home" --copy >"$TMP_DIR/default.out" 2>"$TMP_DIR/default.err"; then
    fail "default install should refuse to overwrite existing skills"
  fi

  assert_file "$skill_dir/local.txt"
  assert_contains "existing destination" "$TMP_DIR/default.err"
  assert_contains "--force or --backup" "$TMP_DIR/default.err"
}

test_dry_run_does_not_write() {
  local home="$TMP_DIR/dry-run"

  run_install "$home" --copy --dry-run >"$TMP_DIR/dry-run.out"

  assert_no_path "$home/skills"
  assert_contains "dry-run" "$TMP_DIR/dry-run.out"
  assert_contains "would copy llm-wiki" "$TMP_DIR/dry-run.out"
  assert_contains "would copy llm-wiki-backfill" "$TMP_DIR/dry-run.out"
}

test_backup_preserves_existing_skill() {
  local home="$TMP_DIR/backup"
  local skill_dir="$home/skills/llm-wiki"
  mkdir -p "$skill_dir"
  echo "local edit" >"$skill_dir/local.txt"

  run_install "$home" --copy --backup >"$TMP_DIR/backup.out"

  assert_file "$home/skills/llm-wiki/SKILL.md"
  assert_no_path "$home/skills/llm-wiki/local.txt"
  local backups
  backups=("$home"/.llm-wiki-skill-backups/llm-wiki-*)
  [[ -d "${backups[0]}" ]] || fail "expected backup directory"
  assert_file "${backups[0]}/local.txt"
  assert_contains "backed up llm-wiki" "$TMP_DIR/backup.out"
}

test_force_replaces_existing_skill() {
  local home="$TMP_DIR/force"
  local skill_dir="$home/skills/llm-wiki"
  mkdir -p "$skill_dir"
  echo "local edit" >"$skill_dir/local.txt"

  run_install "$home" --copy --force >"$TMP_DIR/force.out"

  assert_file "$home/skills/llm-wiki/SKILL.md"
  assert_file "$home/skills/llm-wiki/VERSION"
  assert_file "$home/skills/llm-wiki-backfill/SKILL.md"
  assert_no_path "$home/skills/llm-wiki/local.txt"
  assert_contains "version: 1.0.0" "$home/skills/llm-wiki/VERSION"
  assert_contains "engine_version: engine-v1.0.0" "$home/skills/llm-wiki/VERSION"
  assert_contains "replaced llm-wiki" "$TMP_DIR/force.out"
}

test_claude_client_installs_to_claude_home() {
  local home="$TMP_DIR/claude"
  run_install_claude "$home" --copy >"$TMP_DIR/claude.out"
  assert_file "$home/skills/llm-wiki/SKILL.md"
  assert_contains "Installed llm-wiki skills into:" "$TMP_DIR/claude.out"
}

test_cursor_client_installs_to_cursor_home() {
  local home="$TMP_DIR/cursor"
  run_install_cursor "$home" --copy >"$TMP_DIR/cursor.out"
  assert_file "$home/skills/llm-wiki/SKILL.md"
  assert_contains "Installed llm-wiki skills into:" "$TMP_DIR/cursor.out"
}

test_qoder_client_installs_to_qoder_home() {
  local home="$TMP_DIR/qoder"
  run_install_qoder "$home" --copy >"$TMP_DIR/qoder.out"
  assert_file "$home/skills/llm-wiki/SKILL.md"
  assert_contains "Installed llm-wiki skills into:" "$TMP_DIR/qoder.out"
}

test_default_refuses_existing_skill
test_dry_run_does_not_write
test_backup_preserves_existing_skill
test_force_replaces_existing_skill
test_claude_client_installs_to_claude_home
test_cursor_client_installs_to_cursor_home
test_qoder_client_installs_to_qoder_home
python3 "$ROOT_DIR/tests/build_wiki_test.py"

echo "install tests passed"
