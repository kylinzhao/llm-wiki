from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


AUTH_ENV_FILE = Path(os.environ.get("LLM_WIKI_AUTH_ENV_FILE", "~/.llm-wiki/guazi-sso.env")).expanduser()
GITLAB_PAT_URL = "https://git.guazi-corp.com/profile/personal_access_tokens"
GITLAB_TOKEN_KEY = "GUAZI_GITLAB_TOKEN"


class GitCommandResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def parse_env_file(path: Path | None = None) -> dict[str, str]:
    path = AUTH_ENV_FILE if path is None else path
    if not path.is_file():
        return {}
    command = f"set -a; . {str(path)!r}; env"
    result = subprocess.run(["bash", "-lc", command], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {}
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {GITLAB_TOKEN_KEY}:
            values[key] = value
    return values


def gitlab_token(env: dict[str, str] | None = None) -> str:
    values = os.environ if env is None else env
    token = values.get(GITLAB_TOKEN_KEY, "").strip()
    if token:
        return token
    return parse_env_file().get(GITLAB_TOKEN_KEY, "").strip()


def is_https_gitlab_url(args: list[str]) -> bool:
    for arg in args:
        if "git.guazi-corp.com" not in arg:
            continue
        parsed = urlparse(arg)
        if parsed.scheme == "https" and parsed.netloc == "git.guazi-corp.com":
            return True
    return False


def permission_message(operation: str = "git") -> str:
    scope = "read_repository"
    permission = "读取权限"
    if operation == "push":
        permission = "写入权限"
        scope += "；如需发布共享 KB，请同时勾选 write_repository"
    return (
        f"缺少{permission}或 GitLab 鉴权失败。请先获取 KB 仓库权限或代码仓库权限，并确认本机 SSH Key / Git 凭据可访问 git.guazi-corp.com；"
        f"或到 {GITLAB_PAT_URL} 申请 Personal Access Token（scope: {scope}），"
        "再运行 `bash tools/confluence_sync/init_auth_env.sh` 填入 GitLab token 后重试。"
    )


def _run_git(args: list[str], cwd: Path | None, env: dict[str, str] | None = None) -> GitCommandResult:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    return GitCommandResult(result.returncode, result.stdout, result.stderr)


def _askpass_env(token: str) -> tuple[dict[str, str], tempfile.TemporaryDirectory[str]]:
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
    env.update(
        {
            "GIT_ASKPASS": str(script),
            "GUAZI_GITLAB_TOKEN": token,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env, temp_dir


def run_git(args: list[str], cwd: Path | None = None, *, operation: str = "git") -> GitCommandResult:
    first = _run_git(args, cwd)
    if first.returncode == 0 or not is_https_gitlab_url(args):
        return first
    token = gitlab_token()
    if not token:
        return first
    env, temp_dir = _askpass_env(token)
    try:
        second = _run_git(args, cwd, env=env)
    finally:
        temp_dir.cleanup()
    if second.returncode != 0 and not second.stderr.strip():
        second.stderr = permission_message(operation)
    return second
