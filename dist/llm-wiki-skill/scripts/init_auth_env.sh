#!/usr/bin/env bash
set -euo pipefail

AUTH_ENV_FILE="${LLM_WIKI_AUTH_ENV_FILE:-$HOME/.llm-wiki/guazi-sso.env}"
AUTH_DIR="$(dirname "$AUTH_ENV_FILE")"

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

mkdir -p "$AUTH_DIR"
chmod 700 "$AUTH_DIR"
umask 077

cat > "$AUTH_ENV_FILE" <<EOF
# Local llm-wiki SSO credentials. Do not commit.
GUAZI_SSO_USER_NAME=$GUAZI_SSO_USER_NAME
GUAZI_SSO_PASSWORD=$GUAZI_SSO_PASSWORD
GUAZI_SSO_APPLY_PHONE=$GUAZI_SSO_APPLY_PHONE
JIRA_TOKEN=$JIRA_TOKEN
EOF

chmod 600 "$AUTH_ENV_FILE"
echo "已写入 $AUTH_ENV_FILE"
