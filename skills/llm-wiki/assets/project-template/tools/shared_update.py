from __future__ import annotations

import fnmatch
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


class GitChange:
    def __init__(self, status: str, paths: tuple[str, ...]):
        self.status = status
        self.paths = paths


class PublishDecision:
    def __init__(self, status: str, paths: tuple[str, ...] = (), message: str = ""):
        self.status = status
        self.paths = paths
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
INCLUDE_PATTERNS = (
    "kb.manifest.yaml",
    "BUSINESS_CONTEXT.md",
    "upstream/**",
    "wiki/**",
    "docs/retrieval-playbook.md",
    "docs/build-and-maintenance.md",
    "docs/implementation-workflow.md",
    "docs/query-acceptance.md",
    "docs/*quality-audit*.md",
    "docs/*tooling*.md",
    "staging/update/latest.*",
    "staging/refinement-status.md",
    "staging/refinement-plan.json",
    "staging/source-manifest.json",
    "staging/code-graph/**",
    "staging/traceability/**",
    "graph/**",
    "index/**",
)
EXCLUDE_PATTERNS = (
    "raw/**",
    "raw-code/**",
    ".llm-wiki/**",
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.pfx",
    "*.cookie",
    "*.cookies",
    "*cookie*",
    "*token*",
    "*secret*",
    "*.log",
    ".venv/**",
    "venv/**",
    "node_modules/**",
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


def is_publish_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    parts = normalized.split("/")
    for pattern in EXCLUDE_PATTERNS:
        if "/" not in pattern and any(fnmatch.fnmatchcase(part, pattern) for part in parts):
            return False
        if "/" in pattern and fnmatch.fnmatchcase(normalized, pattern):
            return False
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in INCLUDE_PATTERNS)


def parse_porcelain_z(data: bytes) -> list[GitChange]:
    parts = [part.decode("utf-8") for part in data.split(b"\0") if part]
    changes: list[GitChange] = []
    index = 0
    while index < len(parts):
        item = parts[index]
        status = item[:2]
        first_path = item[3:]
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            index += 1
            changes.append(GitChange(status, (first_path, parts[index])))
        else:
            changes.append(GitChange(status, (first_path,)))
        index += 1
    return changes


def decide_publish_paths(changes: list[GitChange]) -> PublishDecision:
    allowed: list[str] = []
    unexpected: list[str] = []
    for change in changes:
        if all(is_publish_allowed(path) for path in change.paths):
            allowed.extend(change.paths)
        else:
            unexpected.extend(change.paths)
    if unexpected:
        return PublishDecision(
            "unexpected_local_changes",
            message="发现共享发布范围外的本地改动，请先处理后重试：" + ", ".join(unexpected),
        )
    return PublishDecision("ok", tuple(dict.fromkeys(allowed)))
