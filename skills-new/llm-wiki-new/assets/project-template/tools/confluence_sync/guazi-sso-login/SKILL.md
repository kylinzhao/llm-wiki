---
name: llm-wiki-new
description: Use when 需要获取瓜子 SSO Cookie、CHDSSO token 或 cwiki.guazi.com Wiki 登录态，特别是其他 skill 遇到未登录、Cookie/token 失效、E_NO_COOKIE、需要 CWIKI_MANUAL_COOKIE、GUAZISSO 或 chdsso 请求头时（实验包 llm-wiki-new；与全局 llm-wiki 并行，验证通过后再合并）
---

## 功能

获取瓜子 SSO / Wiki / CHDSSO 登录态，作为其他 skill 的基础登录态提供者。

- `sso`：返回 `GUAZISSO=<token>`
- `wiki`：返回可直接用于 `cwiki.guazi.com` 请求头的完整 Cookie
- `chdsso`：返回可直接作为请求头 `chdsso: <token>` 使用的 token，默认环境为 `test`
- `init`：写入本地登录凭据缓存，不发起远端登录
- `init-chdsso`：按环境写入 CHDSSO 的 `phone`、`code` 缓存，不发起远端登录
- 默认使用当天缓存；只有 `--force-refresh` 或刷新原因表示失效/过期时才重新请求
- `wiki --validate` 会在返回缓存前校验 Wiki Cookie；若缓存失效且本地有凭据，会自动重新登录并刷新缓存
- `chdsso --validate` 会在返回缓存前调用对应环境的 CHDSSO 校验接口；若缓存失效且本地有该环境凭据，会自动重新登录并刷新缓存
- 首次需要通过 `init` 写入 `password`、`userName`、`applyPhone`，后续从本地凭据缓存读取
- CHDSSO 首次需要通过 `init-chdsso --env <env>` 写入该环境的 `phone`、`code`；`phone` 和 `code` 必须按环境分别存储与读取
- `sso` / `wiki` / `chdsso` 默认非交互；缺凭据时返回 `E_MISSING_CREDENTIALS`。其他 skill 不应代收凭据，应提示用户单独调用本 skill 的初始化能力完成初始化。

## 统一执行要求

不要假设当前工作目录是 skill 所在目录。必须先取 `SKILL.md` 所在目录作为 `SKILL_ROOT`，再通过 `run.sh` 调用：

```bash
SKILL_ROOT="$(dirname "<SKILL.md 的绝对路径>")"
bash "$SKILL_ROOT/run.sh" wiki --validate --plain
```

获取 SSO Cookie：

```bash
bash "$SKILL_ROOT/run.sh" sso --env online --plain
```

获取 Wiki Cookie：

```bash
bash "$SKILL_ROOT/run.sh" wiki --validate --plain
```

获取 CHDSSO token，默认测试环境：

```bash
bash "$SKILL_ROOT/run.sh" chdsso --validate --plain
```

获取指定环境 CHDSSO token：

```bash
bash "$SKILL_ROOT/run.sh" chdsso --env pre --validate --plain
```

强制刷新：

```bash
bash "$SKILL_ROOT/run.sh" wiki --force-refresh --plain
```

初始化登录凭据缓存，不发起远端登录：

```bash
bash "$SKILL_ROOT/run.sh" init \
  --user-name "<userName>" \
  --password "<password>" \
  --apply-phone "<applyPhone>"
```

初始化 CHDSSO 登录凭据缓存，不发起远端登录：

```bash
bash "$SKILL_ROOT/run.sh" init-chdsso \
  --env test \
  --phone "<phone>" \
  --code "<code>"
```

检查缓存与凭据状态，不发起远端登录：

```bash
bash "$SKILL_ROOT/run.sh" check
```

## 给其他 skill 的接入方式

当 `cwiki-download` 遇到 `E_NO_COOKIE`、未登录、Chrome 调试端口拿不到 Confluence Cookie，或用户明确希望不依赖 Chrome 登录态时，先调用本 skill 获取 Wiki Cookie，再把它作为手动 Cookie 传回原流程：

```bash
SSO_SKILL_ROOT="$(dirname "<guazi-sso-login/SKILL.md 的绝对路径>")"
CWIKI_SKILL_ROOT="$(dirname "<cwiki-download/SKILL.md 的绝对路径>")"
COOKIE="$(bash "$SSO_SKILL_ROOT/run.sh" wiki --validate --plain)"

CWIKI_USE_MANUAL_COOKIE=1 \
CWIKI_MANUAL_COOKIE="$COOKIE" \
bash "$CWIKI_SKILL_ROOT/run.sh" "123456"
```

如果 `run.sh wiki --validate --plain` 提示缺少登录信息，调用方应停止当前流程，并提示用户单独调用 `guazi-sso-login` skill 的 `init` 能力完成初始化。不要在其他 skill 的流程中收集或代传 `password`、`userName`、`applyPhone`。用户进入本 skill 的初始化流程后，再由本 skill 收集凭据并写入缓存：

```bash
bash "$SSO_SKILL_ROOT/run.sh" init \
  --user-name "<userName>" \
  --password "<password>" \
  --apply-phone "<applyPhone>"

COOKIE="$(bash "$SSO_SKILL_ROOT/run.sh" wiki --validate --plain)"
```

当其他 skill 需要 CHDSSO 时，先调用本 skill 获取 token，再作为请求头 `chdsso` 传入目标接口：

```bash
SSO_SKILL_ROOT="$(dirname "<guazi-sso-login/SKILL.md 的绝对路径>")"
TOKEN="$(bash "$SSO_SKILL_ROOT/run.sh" chdsso --env test --validate --plain)"

curl -H "chdsso: $TOKEN" "<需要 CHDSSO 的接口>"
```

如果 `run.sh chdsso --validate --plain` 提示缺少登录信息，调用方应停止当前流程，并提示用户单独调用本 skill 的 `init-chdsso --env <env>` 能力完成初始化。不要在其他 skill 的流程中收集或代传 `phone`、`code`。用户进入本 skill 的初始化流程后，再由本 skill 按环境收集并写入缓存：

```bash
bash "$SSO_SKILL_ROOT/run.sh" init-chdsso \
  --env test \
  --phone "<phone>" \
  --code "<code>"

TOKEN="$(bash "$SSO_SKILL_ROOT/run.sh" chdsso --env test --validate --plain)"
```

## 环境变量

- `GUAZI_SSO_USER_NAME`：用户名
- `GUAZI_SSO_PASSWORD`：登录密码
- `GUAZI_SSO_APPLY_PHONE`：手机号
- `GUAZI_CHDSSO_PHONE`：CHDSSO 手机号
- `GUAZI_CHDSSO_CODE`：CHDSSO 验证码
- `GUAZI_CHDSSO_<ENV>_PHONE`：指定环境 CHDSSO 手机号，例如 `GUAZI_CHDSSO_TEST_PHONE`
- `GUAZI_CHDSSO_<ENV>_CODE`：指定环境 CHDSSO 验证码，例如 `GUAZI_CHDSSO_TEST_CODE`
- `GUAZI_SSO_CACHE_DIR`：缓存目录，默认 `~/.agents/cache/guazi-sso-login`
- `GUAZI_SSO_CACHE_FILE`：缓存文件名或绝对路径，默认 `sso-cache.json`

缓存文件包含登录凭据、按环境保存的 CHDSSO `phone`/`code` 与当天 token/Cookie，脚本会尽量设置为仅当前用户可读写。

## 错误处理

命令失败时输出结构化错误：

```text
[ERROR] E_XXX
原因：...
建议：...
```

- `E_MISSING_CREDENTIALS`：缺少 `password`、`userName` 或 `applyPhone`
- `E_LOGIN_FAILED`：远端登录返回失败信息
- `E_TOKEN_PARSE_FAILED`：登录成功响应中无法解析 token
- `E_WIKI_LOGIN_FAILED`：Wiki OAuth 流程失败
- `E_CHDSSO_VALIDATE_FAILED`：CHDSSO token 校验失败
- `E_HTTP_ERROR`：远端接口请求失败
- `E_CACHE_ERROR`：缓存读写失败
