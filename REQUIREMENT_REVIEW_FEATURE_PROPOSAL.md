# LLM Wiki 需求 Review 功能改造建议

## 背景

这次对「直联风控&处罚-秒杀、DCN拉齐处罚方案」做 review 时，`llm-wiki` 已经证明了一个很有价值的使用方式：不是单独读一篇 PRD，而是把目标需求放回现有业务 wiki、历史需求、知识点、代码能力和实现边界里交叉审查。

现有 `$llm-wiki query` 可以回答问题，`$llm-wiki doctor` 可以审查 wiki 质量，但都不是专门为“新需求评审”设计的。需求 review 需要一套独立流程：接收原始需求 URL，确保它进入 `raw/` 证据层，拉通历史语境和代码证据，输出 findings-first 的审查意见，并能把评论发布回原始 wiki。

## 目标

新增一个需求评审能力，让用户可以这样使用：

```text
用 $llm-wiki review-requirement 帮我 review 这个需求：https://cwiki.guazi.com/pages/viewpage.action?pageId=...
```

能力目标：

- 支持 Cwiki 原始 URL 作为评审入口。
- 如果目标 URL 不在当前 `raw/`，主动发起一次 wiki 下载，把原文纳入 `raw/` 后再评审。
- 基于 `BUSINESS_CONTEXT.md`、`wiki/`、`wiki/code/`、`raw/` 做全局交叉审查。
- 明确区分需求文档证据、代码实现证据、外部系统缺口和推断。
- 输出完整报告版和 Cwiki 评论版。
- 打通评论功能，支持将审查意见发布到原始 wiki 评论区，并做回读校验。

## 新增命令

建议在主 skill 中新增命令：

| Command | Use When | Primary Output |
| --- | --- | --- |
| `llm-wiki review-requirement` | 用户给出 PRD、Cwiki 页面、需求文档 URL，要求做需求评审、查漏补缺、影响范围分析 | 需求评审报告、P0/P1/P2 findings、MECE 影响范围、待决问题、Cwiki 评论稿 |

建议增加短入口 wrapper：

```text
skills/llm-wiki-review-requirement/SKILL.md
```

wrapper 只转发到主协议，避免复制规则：

```text
请使用 $llm-wiki review-requirement 对给定需求做证据型评审。
```

## 标准流程

### 1. 输入识别

需求 review 支持三类输入：

| 输入 | 处理方式 |
| --- | --- |
| `raw/**/index.md` 已存在 | 直接以本地 raw 为目标需求证据 |
| Cwiki URL / pageId | 先检查 raw 是否已有同 pageId；没有则主动下载 |
| 普通 Markdown / 文档路径 | 按 `add-wiki` 证据导入规则纳入 raw 或只读评审 |

### 2. 原始 URL 不在 raw 时主动下载

这是本次必须新增的规则：

> 如果用户提供的是原始 wiki URL，且当前项目 `raw/` 中不存在对应 `pageId` 或 `source_url`，需求 review 不应只靠浏览器临时读取页面。应主动发起一次 wiki 下载，把目标需求落入 `raw/`，再运行受影响的 deterministic build / update。

推荐下载步骤：

1. 从 URL 提取 `pageId`。
2. 扫描 `raw/**/index.md` frontmatter 中的 `page_id`、`source_url`。
3. 若不存在，使用已登录 Cwiki 会话或项目配置的 raw sync 工具下载页面。
4. 新增目录：`raw/<pageId>-<slug-title>/index.md`。
5. frontmatter 至少保留：

```yaml
---
page_id: "662255987"
source_url: "https://cwiki.guazi.com/pages/viewpage.action?pageId=662255987"
title: "直联风控&处罚-秒杀、DCN拉齐处罚方案"
space_key: "C2B"
version: 9
updated_at: "2026-04-29T19:24:26+08:00"
downloaded_at: "2026-04-29T21:40:00+08:00"
source_type: "cwiki"
---
```

6. 不改写已有 `raw/` 页面；如果同 pageId 已存在但版本不同，按增量 sync 规则处理，必要时生成新版本记录或停下确认。
7. 运行项目更新：

```bash
uv run python tools/update_wiki.py
```

如果项目支持原始同步命令，则使用：

```bash
uv run python tools/update_wiki.py --raw-sync-command '<download or sync command>'
```

### 3. 评审检索路径

需求 review 的检索路径应固定输出：

```text
查询类型：需求评审
已使用 BUSINESS_CONTEXT.md：是
目标需求：
raw 状态：已存在 / 本次下载 / 只读外部页面
检索路径：
1. BUSINESS_CONTEXT.md
2. 目标 raw/source 页面
3. concepts/entities
4. conflicts/evidence/proposals/truth/reference
5. 相关历史 sources
6. wiki/code/capabilities
7. wiki/code/traceability
8. 必要时回 raw
```

### 4. Review 维度

默认按 MECE 维度检查：

| 维度 | 检查点 |
| --- | --- |
| 业务愿景 | 是否与 `BUSINESS_CONTEXT.md` 和产品长期方向冲突 |
| 用户旅程 | 是否影响关键链路、转化动作、角色权益 |
| 历史规则 | 是否与已有 PRD、运营规则、实验结论冲突 |
| 状态机 | 是否覆盖创建、成功、失败、逾期、撤销、恢复、异常 |
| 资金账户 | 是否明确扣款、冻结、退款、负余额、对账、幂等 |
| 角色账户 | 普通账号、KA、主子账号、门店、多主体是否闭环 |
| 前端入口 | 按页面、按钮、弹窗、置灰、记录、跳转检查一致性 |
| 后端能力 | API、service、job、message、table、外部依赖是否存在 |
| 数据迁移 | 历史状态、老规则、新规则、灰度切换是否可迁移 |
| 通知运营 | push、站内信、公告、帮助中心、客服话术是否一致 |
| 指标监控 | 是否能监控业务伤害、治理收益、异常和回滚条件 |

### 5. Findings-first 输出

需求 review 的输出应优先列问题，而不是先复述需求。

建议分级：

| 等级 | 含义 |
| --- | --- |
| P0 | 不解决会导致开发无法唯一实现、账务/规则错误、严重业务风险 |
| P1 | 不解决会导致体验不一致、测试口径缺失、运营解释困难 |
| P2 | 建议增强项、监控项、文案项、灰度项 |

每个 finding 包含：

```text
标题：
等级：
证据：
影响：
建议决策：
是否阻塞开发：
```

## 输出形态

### 完整报告版

用于对话或本地沉淀：

```text
一、结论
二、证据范围
三、全局定位
四、前后变化
五、MECE 影响范围
六、P0/P1/P2 问题
七、建议目标模型
八、验收清单
九、指标护栏
十、待决问题
十一、证据链接
```

### Cwiki 评论版

用于发布回原始 wiki 评论区：

- 使用 HTML storage 格式或 Confluence 兼容 Markdown。
- 证据范围必须使用原始 Cwiki 链接。
- 禁止出现本地路径，例如 `/Users/...`、`wiki/sources/*.md`。
- 代码证据可以描述为“本地代码证据显示”，但不要贴本地路径，除非评论目标允许。
- 发布前做本地路径扫描。

## 评论功能打通

需求 review 应支持把评论发布回原始 wiki，但必须有安全边界。

### 推荐能力

新增脚本或工具：

```text
skills/llm-wiki/scripts/cwiki_download.py
skills/llm-wiki/scripts/cwiki_comment.py
```

脚本只负责 I/O：

- `cwiki_download.py`：读取 Cwiki 页面并写入 `raw/`。
- `cwiki_comment.py`：发布、更新、回读评论。
- 不在脚本里做 LLM 总结、规则判断或需求分析。

### 评论发布流程

1. 生成评论稿。
2. 检查评论稿是否包含本地路径。
3. 检查评论稿中的证据链接是否为原始 Cwiki URL。
4. dry-run 输出：目标 pageId、标题、评论长度、链接数量、本地路径检查结果。
5. 用户确认后发布，或在用户已明确要求“推送评论”时直接发布。
6. 使用 Cwiki REST API 创建评论。
7. 如果先创建了测试评论，应原地更新，不留下垃圾评论。
8. 发布后回读校验：commentId、version、webui、链接数量、本地路径检查结果。

### Cwiki API 经验

本次实测里：

- `POST /rest/api/content/{pageId}/child/comment` 返回 `405`，不可用于写入。
- `POST /rest/api/content` 可以创建 comment。
- `PUT /rest/api/content/{commentId}` 可以更新 comment。
- `GET /rest/api/content/{commentId}?expand=body.storage,version` 可用于回读校验。

创建评论 payload 示例：

```json
{
  "type": "comment",
  "container": {
    "id": "662255987",
    "type": "page"
  },
  "body": {
    "storage": {
      "value": "<h2>LLM Wiki 交叉审查意见</h2><p>...</p>",
      "representation": "storage"
    }
  }
}
```

更新评论 payload 示例：

```json
{
  "id": "663228641",
  "type": "comment",
  "title": "Re: 页面标题",
  "container": {
    "id": "662255987",
    "type": "page"
  },
  "body": {
    "storage": {
      "value": "<h2>更新后的评论</h2>",
      "representation": "storage"
    }
  },
  "version": {
    "number": 2,
    "minorEdit": false
  }
}
```

### 发布安全规则

- 默认先 dry-run。
- 如果用户明确说“推送到评论区”，可以执行发布，但仍要先完成本地路径检查。
- 不能修改原始需求正文，除非用户明确要求编辑页面。
- 不能删除或覆盖他人评论。
- 如果需要更新已发布评论，只能更新本轮创建的 commentId，或用户明确指定的 commentId。
- 认证失败、权限不足、页面不存在时，输出评论稿和失败原因，不伪装已发布。

## 建议文件改动

第一阶段只做协议和模板：

```text
skills/llm-wiki/SKILL.md
skills/llm-wiki/README.md
skills/llm-wiki/references/commands.md
skills/llm-wiki/references/query-logic.md
skills/llm-wiki/references/requirement-review.md
skills/llm-wiki/templates/requirement-review.md
skills/llm-wiki/templates/requirement-review-comment.html
skills/llm-wiki-review-requirement/SKILL.md
skills/llm-wiki-review-requirement/agents/openai.yaml
README.md
INSTRUCTION_AND_RELEASE_PLAN.md
```

第二阶段再加 Cwiki I/O：

```text
skills/llm-wiki/scripts/cwiki_download.py
skills/llm-wiki/scripts/cwiki_comment.py
```

如果已有独立 `cwiki-upload` skill，可以把评论能力沉淀为 `cwiki-comment` 通用 skill；`llm-wiki review-requirement` 只调用它，不复制 Confluence 发布逻辑。

## 验收标准

### 功能验收

- 给一个已在 `raw/` 的需求 URL，能直接 review。
- 给一个不在 `raw/` 的 Cwiki URL，会先下载到 `raw/`，再 update，再 review。
- 输出报告显式说明 `raw 状态`。
- 输出报告能区分需求证据、代码证据、推断、缺失证据。
- 评论版不包含本地路径。
- 评论版证据范围使用原始 Cwiki 链接。
- 用户要求推送评论时，能创建评论并返回 comment URL。
- 发布后能回读校验 commentId、version、本地路径检查、链接数量。

### 质量验收

- 不复述为主，必须 findings-first。
- 每个 P0/P1 都能说明证据、影响和建议决策。
- 不把后端接口存在写成业务一定生效。
- 不把外部系统缺失证据写成当前代码已支持。
- 不把临时浏览器读取当成可复现证据；原始 URL 需要进入 `raw/` 或明确标记为只读外部证据。

## 本次案例沉淀

「直联风控&处罚-秒杀、DCN拉齐处罚方案」暴露出的通用需求 review 模式：

- 目标需求页可能是新页面，本地 `raw/` 不一定已有。
- 只读当前页会漏掉历史规则和业务愿景冲突。
- 需求里的“统一规则”必须和旧版梯度处罚、现有入口规则、已有申诉能力、资金外部依赖一起审。
- 报告给用户看可以引用本地 wiki；评论贴回 Cwiki 时必须换成原始链接。
- 评论发布不是页面发布，不能复用只支持创建/更新页面的 upload 流程，需要专门 comment 能力。

这说明 `review-requirement` 应该成为 `llm-wiki` 的一等命令，而不是靠临时 query 拼出来。
