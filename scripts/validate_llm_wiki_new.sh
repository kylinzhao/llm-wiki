#!/usr/bin/env bash
# Validate llm-wiki-new bundle: unit tests, context budget, and dcn KB doctor run.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DCN_KB="${LLM_WIKI_NEW_VALIDATION_KB:-/Users/zhaoliang/guazi/work/multi-knowledge-base-space/dcn-llm-wiki}"
SKILLS_NEW="$ROOT_DIR/skills-new"
SKILLS_CLIENT="${LLM_WIKI_NEW_CLIENT:-cursor}"
case "$SKILLS_CLIENT" in
  claude) INSTALL_SKILLS="${CLAUDE_HOME:-$HOME/.claude}/skills" ;;
  cursor) INSTALL_SKILLS="${CURSOR_HOME:-$HOME/.cursor}/skills" ;;
  codex)  INSTALL_SKILLS="${CODEX_HOME:-$HOME/.codex}/skills" ;;
  *)      INSTALL_SKILLS="${CURSOR_HOME:-$HOME/.cursor}/skills" ;;
esac

echo "== 1. Repo tests =="
cd "$ROOT_DIR"
python3 -m pytest tests/test_query_citation_policy.py tests/test_release_version.py -q

echo ""
echo "== 2. Sub-entry context budget (llm-wiki-new-doctor) =="
python3 <<PY
from pathlib import Path

root = Path("$ROOT_DIR") / "skills-new"
pkg = root / "llm-wiki-new"
entry = root / "llm-wiki-new-doctor" / "SKILL.md"
files = [
    entry,
    pkg / "references/core-rules.md",
    pkg / "references/commands/_shared.md",
    pkg / "references/commands/doctor.md",
]
total = 0
for f in files:
    size = f.stat().st_size
    total += size
    print(f"  {size:6d}  {f.relative_to(root)}")
print(f"  TOTAL {total} bytes (~{total // 3} tokens est.)")
text = entry.read_text(encoding="utf-8")
if "完整 \`SKILL.md\`" in text and "不要" not in text:
    raise SystemExit("doctor entry still mandates full SKILL.md")
print("  OK: sub-entry does not require full main SKILL.md")
PY

echo ""
echo "== 3. Installed skill names ($SKILLS_CLIENT) =="
for name in llm-wiki-new llm-wiki-new-doctor llm-wiki-new-update; do
  if [[ -e "$INSTALL_SKILLS/$name" ]]; then
    echo "  OK $INSTALL_SKILLS/$name"
  else
    echo "  MISSING $name — run ./install-llm-wiki-new.sh --link --client $SKILLS_CLIENT" >&2
    exit 1
  fi
done
if [[ -e "$INSTALL_SKILLS/llm-wiki-doctor" ]]; then
  echo "  OK existing llm-wiki-doctor present at $INSTALL_SKILLS"
fi

echo ""
echo "== 4. dcn KB deterministic doctor =="
if [[ ! -d "$DCN_KB" ]]; then
  echo "DCN KB not found: $DCN_KB" >&2
  exit 1
fi
cd "$DCN_KB"
if [[ -f uv.lock ]]; then
  uv run python tools/doctor.py
else
  python3 tools/doctor.py
fi

echo ""
echo "== 5. dcn KB health snapshot =="
python3 -c "
import json
from pathlib import Path
p = Path('staging/health/latest.json')
if p.exists():
    d = json.loads(p.read_text())
    print('  status:', d.get('status'))
    print('  evidence_gaps:', len(d.get('evidence_gaps') or []))
else:
    print('  (no staging/health/latest.json)')
"

echo ""
echo "validate_llm_wiki_new: PASS"
