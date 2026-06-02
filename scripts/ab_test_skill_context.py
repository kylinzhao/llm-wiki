#!/usr/bin/env python3
"""A/B: old llm-wiki-* vs llm-wiki-new-* protocol + dcn KB functional smoke."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DCN = Path("/Users/zhaoliang/guazi/work/multi-knowledge-base-space/dcn-llm-wiki")
OLD_PKG = Path.home() / ".cursor/skills/llm-wiki"
OLD_DOCTOR_ENTRY = Path.home() / ".cursor/skills/llm-wiki-doctor/SKILL.md"
OLD_QUERY_ENTRY = Path.home() / ".cursor/skills/llm-wiki-query/SKILL.md"
NEW_PKG = Path(__file__).resolve().parents[1] / "skills-new/llm-wiki-new"
NEW_DOCTOR_ENTRY = Path(__file__).resolve().parents[1] / "skills-new/llm-wiki-new-doctor/SKILL.md"
NEW_QUERY_ENTRY = Path(__file__).resolve().parents[1] / "skills-new/llm-wiki-new-query/SKILL.md"

# Per references/commands/doctor.md (shared between bundles; project-relative)
DOCTOR_KB_READS_FULL = [
    "BUSINESS_CONTEXT.md",
    "wiki/index.md",
    "wiki/overview.md",
    "docs/retrieval-playbook.md",
    "docs/build-and-maintenance.md",
    "staging/refinement-status.md",
    "staging/health/latest.json",
    "graph/summary.md",
    "wiki/code/index.md",
    "wiki/code/traceability/index.md",
    "docs/query-acceptance.md",
    "docs/gplus-quality-audit.md",
]

# Practical doctor pass: JSON/summary first; skip 160KB+ refinement-status body unless needed
DOCTOR_KB_READS_LITE = [
    "BUSINESS_CONTEXT.md",
    "wiki/overview.md",
    "staging/health/latest.json",
    "staging/doctor/latest.json",
    "graph/summary.md",
]

QUERY_KB_READS = [
    "BUSINESS_CONTEXT.md",
    "wiki/index.md",
    "wiki/concepts/dcn-product-overview.md",
]

QUERY_PLUS_EXTRA = [
    "wiki/code/capabilities/source-list-detail.md",
    "references/query-logic.md",  # new only in skill; old also says read query-logic in commands
]


def read_bytes(paths: list[Path]) -> tuple[int, list[str], list[str]]:
    total = 0
    ok: list[str] = []
    missing: list[str] = []
    for p in paths:
        if not p.exists():
            missing.append(str(p))
            continue
        total += p.stat().st_size
        ok.append(str(p))
    return total, ok, missing


def est_tokens(byte_count: int) -> int:
    # Rough EN/CN mix for markdown
    return byte_count // 3


def run_dcn_tool(script: str) -> tuple[int, str]:
    if not script.endswith(".py"):
        script = f"{script}.py"
    proc = subprocess.run(
        ["uv", "run", "python", f"tools/{script}"],
        cwd=DCN,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip().splitlines()[-3:] if out.strip() else []


def doctor_summary_from_json() -> dict:
    p = DCN / "staging/doctor/latest.json"
    if not p.exists():
        return {"error": "missing latest.json"}
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    print("=" * 60)
    print("A/B: Skill protocol load (what agent is instructed to read first)")
    print("=" * 60)

    old_doctor_protocol = [
        OLD_DOCTOR_ENTRY,
        OLD_PKG / "SKILL.md",
        OLD_PKG / "references/commands.md",
    ]
    new_doctor_protocol = [
        NEW_DOCTOR_ENTRY,
        NEW_PKG / "references/core-rules.md",
        NEW_PKG / "references/commands/_shared.md",
        NEW_PKG / "references/commands/doctor.md",
    ]

    old_query_protocol = [
        OLD_QUERY_ENTRY,
        OLD_PKG / "SKILL.md",
        OLD_PKG / "references/commands.md",
    ]
    new_query_protocol = [
        NEW_QUERY_ENTRY,
        NEW_PKG / "references/core-rules.md",
        NEW_PKG / "references/commands/_shared.md",
        NEW_PKG / "references/commands/query.md",
    ]

    scenarios = [
        ("doctor (protocol + full KB list in doctor.md)", old_doctor_protocol, new_doctor_protocol, DOCTOR_KB_READS_FULL),
        ("doctor (protocol + lite KB)", old_doctor_protocol, new_doctor_protocol, DOCTOR_KB_READS_LITE),
        ("query", old_query_protocol, new_query_protocol, QUERY_KB_READS),
    ]

    results = []
    for name, old_paths, new_paths, kb_rels in scenarios:
        ob, _, om = read_bytes(old_paths)
        nb, _, nm = read_bytes(new_paths)
        kb_paths = [DCN / r for r in kb_rels]
        kb_b, _, kbm = read_bytes(kb_paths)
        # query-plus extra for new only in entry; old query also has query-logic in commands section
        ql = NEW_PKG / "references/query-logic.md"
        old_ql = OLD_PKG / "references/query-logic.md"
        if name == "query":
            ob += old_ql.stat().st_size if old_ql.exists() else 0
            nb += ql.stat().st_size if ql.exists() else 0

        old_total = ob + kb_b
        new_total = nb + kb_b
        row = {
            "scenario": name,
            "old_protocol_b": ob,
            "new_protocol_b": nb,
            "kb_b": kb_b,
            "old_total_b": old_total,
            "new_total_b": new_total,
            "saved_b": old_total - new_total,
            "saved_pct": round(100 * (old_total - new_total) / old_total, 1) if old_total else 0,
            "old_missing": om + kbm,
            "new_missing": nm + kbm,
        }
        results.append(row)
        print(f"\n--- {name} ---")
        print(f"  OLD protocol only:     {ob:>8} B  (~{est_tokens(ob):>6} tok)")
        print(f"  NEW protocol only:     {nb:>8} B  (~{est_tokens(nb):>6} tok)")
        print(f"  KB evidence (both):    {kb_b:>8} B  (~{est_tokens(kb_b):>6} tok)")
        print(f"  OLD total instructed:  {old_total:>8} B  (~{est_tokens(old_total):>6} tok)")
        print(f"  NEW total instructed:  {new_total:>8} B  (~{est_tokens(new_total):>6} tok)")
        print(f"  Savings:               {row['saved_b']:>8} B  ({row['saved_pct']}%)")
        if om or nm:
            print(f"  Missing protocol: old={om} new={nm}")

    print("\n" + "=" * 60)
    print("Functional: deterministic tools on dcn KB (same for both bundles)")
    print("=" * 60)
    for tool in ("doctor.py", "health.py"):
        code, tail = run_dcn_tool(tool.replace(".py", ""))
        print(f"  {tool}: exit={code}  {' | '.join(tail)}")

    print("\n" + "=" * 60)
    print("Functional: doctor JSON verdict (post tools/doctor.py)")
    print("=" * 60)
    d = doctor_summary_from_json()
    print(f"  summary: {d.get('summary', d.get('error'))}")
    print(f"  maxSeverity: {d.get('maxSeverity')}  p0: {d.get('p0Count')}")
    findings = d.get("findings") or []
    print(f"  findings: {len(findings)}")
    for f in findings[:5]:
        print(f"    - [{f.get('severity')}] {f.get('title')}")

    print("\n" + "=" * 60)
    print("Functional: query smoke (evidence must answer fixed questions)")
    print("=" * 60)
    bc = (DCN / "BUSINESS_CONTEXT.md").read_text(encoding="utf-8")
    cap = (DCN / "wiki/code/capabilities/source-list-detail.md").read_text(encoding="utf-8")
    q1_ok = "DCN" in bc and "同行找车" in bc and "源头找车" in bc
    q2_ok = "/dcncenter/list/sourcelist" in cap and "DCNList" in cap
    print(f"  Q1 business (DCN=同行找车/源头找车): {'PASS' if q1_ok else 'FAIL'}")
    print(f"  Q2 impl (sourcelist + DCNList):       {'PASS' if q2_ok else 'FAIL'}")

    print("\n" + "=" * 60)
    print("Compliance: do entries still mandate full main SKILL.md?")
    print("=" * 60)
    old_doc = OLD_DOCTOR_ENTRY.read_text(encoding="utf-8")
    new_doc = NEW_DOCTOR_ENTRY.read_text(encoding="utf-8")
    old_bad = "SKILL.md" in old_doc and "包根目录" in old_doc
    new_bad = "不要" not in new_doc and "完整 `SKILL.md`" in new_doc
    new_good = "不要" in new_doc and "core-rules" in new_doc
    print(f"  OLD entry requires main SKILL.md: {old_bad}")
    print(f"  NEW entry forbids full SKILL:     {new_good and not new_bad}")

    # Write machine-readable report
    report = {
        "dcn_kb": str(DCN),
        "scenarios": results,
        "doctor": d,
        "query_smoke": {"q1_business": q1_ok, "q2_impl": q2_ok},
        "compliance": {"old_requires_main_skill": old_bad, "new_forbids_main_skill": new_good},
    }
    out = Path(__file__).resolve().parents[1] / "staging/ab-test-skill-context.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
