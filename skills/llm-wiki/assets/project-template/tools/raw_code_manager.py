from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


METADATA_FILENAME = ".llm-wiki-codebase.yaml"


class RawCodeManagerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True, text=True)


def slugify_codebase_id(name: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-") or "codebase"


def derive_codebase_id(source: str) -> str:
    source_text = source.rstrip("/").rstrip(".git")
    return slugify_codebase_id(Path(source_text).name)


def managed_codebase_path(project: Path, codebase_id: str) -> Path:
    return project / "raw-code" / codebase_id


def resolve_repo_source(source: str) -> tuple[str, str]:
    source_path = Path(source)
    if source_path.exists():
        return str(source_path.resolve()), source_path.name
    return source, Path(source.rstrip("/")).name or "repo"


def probe_repo_access(source: str) -> tuple[bool, str | None]:
    source_path = Path(source)
    if source_path.exists():
        probe = run_git(["rev-parse", "--is-inside-work-tree"], cwd=source_path)
        if probe.returncode != 0:
            return False, "invalid_repo_source"
        return True, None
    probe = run_git(["ls-remote", source])
    if probe.returncode != 0:
        return False, "missing_access"
    return True, None


def write_codebase_metadata(managed_dir: Path, payload: dict[str, str]) -> Path:
    metadata = {
        "codebase_id": payload["codebase_id"],
        "managed": True,
        "repo_url": payload["repo_url"],
        "origin_ref": payload["origin_ref"],
        "default_branch": payload["default_branch"],
        "managed_path": payload["managed_path"],
        "created_by": "llm-wiki-add-code",
    }
    path = managed_dir / METADATA_FILENAME
    path.write_text(yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True), encoding="utf-8")
    ensure_metadata_ignored(managed_dir)
    return path


def ensure_metadata_ignored(managed_dir: Path) -> None:
    git_dir_result = run_git(["rev-parse", "--git-dir"], cwd=managed_dir)
    if git_dir_result.returncode != 0:
        return
    git_dir = Path(git_dir_result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = managed_dir / git_dir
    exclude = git_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    if METADATA_FILENAME not in {line.strip() for line in existing.splitlines()}:
        suffix = "" if existing.endswith("\n") or not existing else "\n"
        exclude.write_text(existing + suffix + METADATA_FILENAME + "\n", encoding="utf-8")


def read_codebase_metadata(managed_dir: Path) -> dict[str, object] | None:
    path = managed_dir / METADATA_FILENAME
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def detect_default_branch(repo_dir: Path) -> str:
    branch = run_git(["symbolic-ref", "--short", "HEAD"], cwd=repo_dir)
    if branch.returncode == 0 and branch.stdout.strip():
        return branch.stdout.strip()
    return "main"


def ensure_clean_target(path: Path) -> None:
    if not path.exists():
        return
    if any(path.iterdir()):
        raise RawCodeManagerError("dirty_target", f"managed raw-code target is not clean: {path}")


def clone_repo(source: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_git(["clone", source, str(target)])
    if result.returncode != 0:
        code = "missing_access" if "denied" in result.stderr.lower() or "auth" in result.stderr.lower() else "invalid_repo_source"
        raise RawCodeManagerError(code, result.stderr.strip() or f"failed to clone {source}")


def add_managed_codebase(project: Path, source: str, codebase_id: str | None = None) -> dict[str, str]:
    project = project.resolve()
    resolved_source, source_name = resolve_repo_source(source)
    resolved_codebase_id = codebase_id or derive_codebase_id(source_name)

    ok, error_code = probe_repo_access(resolved_source)
    if not ok:
        message = "repository access is missing" if error_code == "missing_access" else "source is not a readable git repository"
        raise RawCodeManagerError(error_code or "invalid_repo_source", message)

    target = managed_codebase_path(project, resolved_codebase_id)
    ensure_clean_target(target)
    if target.exists():
        shutil.rmtree(target)

    clone_repo(resolved_source, target)
    default_branch = detect_default_branch(target)
    metadata_path = write_codebase_metadata(
        target,
        {
            "codebase_id": resolved_codebase_id,
            "repo_url": resolved_source,
            "origin_ref": default_branch,
            "default_branch": default_branch,
            "managed_path": str(target),
        },
    )

    return {
        "codebase_id": resolved_codebase_id,
        "managed_path": str(target),
        "repo_url": resolved_source,
        "default_branch": default_branch,
        "metadata_path": str(metadata_path),
    }
