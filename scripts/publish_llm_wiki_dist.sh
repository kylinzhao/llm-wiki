#!/usr/bin/env bash
# Sync skills/llm-wiki into dist/llm-wiki-skill and build GrapeHub release zip.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT_DIR/skills/llm-wiki"
DST="$ROOT_DIR/dist/llm-wiki-skill"
ZIP="$ROOT_DIR/dist/llm-wiki-skill.zip"

if [[ ! -d "$SRC" ]]; then
  echo "Missing source skill: $SRC" >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/dist"

rsync -a --delete \
  --exclude='.DS_Store' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.venv/' \
  --exclude='manifest.json' \
  "$SRC/" "$DST/"

rm -f "$DST/mainfest.json"

for required in SKILL.md manifest.json VERSION; do
  if [[ ! -f "$DST/$required" ]]; then
    echo "Missing required release file: $DST/$required" >&2
    exit 1
  fi
done

rm -f "$ZIP"
(
  cd "$ROOT_DIR/dist"
  zip -rq "$ZIP" llm-wiki-skill -x "*.DS_Store" -x "*__pycache__*"
)

echo "Published dist package: $DST"
echo "Release zip: $ZIP"
echo "Required files:"
ls -la "$DST/SKILL.md" "$DST/manifest.json" "$DST/VERSION"
