from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml


METADATA_FILENAME = ".llm-wiki-codebase.yaml"
CODE_SOURCES_PATH = Path("upstream/code-sources.json")
CODE_REPO_PERMISSION_PATTERNS = (
    "permission denied",
    "authentication failed",
    "repository not found",
    "403",
    "you are not allowed",
    "could not read from remote repository",
    "http basic: access denied",
)


class RawCodeManagerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True, text=True)


def read_code_sources_manifest(project: Path) -> dict[str, object]:
    path = project / CODE_SOURCES_PATH
    if not path.is_file():
        return {"version": 1, "sources": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RawCodeManagerError("code_source_config_failed", f"upstream/code-sources.json 不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise RawCodeManagerError("code_source_config_failed", "upstream/code-sources.json 必须是对象")
    return data


def write_code_sources_manifest(project: Path, manifest: dict[str, object]) -> Path:
    path = project / CODE_SOURCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def upsert_code_source(project: Path, entry: dict[str, object]) -> Path:
    manifest = read_code_sources_manifest(project)
    entry_id = entry.get("codebase_id")
    sources = [
        source
        for source in manifest.get("sources", [])
        if not isinstance(source, dict) or source.get("codebase_id") != entry_id
    ]
    sources.append(entry)
    updated = {"version": 1, "sources": sources}
    normalized = validate_code_sources_manifest(updated, shared_mode=False, project=project)
    return write_code_sources_manifest(project, {"version": 1, "sources": normalized})


def is_local_repo_url(value: str) -> bool:
    return value.startswith("/") or value.startswith("./") or value.startswith("../") or not ("://" in value or "@" in value)


def is_permission_error(message: str) -> bool:
    lowered = message.lower()
    return any(pattern in lowered for pattern in CODE_REPO_PERMISSION_PATTERNS)


def validate_code_sources_manifest(manifest: dict[str, object], shared_mode: bool, project: Path | None = None) -> list[dict[str, object]]:
    if manifest.get("version") != 1:
        raise RawCodeManagerError("code_source_config_failed", "upstream/code-sources.json 的 version 必须是 1")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise RawCodeManagerError("code_source_config_failed", "upstream/code-sources.json 的 sources 必须是列表")

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_targets: set[str] = set()
    for raw in sources:
        if not isinstance(raw, dict):
            raise RawCodeManagerError("code_source_config_failed", "每个代码证据源必须是对象")
        codebase_id = str(raw.get("codebase_id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", codebase_id) or codebase_id in {".", ".."}:
            raise RawCodeManagerError("code_source_config_failed", f"无效的 codebase_id：{codebase_id}")
        target_dir = str(raw.get("target_dir", ""))
        if codebase_id in seen_ids or target_dir in seen_targets:
            raise RawCodeManagerError("code_source_config_failed", "重复的 codebase_id 或 target_dir")
        if target_dir != f"raw-code/{codebase_id}":
            raise RawCodeManagerError("code_source_config_failed", f"target_dir 必须是 raw-code/{codebase_id}")
        seen_ids.add(codebase_id)
        seen_targets.add(target_dir)

        repo_url = str(raw.get("repo_url", ""))
        if not repo_url:
            raise RawCodeManagerError("code_source_config_failed", "缺少必填字段 repo_url")
        if is_local_repo_url(repo_url):
            if shared_mode:
                raise RawCodeManagerError("code_source_config_failed", "共享模式不允许使用本机 repo_url")
            if project is None:
                raise RawCodeManagerError("code_source_config_failed", "校验本机 repo_url 时必须提供项目目录")
            local_path = (project / repo_url).resolve() if not Path(repo_url).is_absolute() else Path(repo_url).resolve()
            if ".." in Path(repo_url).parts or not local_path.exists() or run_git(["rev-parse", "--is-inside-work-tree"], cwd=local_path).returncode != 0:
                raise RawCodeManagerError("code_source_config_failed", "本机 repo_url 必须指向已存在的 git 仓库")
        elif not (repo_url.startswith("git@") or repo_url.startswith("ssh://") or repo_url.startswith("http://") or repo_url.startswith("https://")):
            raise RawCodeManagerError("code_source_config_failed", f"不支持的 repo_url：{repo_url}")

        origin_ref = str(raw.get("origin_ref", ""))
        bad_ref = origin_ref.startswith(("origin/", "refs/")) or ".." in origin_ref or "//" in origin_ref or re.fullmatch(r"[0-9a-fA-F]{40}", origin_ref)
        if bad_ref or run_git(["check-ref-format", "--branch", origin_ref]).returncode != 0:
            raise RawCodeManagerError("code_source_config_failed", f"无效的 origin_ref：{origin_ref}")
        if not isinstance(raw.get("enabled"), bool) or raw.get("managed") is not True or raw.get("sync") != {"mode": "ff-only"}:
            raise RawCodeManagerError("code_source_config_failed", "enabled、managed 或 sync.mode 配置无效")

        default_branch = raw.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise RawCodeManagerError("code_source_config_failed", "缺少必填字段 default_branch")
        normalized.append(
            {
                "codebase_id": codebase_id,
                "repo_url": repo_url,
                "origin_ref": origin_ref,
                "default_branch": default_branch,
                "target_dir": target_dir,
                "enabled": raw["enabled"],
                "managed": True,
                "sync": {"mode": "ff-only"},
            }
        )
    return sorted(normalized, key=lambda source: str(source["codebase_id"]))


def slugify_codebase_id(name: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() or ch == "_" else "-" for ch in name.strip())
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


def remote_origin_url(source: str) -> str:
    source_path = Path(source)
    if not source_path.exists():
        return source
    result = run_git(["config", "--get", "remote.origin.url"], cwd=source_path)
    remote = result.stdout.strip()
    if result.returncode != 0 or not remote:
        raise RawCodeManagerError("code_source_config_failed", "代码仓库缺少远程 origin，无法写入可共享的代码证据源声明。请先配置远程仓库后重试。")
    return remote


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


def ensure_managed_checkout(project: Path, source: dict[str, object]) -> Path:
    target = project / str(source["target_dir"])
    if target.exists():
        return target
    try:
        clone_repo(str(source["repo_url"]), target)
    except RawCodeManagerError as exc:
        if is_permission_error(exc.message):
            raise RawCodeManagerError("evidence_failed", f"无法访问代码证据仓库。请先获取代码仓库读取权限后重试。详情：{exc.message}") from exc
        raise RawCodeManagerError("evidence_failed", f"代码证据仓库克隆失败。请检查仓库地址、网络或分支配置。详情：{exc.message}") from exc

    for args, message in [
        (["checkout", str(source["origin_ref"])], "无法切换到声明的代码分支。请检查代码仓库分支权限和 origin_ref 配置。"),
        (["branch", "--set-upstream-to", f"origin/{source['origin_ref']}"], "无法配置代码仓库上游分支。请检查代码仓库读取权限和分支配置。"),
    ]:
        result = run_git(args, cwd=target)
        if result.returncode != 0:
            detail = result.stderr.strip()
            suffix = f"详情：{detail}" if detail else ""
            raise RawCodeManagerError("evidence_failed", message + suffix)
    write_codebase_metadata(
        target,
        {
            "codebase_id": str(source["codebase_id"]),
            "repo_url": str(source["repo_url"]),
            "origin_ref": str(source["origin_ref"]),
            "default_branch": str(source["default_branch"]),
            "managed_path": str(source["target_dir"]),
            "managed": True,
            "created_by": "llm-wiki-add-code",
        },
    )
    return target


def validate_existing_checkout(project: Path, source: dict[str, object], target: Path) -> None:
    metadata = read_codebase_metadata(target)
    if not metadata:
        raise RawCodeManagerError("evidence_failed", f"代码证据 {target} 缺少 llm-wiki 管理元数据。")
    expected = {
        "codebase_id": str(source["codebase_id"]),
        "repo_url": str(source["repo_url"]),
        "origin_ref": str(source["origin_ref"]),
        "default_branch": str(source["default_branch"]),
        "managed_path": str(source["target_dir"]),
        "managed": True,
        "created_by": "llm-wiki-add-code",
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise RawCodeManagerError("evidence_failed", f"代码证据 {target} 的 {key} 元数据不匹配。")
    if run_git(["rev-parse", "--is-inside-work-tree"], cwd=target).returncode != 0:
        raise RawCodeManagerError("evidence_failed", f"代码证据 {target} 不是有效的 git checkout。")
    branch = run_git(["branch", "--show-current"], cwd=target)
    if branch.returncode != 0 or branch.stdout.strip() != str(source["origin_ref"]):
        raise RawCodeManagerError("evidence_failed", f"代码证据 {target} 当前分支不是 {source['origin_ref']}。")
    upstream = run_git(["rev-parse", "--abbrev-ref", "@{u}"], cwd=target)
    if upstream.returncode != 0 or upstream.stdout.strip() != f"origin/{source['origin_ref']}":
        raise RawCodeManagerError("evidence_failed", f"代码证据 {target} 的上游分支不是 origin/{source['origin_ref']}。")
    status = run_git(["status", "--porcelain"], cwd=target)
    if status.returncode != 0 or status.stdout.strip():
        raise RawCodeManagerError("evidence_failed", f"代码证据 {target} 有未提交改动，请先处理后重试。")


def tracked_or_existing_code_paths(project: Path) -> list[str]:
    result = run_git(["ls-files", "wiki/code"], cwd=project)
    if result.returncode == 0:
        return [path for path in result.stdout.splitlines() if path]
    code_root = project / "wiki" / "code"
    if not code_root.exists():
        return []
    return [str(path.relative_to(project)).replace("\\", "/") for path in code_root.rglob("*") if path.is_file()]


def codebase_ids_from_code_paths(paths: list[str], declared_ids: set[str]) -> set[str]:
    ids: set[str] = set()
    prefix = "wiki/code/codebases/"
    for path in paths:
        if path.startswith(prefix):
            remainder = path[len(prefix):]
            codebase_id = remainder.split("/", 1)[0]
            if codebase_id:
                ids.add(codebase_id)
            continue
        if not path.startswith("wiki/code/"):
            continue
        relative = path[len("wiki/code/"):]
        parts = [part for part in relative.split("/") if part]
        stem = Path(parts[-1]).stem if parts else ""
        candidates = set(parts)
        if stem:
            candidates.add(stem)
        matched = declared_ids & candidates
        if matched:
            ids.update(matched)
        elif stem:
            ids.add(stem)
    return ids


def validate_code_evidence_conflicts(project: Path, sources: list[dict[str, object]]) -> None:
    declared = {str(source["codebase_id"]): source for source in sources}
    enabled = {codebase_id for codebase_id, source in declared.items() if source["enabled"]}
    disabled = set(declared) - enabled
    code_paths = tracked_or_existing_code_paths(project)
    code_ids = codebase_ids_from_code_paths(code_paths, set(declared))

    for codebase_id in sorted(disabled & code_ids):
        raise RawCodeManagerError("evidence_failed", f"代码证据源 {codebase_id} 已禁用，但仍存在 wiki/code/** 代码证据。")

    raw_code = project / "raw-code"
    if raw_code.is_dir():
        for path in sorted(raw_code.iterdir()):
            if path.is_dir() and path.name not in declared:
                raise RawCodeManagerError("evidence_failed", f"发现未声明的代码证据缓存：raw-code/{path.name}。")

    for codebase_id in sorted(code_ids - set(declared)):
        if (raw_code / codebase_id).exists():
            raise RawCodeManagerError("evidence_failed", f"发现未声明的代码证据：{codebase_id}。")
        raise RawCodeManagerError("evidence_failed", f"缺少代码证据源：wiki/code/** 引用了 {codebase_id}，但 upstream/code-sources.json 未声明。")


def managed_code_sync_specs(project: Path, shared_mode: bool = False) -> list[dict[str, object]]:
    manifest = read_code_sources_manifest(project)
    sources = validate_code_sources_manifest(manifest, shared_mode=shared_mode, project=project)
    validate_code_evidence_conflicts(project, sources)
    specs: list[dict[str, object]] = []
    for source in sources:
        if not source["enabled"]:
            continue
        target = ensure_managed_checkout(project, source)
        validate_existing_checkout(project, source, target)
        specs.append({"label": str(source["codebase_id"]), "cwd": target, "command": ["git", "pull", "--ff-only"]})
    return specs


def add_managed_codebase(project: Path, source: str, codebase_id: str | None = None) -> dict[str, str]:
    project = project.resolve()
    resolved_source, source_name = resolve_repo_source(source)
    resolved_codebase_id = codebase_id or derive_codebase_id(source_name)

    ok, error_code = probe_repo_access(resolved_source)
    if not ok:
        message = "repository access is missing" if error_code == "missing_access" else "source is not a readable git repository"
        raise RawCodeManagerError(error_code or "invalid_repo_source", message)
    origin_url = remote_origin_url(resolved_source)

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
            "repo_url": origin_url,
            "origin_ref": default_branch,
            "default_branch": default_branch,
            "managed_path": f"raw-code/{resolved_codebase_id}",
        },
    )
    upsert_code_source(
        project,
        {
            "codebase_id": resolved_codebase_id,
            "repo_url": origin_url,
            "origin_ref": default_branch,
            "default_branch": default_branch,
            "target_dir": f"raw-code/{resolved_codebase_id}",
            "enabled": True,
            "managed": True,
            "sync": {"mode": "ff-only"},
        },
    )

    return {
        "codebase_id": resolved_codebase_id,
        "managed_path": f"raw-code/{resolved_codebase_id}",
        "repo_url": origin_url,
        "default_branch": default_branch,
        "metadata_path": str(metadata_path),
    }
