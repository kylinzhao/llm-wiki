from __future__ import annotations

import subprocess
from pathlib import Path


class GitResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class PreflightResult:
    def __init__(self, status: str, message: str = ""):
        self.status = status
        self.message = message


PERMISSION_PATTERNS = (
    "permission denied",
    "authentication failed",
    "repository not found",
    "403",
    "you are not allowed",
    "could not read from remote repository",
    "http basic: access denied",
)


def classify_git_permission(stderr: str, operation: str) -> str:
    lowered = stderr.lower()
    if any(pattern in lowered for pattern in PERMISSION_PATTERNS):
        return "write_permission" if operation == "push" else "read_permission"
    return "none"


def run_git(args: list[str], cwd: Path) -> GitResult:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return GitResult(result.returncode, result.stdout, result.stderr)


def check_evidence_cache_hygiene(project: Path) -> PreflightResult:
    paths = ["raw/"]
    raw_code_needed = any(
        [
            (project / "raw-code").exists(),
            (project / "upstream" / "code-sources.json").exists(),
            (project / "wiki" / "code").exists(),
            (project / "staging" / "code-graph").exists(),
        ]
    )
    if raw_code_needed:
        paths.append("raw-code/")

    for path in paths:
        tracked = run_git(["ls-files", "--", path], cwd=project)
        if tracked.stdout.strip():
            first = tracked.stdout.splitlines()[0]
            return PreflightResult(
                "evidence_cache_tracked_failed",
                f"证据缓存 {first} 已被 git 跟踪。请先从仓库中移除 raw/raw-code 缓存文件。",
            )
        ignored = run_git(["check-ignore", "-q", path], cwd=project)
        if ignored.returncode != 0:
            return PreflightResult(
                "evidence_cache_ignore_failed",
                f"证据缓存 {path} 必须写入 .gitignore 后才能使用共享更新。",
            )
    return PreflightResult("ok")
