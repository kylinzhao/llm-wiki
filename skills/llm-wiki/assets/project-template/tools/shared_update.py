from __future__ import annotations

import fnmatch
import os
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


class PublishResult:
    def __init__(self, status: str, message: str = ""):
        self.status = status
        self.message = message


class GitBytesResult:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class GitChange:
    def __init__(self, status: str, paths: tuple[str, ...]):
        self.status = status
        self.paths = paths


class PublishDecision:
    def __init__(self, status: str, paths: tuple[str, ...] = (), message: str = ""):
        self.status = status
        self.paths = paths
        self.message = message


SOFT_VALIDATION_STATUSES = {
    "ok",
    "refinement_pending",
    "usable_with_gaps",
    "semantic_gaps",
}


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
    "staging/**",
    "graph/**",
    "index/**",
    "tools/**",
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


def run_git_bytes(args: list[str], cwd: Path) -> GitBytesResult:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    return GitBytesResult(result.returncode, result.stdout, result.stderr.decode("utf-8", errors="replace"))


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


def is_git_repo(project: Path) -> bool:
    return run_git(["rev-parse", "--is-inside-work-tree"], cwd=project).returncode == 0


def git_status_dirty(project: Path) -> bool:
    result = run_git(["status", "--porcelain"], cwd=project)
    return result.returncode != 0 or bool(result.stdout.strip())


def current_upstream(project: Path, git_runner=run_git) -> tuple[str | None, GitResult]:
    result = git_runner(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], project)
    upstream = result.stdout.strip()
    return (upstream if result.returncode == 0 and upstream else None), result


def read_divergence(project: Path, upstream: str) -> tuple[int, int]:
    result = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], cwd=project)
    if result.returncode != 0:
        return 0, 0
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return 0, 0
    return int(parts[0]), int(parts[1])


def diff_touched_paths(project: Path, upstream: str) -> list[str] | None:
    diff = run_git(["diff", "--name-status", "-z", f"{upstream}..HEAD"], cwd=project)
    if diff.returncode != 0:
        return None
    parts = [part for part in diff.stdout.split("\0") if part]
    paths: list[str] = []
    index = 0
    while index < len(parts):
        status = parts[index]
        index += 1
        if status.startswith(("R", "C")):
            if index + 1 >= len(parts):
                return None
            paths.extend([parts[index], parts[index + 1]])
            index += 2
        else:
            if index >= len(parts):
                return None
            paths.append(parts[index])
            index += 1
    return paths


def recognized_update_commits_only(project: Path, upstream: str) -> bool:
    subject = f"Update {project.name} knowledge base"
    commit_list = run_git(["rev-list", f"{upstream}..HEAD"], cwd=project)
    if commit_list.returncode != 0:
        return False
    commits = [line for line in commit_list.stdout.splitlines() if line]
    if not commits:
        return False
    for commit in commits:
        message = run_git(["show", "-s", "--format=%B", commit], cwd=project)
        if message.returncode != 0:
            return False
        lines = message.stdout.splitlines()
        if not lines or lines[0].strip() != subject:
            return False
        body = "\n".join(lines[1:])
        if "Actor: local-skill" not in body and "Actor: gateway" not in body:
            return False
    paths = diff_touched_paths(project, upstream)
    if paths is None:
        return False
    return bool(paths) and all(is_publish_allowed(path) for path in paths)


def local_mode_offer(message: str) -> PreflightResult:
    return PreflightResult("offer_local_mode", message + " 是否切换到本机模式继续？")


def local_preflight(project: Path) -> PreflightResult:
    if not is_git_repo(project):
        return PreflightResult("ok", "当前目录不是 git 仓库，将以本机模式继续。")
    hygiene = check_evidence_cache_hygiene(project)
    if hygiene.status != "ok":
        return hygiene
    if git_status_dirty(project):
        return PreflightResult("dirty_worktree_blocked", "本机模式要求 git 工作区干净，请先提交、暂存或清理本地改动。")
    return PreflightResult("ok")


def shared_preflight(
    project: Path,
    no_auto_raw_sync: bool,
    interactive: bool,
    git_runner=run_git,
    divergence_reader=read_divergence,
    ahead_is_recognized=recognized_update_commits_only,
) -> PreflightResult:
    if no_auto_raw_sync:
        return PreflightResult("shared_sync_failed", "共享模式不能跳过 raw/raw-code 同步。请取消跳过参数，或显式使用本机模式。")

    if not is_git_repo(project):
        message = "共享模式需要 KB 目录是 git 仓库。"
        return local_mode_offer(message) if interactive else PreflightResult("shared_sync_failed", message)

    hygiene = check_evidence_cache_hygiene(project)
    if hygiene.status != "ok":
        return hygiene

    upstream, upstream_result = current_upstream(project)
    if not upstream:
        detail = upstream_result.stderr.strip()
        message = "共享模式需要配置 KB 仓库上游分支。"
        if classify_git_permission(detail, "pull") == "read_permission":
            message = "无法读取 KB 仓库上游。请先获取 KB 仓库权限（读取权限）后重试。"
        return local_mode_offer(message) if interactive else PreflightResult("shared_sync_failed", message)

    if git_status_dirty(project):
        return PreflightResult("dirty_worktree_blocked", "共享模式要求 git 工作区干净，请先提交、暂存或清理本地改动。")

    fetch = git_runner(["fetch", "--prune", "origin"], project)
    if fetch.returncode != 0:
        detail = fetch.stderr.strip()
        if classify_git_permission(detail, "pull") == "read_permission":
            message = "无法读取 KB 仓库。请先获取 KB 仓库权限（读取权限）后重试。详情：" + detail
        else:
            message = "共享 KB 同步失败。详情：" + detail
        return local_mode_offer(message) if interactive else PreflightResult("shared_sync_failed", message)

    ahead, behind = divergence_reader(project, upstream)
    if ahead and behind:
        message = "共享 KB 分支已分叉，无法自动同步。"
        return local_mode_offer(message) if interactive else PreflightResult("shared_sync_failed", message)

    if behind:
        pull = git_runner(["pull", "--ff-only"], project)
        if pull.returncode != 0:
            detail = pull.stderr.strip()
            if classify_git_permission(detail, "pull") == "read_permission":
                message = "无法读取 KB 仓库。请先获取 KB 仓库权限（读取权限）后重试。详情：" + detail
            else:
                message = "共享 KB pull 失败。详情：" + detail
            return local_mode_offer(message) if interactive else PreflightResult("shared_sync_failed", message)

    if ahead:
        if not ahead_is_recognized(project, upstream):
            return PreflightResult("ahead_unrecognized_commits", "存在尚未发布且无法识别的本地提交，请人工处理后重试。")
        push = git_runner(["push"], project)
        if push.returncode != 0:
            detail = push.stderr.strip()
            if classify_git_permission(detail, "push") == "write_permission":
                return PreflightResult("unpublished_local_baseline", "无法发布共享 KB 基线。请先获取 KB 仓库写入权限后重试。详情：" + detail)
            return PreflightResult("unpublished_local_baseline", "本地共享 KB 基线尚未发布，自动 push 失败。请检查远端状态后重试。详情：" + detail)
        fetch_after_push = git_runner(["fetch", "--prune", "origin"], project)
        if fetch_after_push.returncode != 0:
            detail = fetch_after_push.stderr.strip()
            return PreflightResult("shared_sync_failed", "共享 KB 发布后重新同步失败。详情：" + detail)
        ahead, behind = divergence_reader(project, upstream)
        if ahead and behind:
            return PreflightResult("shared_sync_failed", "共享 KB 发布后仍然分叉，请人工处理后重试。")
        if ahead:
            return PreflightResult("unpublished_local_baseline", "本地共享 KB 基线仍未发布，请人工检查远端状态。")
        if behind:
            pull = git_runner(["pull", "--ff-only"], project)
            if pull.returncode != 0:
                detail = pull.stderr.strip()
                if classify_git_permission(detail, "pull") == "read_permission":
                    return PreflightResult("shared_sync_failed", "无法读取 KB 仓库。请先获取 KB 仓库权限（读取权限）后重试。详情：" + detail)
                return PreflightResult("shared_sync_failed", "共享 KB pull 失败。详情：" + detail)

    return PreflightResult("ok")


def publish_shared_baseline(project: Path, actor: str = "local-skill", git_runner=run_git, status_runner=run_git_bytes) -> PublishResult:
    status = status_runner(["status", "--porcelain=v1", "-z"], cwd=project)
    if status.returncode != 0:
        return PublishResult("shared_sync_failed", "读取 git 状态失败，未发布共享 KB。请检查本地仓库状态后重试。")
    changes = parse_porcelain_z(status.stdout)
    decision = decide_publish_paths(changes)
    if decision.status != "ok":
        return PublishResult(decision.status, decision.message)
    if not decision.paths:
        return PublishResult("no_changes", "共享 KB 没有需要发布的变更。")

    add = git_runner(["add", "--", *decision.paths], cwd=project)
    if add.returncode != 0:
        return PublishResult("stage_failed_dirty_result", "暂存共享 KB 变更失败，未发布任何文件。请检查本地工作区状态后重试。")

    commit = git_runner(
        [
            "commit",
            "-m",
            f"Update {project.name} knowledge base",
            "-m",
            f"Actor: {actor}",
        ],
        cwd=project,
    )
    if commit.returncode != 0:
        return PublishResult("commit_failed_dirty_result", "提交共享 KB 失败，本地工作区可能保留了已暂存变更。请先处理后重试。")

    push = git_runner(["push"], cwd=project)
    if push.returncode != 0:
        if classify_git_permission(push.stderr, "push") == "write_permission":
            return PublishResult("unpublished_local_baseline", "共享 KB 已在本地提交，但推送失败：缺少写入权限。请先获取 KB 仓库权限后执行 git push。")
        return PublishResult("unpublished_local_baseline", "共享 KB 已在本地提交，但推送失败。请检查网络、仓库地址或 Git 凭证后重试。")

    return PublishResult("published", "共享 KB 已发布。")


def resolve_update_mode(local_flag: bool, shared_flag: bool, env: dict[str, str] | None = None) -> str:
    values = os.environ if env is None else env
    if local_flag or values.get("LLM_WIKI_UPDATE_MODE") == "local":
        return "local"
    return "shared"


def raw_sync_skipped(no_auto_raw_sync: bool, env: dict[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return no_auto_raw_sync or values.get("LLM_WIKI_NO_AUTO_RAW_SYNC") == "1"


def begin_update(
    project: Path,
    mode: str,
    no_auto_raw_sync: bool,
    interactive: bool,
    update_callback,
    env: dict[str, str] | None = None,
) -> PreflightResult:
    skipped = raw_sync_skipped(no_auto_raw_sync, env)
    preflight = shared_preflight(project, skipped, interactive) if mode == "shared" else local_preflight(project)
    if preflight.status != "ok":
        return preflight
    code = update_callback()
    if code == 0:
        return PreflightResult("ok")
    return PreflightResult("validation_failed", "确定性更新失败，未发布共享 KB。")


def accept_local_fallback(project: Path, local_preflight_fn=local_preflight, update_callback=None) -> PreflightResult:
    preflight = local_preflight_fn(project)
    if preflight.status != "ok":
        return preflight
    code = update_callback() if update_callback else 0
    return PreflightResult("ok" if code == 0 else "validation_failed")


def complete_shared_update(project: Path, semantic_validation, publisher=publish_shared_baseline) -> PublishResult:
    validation = semantic_validation()
    if validation.status not in SOFT_VALIDATION_STATUSES:
        return validation
    return publisher(project)
