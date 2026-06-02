#!/usr/bin/env bash
set -euo pipefail

AUTH_ENV_FILE="${LLM_WIKI_AUTH_ENV_FILE:-$HOME/.llm-wiki/guazi-sso.env}"
AUTH_DIR="$(dirname "$AUTH_ENV_FILE")"

quote_env_value() {
  printf '%q' "$1"
}

append_env_value() {
  local key="$1"
  local value="$2"
  if [[ -n "$value" ]]; then
    printf '%s=%s\n' "$key" "$(quote_env_value "$value")" >> "$AUTH_ENV_FILE"
  fi
}

read -r -p "Choose auth mode [sso/cookie] (default: sso): " AUTH_MODE
AUTH_MODE="${AUTH_MODE:-sso}"

mkdir -p "$AUTH_DIR"
chmod 700 "$AUTH_DIR"
umask 077

cat > "$AUTH_ENV_FILE" <<'EOF'
# Local llm-wiki auth values. Do not commit.
# Loaded by llm-wiki Cwiki sync tools on this computer.
EOF

case "$AUTH_MODE" in
  cookie)
    read -r -s -p "Paste full COOKIE_HEADER（输入时不会显示）: " COOKIE_HEADER
    echo
    read -r -s -p "请输入 Jira 令牌（输入时不会显示，没有可直接回车）: " JIRA_TOKEN
    echo
    if [[ -z "$COOKIE_HEADER" ]]; then
      echo "COOKIE_HEADER 不能为空；未写入鉴权文件。" >&2
      exit 2
    fi
    append_env_value "COOKIE_HEADER" "$COOKIE_HEADER"
    append_env_value "JIRA_TOKEN" "$JIRA_TOKEN"
    ;;
  sso)
    read -r -p "请输入瓜子用户名: " GUAZI_SSO_USER_NAME
    read -r -s -p "请输入瓜子密码（输入时不会显示）: " GUAZI_SSO_PASSWORD
    echo
    read -r -p "请输入手机号: " GUAZI_SSO_APPLY_PHONE
    read -r -s -p "请输入 Jira 令牌（输入时不会显示，没有可直接回车）: " JIRA_TOKEN
    echo
    if [[ -z "$GUAZI_SSO_USER_NAME" || -z "$GUAZI_SSO_PASSWORD" || -z "$GUAZI_SSO_APPLY_PHONE" ]]; then
      echo "用户名、密码和手机号不能为空；未写入鉴权文件。" >&2
      exit 2
    fi
    append_env_value "GUAZI_SSO_USER_NAME" "$GUAZI_SSO_USER_NAME"
    append_env_value "GUAZI_SSO_PASSWORD" "$GUAZI_SSO_PASSWORD"
    append_env_value "GUAZI_SSO_APPLY_PHONE" "$GUAZI_SSO_APPLY_PHONE"
    append_env_value "JIRA_TOKEN" "$JIRA_TOKEN"
    ;;
  *)
    echo "未知鉴权模式：$AUTH_MODE。请输入 sso 或 cookie。" >&2
    exit 2
    ;;
esac

chmod 600 "$AUTH_ENV_FILE"
echo "已写入 $AUTH_ENV_FILE"
