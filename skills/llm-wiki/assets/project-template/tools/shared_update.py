from __future__ import annotations

import subprocess
from pathlib import Path


class GitResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


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
