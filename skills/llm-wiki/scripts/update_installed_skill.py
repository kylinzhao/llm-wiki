#!/usr/bin/env python3
"""Update the installed LLM Wiki skill bundle from a local bundle checkout."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
DEFAULT_GIT_URL = "https://git.guazi-corp.com/c2b-fe/llm-wiki.git"
GITLAB_PAT_URL = "https://git.guazi-corp.com/profile/personal_access_tokens"
AUTH_ENV_FILE = Path(os.environ.get("LLM_WIKI_AUTH_ENV_FILE", "~/.llm-wiki/guazi-sso.env")).expanduser()
GITLAB_TOKEN_KEY = "GUAZI_GITLAB_TOKEN"


def is_bundle_root(path: Path) -> bool:
    return (path / "install.sh").is_file() and (path / "skills" / "llm-wiki").is_dir()


def parse_auth_env(path: Path | None = None) -> dict[str, str]:
    path = AUTH_ENV_FILE if path is None else path
    if not path.is_file():
        return {}
    result = subprocess.run(
        ["bash", "-lc", f"set -a; . {str(path)!r}; env"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == GITLAB_TOKEN_KEY:
            values[key] = value
    return values


def gitlab_token() -> str:
    return os.environ.get(GITLAB_TOKEN_KEY, "").strip() or parse_auth_env().get(GITLAB_TOKEN_KEY, "").strip()


def is_https_guazi_gitlab_command(command: list[str]) -> bool:
    for value in command:
        if "git.guazi-corp.com" not in value:
            continue
        parsed = urlparse(value)
        if parsed.scheme == "https" and parsed.netloc == "git.guazi-corp.com":
            return True
    return False


def git_askpass_env(token: str) -> tuple[dict[str, str], tempfile.TemporaryDirectory[str]]:
    temp_dir = tempfile.TemporaryDirectory(prefix="llm-wiki-git-askpass-")
    script = Path(temp_dir.name) / "askpass.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$1\" in\n"
        "  *Username*) printf '%s\\n' oauth2 ;;\n"
        "  *Password*) printf '%s\\n' \"$GUAZI_GITLAB_TOKEN\" ;;\n"
        "  *) printf '\\n' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    script.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    env = os.environ.copy()
    env.update({"GIT_ASKPASS": str(script), "GIT_TERMINAL_PROMPT": "0", "GUAZI_GITLAB_TOKEN": token})
    return env, temp_dir


def call(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> int:
    return subprocess.call(command, cwd=cwd, env=env)


def run(command: list[str], cwd: Path) -> int:
    print("+ " + " ".join(command))
    code = call(command, cwd)
    if code == 0 or not command or command[0] != "git" or not is_https_guazi_gitlab_command(command):
        return code
    token = gitlab_token()
    if not token:
        return code
    env, temp_dir = git_askpass_env(token)
    try:
        print("+ git ... (retry with GUAZI_GITLAB_TOKEN from local auth env)")
        return call(command, cwd, env=env)
    finally:
        temp_dir.cleanup()


def run_checked(command: list[str], cwd: Path) -> None:
    code = run(command, cwd)
    if code != 0:
        raise SystemExit(code)


def gitlab_auth_help(git_url: str) -> str:
    return (
        f"Could not clone llm-wiki skill source from {git_url}.\n"
        "If this is a private Guazi GitLab repository, create a GitLab token at:\n"
        f"  {GITLAB_PAT_URL}\n"
        "Required scope: read_repository.\n"
        "Then configure SSH Key / Git credentials, or run `bash ${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/init_auth_env.sh` "
        "and fill GUAZI_GITLAB_TOKEN before retrying. You can also pass --source /path/to/llm-wiki-skill "
        "to install from a local checkout."
    )


def default_bundle_root() -> Path | None:
    # Source checkout layout: <bundle>/skills/llm-wiki/scripts/this_file.py
    candidate = SCRIPT_PATH.parents[3]
    if is_bundle_root(candidate):
        return candidate

    for env_name in ("LLM_WIKI_SKILL_SOURCE", "LLM_WIKI_SKILL_BUNDLE", "LLM_WIKI_SKILL_CHECKOUT"):
        env_value = os.environ.get(env_name)
        if not env_value:
            continue
        candidate = Path(env_value).expanduser().resolve()
        if is_bundle_root(candidate):
            return candidate

    cwd = Path.cwd().resolve()
    for base in (cwd, *cwd.parents):
        for candidate in (base, base / "llm-wiki-skill"):
            if is_bundle_root(candidate):
                return candidate
    return None


def default_cache_dir(cache_dir: str | None) -> Path:
    if cache_dir:
        return Path(cache_dir).expanduser().resolve()
    env_value = os.environ.get("LLM_WIKI_SKILL_CACHE_DIR")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return Path("~/.cache/llm-wiki-skill").expanduser().resolve()


def default_git_url(git_url: str | None) -> str:
    if git_url:
        return git_url
    return os.environ.get("LLM_WIKI_SKILL_GIT_URL", DEFAULT_GIT_URL)


def git_origin_url(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=path,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def cached_git_bundle_root(git_url: str, cache_dir: str | None) -> Path:
    root = default_cache_dir(cache_dir) / "llm-wiki"
    if root.exists():
        if not is_git_worktree(root):
            raise SystemExit(f"Cached source exists but is not a git worktree: {root}")
        existing_url = git_origin_url(root)
        if existing_url and existing_url != git_url:
            raise SystemExit(
                f"Cached source origin mismatch: {root}\n"
                f"  existing: {existing_url}\n"
                f"  requested: {git_url}\n"
                "Pass --cache-dir to use a different cache, or remove the cached directory."
            )
        return root

    root.parent.mkdir(parents=True, exist_ok=True)
    code = run(["git", "clone", git_url, str(root)], root.parent)
    if code != 0:
        raise SystemExit(gitlab_auth_help(git_url))
    return root


def resolve_bundle_root(source: str | None, git_url: str | None, cache_dir: str | None, no_download: bool) -> Path:
    if source:
        root = Path(source).expanduser().resolve()
    else:
        root = default_bundle_root()
        if root is None:
            if no_download:
                raise SystemExit(
                    "Could not infer the llm-wiki skill bundle checkout from this installed skill. "
                    "Pass --source /path/to/llm-wiki-skill, or allow GitLab download."
                )
            root = cached_git_bundle_root(default_git_url(git_url), cache_dir)

    if not is_bundle_root(root):
        if not (root / "install.sh").is_file():
            raise SystemExit(f"Missing install.sh in bundle source: {root}")
        raise SystemExit(f"Missing skills/llm-wiki in bundle source: {root}")
    return root


def is_git_worktree(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def update_prd_review_max(bundle_root: Path, client: str, mode: str) -> int:
    script = bundle_root / "scripts" / "install_prd_review_max.sh"
    if not script.is_file():
        print("Warning: missing scripts/install_prd_review_max.sh; skipped prd-review-max update.")
        return 0

    command = [str(script), mode, "--upgrade", "--client", client]
    if mode == "--copy":
        command.append("--force")
    print("Updating upstream prd-review-max dependency...")
    return run(command, bundle_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        help="Local llm-wiki-skill bundle checkout. Overrides local discovery and GitLab download.",
    )
    parser.add_argument(
        "--git-url",
        help=f"Git URL used when no local source can be inferred. Defaults to $LLM_WIKI_SKILL_GIT_URL or {DEFAULT_GIT_URL}.",
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory for the downloaded GitLab checkout. Defaults to $LLM_WIKI_SKILL_CACHE_DIR or ~/.cache/llm-wiki-skill.",
    )
    parser.add_argument(
        "--client",
        default="auto",
        choices=["auto", "codex", "claude", "cursor", "qoder", "all"],
        help="Client skill directory to update. Defaults to auto.",
    )
    parser.add_argument("--mode", default="--copy", choices=["--copy", "--link"], help="Install mode.")
    parser.add_argument("--backup", action="store_true", help="Back up existing installed skills before updating.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing installed skills without backup.")
    parser.add_argument(
        "--backup-dir",
        help=(
            "Backup destination directory passed to install.sh --backup-dir. "
            "Defaults to $LLM_WIKI_SKILL_BACKUP_DIR or ~/.llm-wiki-skill-backups."
        ),
    )
    parser.add_argument("--no-pull", action="store_true", help="Do not git pull the source checkout before installing.")
    parser.add_argument("--no-download", action="store_true", help="Fail instead of cloning from GitLab when no local source is found.")
    parser.add_argument(
        "--skip-prd-review-max",
        action="store_true",
        help="Do not install or upgrade the upstream prd-review-max dependency after updating llm-wiki.",
    )
    args = parser.parse_args()

    if args.backup and args.force:
        raise SystemExit("Choose only one of --backup or --force.")

    bundle_root = resolve_bundle_root(args.source, args.git_url, args.cache_dir, args.no_download)
    if not args.no_pull and is_git_worktree(bundle_root):
        code = run(["git", "pull", "--ff-only"], bundle_root)
        if code != 0:
            return code

    install_command = ["./install.sh", args.mode, "--client", args.client]
    if args.backup:
        install_command.append("--backup")
    if args.force:
        install_command.append("--force")
    if args.backup_dir:
        install_command.extend(["--backup-dir", args.backup_dir])
    if not args.backup and not args.force:
        install_command.append("--backup")

    code = run(install_command, bundle_root)
    if code != 0:
        return code

    if not args.skip_prd_review_max:
        code = update_prd_review_max(bundle_root, args.client, args.mode)
        if code != 0:
            return code

    print(
        "Installed llm-wiki skill updated. Existing KB projects keep their project-local tools until refreshed."
    )
    print(
        "Run `llm-wiki maintain-all` / `$llm-wiki-maintain-all` to preview batch backfill/update for registered KBs."
    )
    if not args.skip_prd_review_max:
        print("Upstream prd-review-max was refreshed via scripts/install_prd_review_max.sh --upgrade.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
