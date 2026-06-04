#!/usr/bin/env bash
set -euo pipefail

AUTH_ENV_FILE="${LLM_WIKI_AUTH_ENV_FILE:-$HOME/.llm-wiki/guazi-sso.env}"
AUTH_DIR="$(dirname "$AUTH_ENV_FILE")"

quote_env_value() {
  printf '%q' "$1"
}

load_existing_auth_env() {
  if [[ -f "$AUTH_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$AUTH_ENV_FILE"
  fi
}

append_env_value() {
  local key="$1"
  local value="$2"
  if [[ -n "$value" ]]; then
    printf '%s=%s\n' "$key" "$(quote_env_value "$value")" >> "$AUTH_ENV_FILE"
  fi
}

gitlab_ssh_accessible() {
  local output
  output="$(ssh -o BatchMode=yes -o ConnectTimeout=3 -T git@git.guazi-corp.com </dev/null 2>&1 || true)"
  case "$output" in
    *"successfully authenticated"*|*"Welcome"*|*"authenticated"*) return 0 ;;
  esac
  return 1
}

gitlab_credential_accessible() {
  local output
  local key
  local value
  output="$(printf 'protocol=https\nhost=git.guazi-corp.com\n\n' | git credential fill 2>/dev/null || true)"
  while IFS='=' read -r key value; do
    if [[ "$key" == "password" && -n "$value" ]]; then
      return 0
    fi
  done <<< "$output"
  return 1
}

gitlab_auth_available() {
  gitlab_ssh_accessible || gitlab_credential_accessible
}

read_gitlab_token() {
  echo
  if [[ -n "${GUAZI_GITLAB_TOKEN:-}" ]]; then
    echo "已检测到本机已有 GitLab 令牌，跳过输入。"
    return 0
  fi
  if gitlab_auth_available; then
    echo "GitLab 令牌可选：已检测到本机 SSH Key / Git credential 可访问 git.guazi-corp.com，可直接回车跳过。"
  else
    echo "GitLab 令牌可选：未检测到本机可复用的 GitLab 鉴权，后续访问私有仓库时可能需要补充。"
  fi
  echo "如需创建 GitLab 令牌，请打开：https://git.guazi-corp.com/profile/personal_access_tokens"
  read -r -s -p "请输入 GitLab 令牌（输入时不会显示，没有可直接回车）: " GUAZI_GITLAB_TOKEN
  echo
}

read_jira_token() {
  echo
  if [[ -n "${JIRA_TOKEN:-}" ]]; then
    echo "已检测到本机已有 Jira 令牌，跳过输入。"
    return 0
  fi
  echo "Jira 令牌可选；没有可直接回车。"
  echo "如需创建 Jira 令牌，请打开 Jira 个人设置页：https://jira.guazi-corp.com/secure/ViewProfile.jspa"
  read -r -s -p "请输入 Jira 令牌（输入时不会显示，没有可直接回车）: " JIRA_TOKEN
  echo
}

load_existing_auth_env

read -r -p "Choose auth mode [sso/cookie] (default: sso): " AUTH_MODE
AUTH_MODE="${AUTH_MODE:-sso}"

mkdir -p "$AUTH_DIR"
chmod 700 "$AUTH_DIR"
umask 077

cat > "$AUTH_ENV_FILE" <<'EOF'
# Local llm-wiki auth values. Do not commit.
# Loaded by llm-wiki Cwiki/Jira/Git helper tools on this computer.
EOF

case "$AUTH_MODE" in
  cookie)
    if [[ -z "${COOKIE_HEADER:-}" ]]; then
      read -r -s -p "Paste full COOKIE_HEADER（输入时不会显示）: " COOKIE_HEADER
      echo
    fi
    read_jira_token
    read_gitlab_token
    if [[ -z "${COOKIE_HEADER:-}" ]]; then
      echo "COOKIE_HEADER 不能为空；未写入鉴权文件。" >&2
      exit 2
    fi
    append_env_value "COOKIE_HEADER" "$COOKIE_HEADER"
    append_env_value "JIRA_TOKEN" "$JIRA_TOKEN"
    append_env_value "GUAZI_GITLAB_TOKEN" "$GUAZI_GITLAB_TOKEN"
    ;;
  sso)
    if [[ -z "${GUAZI_SSO_USER_NAME:-}" ]]; then
      read -r -p "请输入瓜子用户名: " GUAZI_SSO_USER_NAME
    fi
    if [[ -z "${GUAZI_SSO_PASSWORD:-}" ]]; then
      read -r -s -p "请输入瓜子密码（输入时不会显示）: " GUAZI_SSO_PASSWORD
      echo
    fi
    if [[ -z "${GUAZI_SSO_APPLY_PHONE:-}" ]]; then
      read -r -p "请输入手机号: " GUAZI_SSO_APPLY_PHONE
    fi
    read_jira_token
    read_gitlab_token
    if [[ -z "${GUAZI_SSO_USER_NAME:-}" || -z "${GUAZI_SSO_PASSWORD:-}" || -z "${GUAZI_SSO_APPLY_PHONE:-}" ]]; then
      echo "用户名、密码和手机号不能为空；未写入鉴权文件。" >&2
      exit 2
    fi
    append_env_value "GUAZI_SSO_USER_NAME" "$GUAZI_SSO_USER_NAME"
    append_env_value "GUAZI_SSO_PASSWORD" "$GUAZI_SSO_PASSWORD"
    append_env_value "GUAZI_SSO_APPLY_PHONE" "$GUAZI_SSO_APPLY_PHONE"
    append_env_value "JIRA_TOKEN" "$JIRA_TOKEN"
    append_env_value "GUAZI_GITLAB_TOKEN" "$GUAZI_GITLAB_TOKEN"
    ;;
  *)
    echo "未知鉴权模式：$AUTH_MODE。请输入 sso 或 cookie。" >&2
    exit 2
    ;;
esac

chmod 600 "$AUTH_ENV_FILE"
echo "已写入 $AUTH_ENV_FILE"
