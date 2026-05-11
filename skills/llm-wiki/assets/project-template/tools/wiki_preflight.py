"""Evidence-layer checks for partial clones (built wiki without raw/ or raw-code/)."""

from __future__ import annotations

import json
from pathlib import Path


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def raw_dir_has_files(raw: Path) -> bool:
    if not raw.is_dir():
        return False
    for path in raw.rglob("*"):
        if path.is_file():
            return True
    return False


def wiki_expects_raw(project: Path) -> bool:
    sources_dir = project / "wiki" / "sources"
    if sources_dir.is_dir() and any(sources_dir.glob("*.md")):
        return True
    manifest = read_json(project / "staging" / "source-manifest.json", {})
    if isinstance(manifest, dict):
        sources = manifest.get("sources", [])
        if isinstance(sources, list) and len(sources) > 0:
            return True
    return False


def wiki_expects_raw_code(project: Path) -> bool:
    codebases_root = project / "wiki" / "code" / "codebases"
    if codebases_root.is_dir():
        for child in codebases_root.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                return True
    summary = read_json(project / "staging" / "code-graph" / "summary.json", {})
    if isinstance(summary, dict):
        codebases = summary.get("codebases", [])
        if isinstance(codebases, list) and len(codebases) > 0:
            return True
    return False


def raw_code_has_codebases(raw_code: Path) -> bool:
    if not raw_code.is_dir():
        return False
    for child in raw_code.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            return True
    return False


def raw_evidence_preflight_failed(project: Path) -> str | None:
    """Return a stderr message if raw/ must be present but is missing or empty."""
    if not wiki_expects_raw(project):
        return None
    raw_dir = project / "raw"
    if not raw_dir.is_dir():
        return (
            "missing_raw_evidence: This project already has built source pages (wiki/sources/ or "
            "staging/source-manifest.json), but raw/ is missing locally. "
            "Pull or restore raw/ (submodule, sparse checkout, LFS, or internal sync) before "
            "running build_wiki or update_wiki."
        )
    if not raw_dir_has_files(raw_dir):
        return (
            "empty_raw_evidence: raw/ exists but has no files while wiki/sources (or source-manifest) "
            "expects requirement evidence. Populate raw/ from your evidence remote, then rerun."
        )
    return None


def raw_code_evidence_preflight_failed(project: Path) -> str | None:
    """Return a stderr message if raw-code/ must be present but is missing or empty."""
    if not wiki_expects_raw_code(project):
        return None
    raw_code = project / "raw-code"
    if not raw_code.is_dir():
        return (
            "missing_raw_code_evidence: Code wiki artifacts exist (wiki/code/codebases/ or "
            "staging/code-graph/summary.json), but raw-code/ is missing locally. "
            "Pull or restore raw-code/ before scan_code, graphify, or trace refresh."
        )
    if not raw_code_has_codebases(raw_code):
        return (
            "empty_raw_code_evidence: raw-code/ exists but has no codebase directories while "
            "code wiki expects implementation evidence. Populate raw-code/<codebase_id>/, then rerun."
        )
    return None
