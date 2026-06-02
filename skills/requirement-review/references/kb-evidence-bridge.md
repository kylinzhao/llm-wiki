# LLM Wiki 知识库证据桥接

本文件是 `$requirement-review` 相对 `$prd-review-max` 的**唯一增量层**。`prd-review-max` 负责 PRD/Spec 本身的业务与 UX 诊断；本文件负责在评审前/后接入 LLM Wiki 知识库证据，并补充影响范围、历史冲突与已有实现差异。

**禁止修改** `prd-review-max` 包内任何文件。若上游规则不足，只在本文件或 `$requirement-review/SKILL.md` 中补充桥接说明。

## 何时启用

满足任一条件即启用知识库证据层：

- 当前项目是 LLM Wiki 项目（存在 `BUSINESS_CONTEXT.md`、`raw/`、`wiki/` 等）
- 用户通过 `$llm-wiki-review-requirement` 或 `llm-wiki review-requirement` 触发
- 用户明确要求结合历史需求、业务 wiki 或代码能力评审

若当前目录不是 LLM Wiki 项目，跳过本文件中的检索步骤，直接执行 `$prd-review-max`。

## 阶段 A：需求证据就位（在调用 prd-review-max 之前）

### A1. 识别目标需求

- Cwiki URL / pageId → 扫描 `raw/**/index.md` 的 `page_id`、`source_url`
- 本地 Markdown / 文档路径 → 直接作为目标需求
- 粘贴文本 → 标记为 `粘贴文本`，证据强度弱于 raw

### A2. raw 同步

- Cwiki 页面不在 `raw/` 时：若项目有 Cwiki/raw 同步流程，先同步再评审
- 禁止手改已有 `raw/` 页面；同 pageId 版本冲突且无安全约定时，停止并询问
- 同步后如有 `tools/update_wiki.py`，运行确定性 update（通常 `uv run python tools/update_wiki.py`）

### A3. 多模态与原型

- 需求相关图片：多模态详细识别，记录 UI、流程、表格、状态、字段与文本冲突
- zip 附件：按 HTML 原型处理，解压到临时目录，检查入口页、交互、状态、mock 数据
- 若需本地预览且工作区端口易冲突，先运行 local-port-registry guard

## 阶段 B：知识库证据检索（在调用 prd-review-max 之前）

按顺序检索，并把**会改变评审结论**的发现整理成「知识库上下文摘要」，供后续注入 prd-review-max 诊断：

| 顺序 | 证据层 | 用途 |
| --- | --- | --- |
| 1 | `BUSINESS_CONTEXT.md` | 业务语义基线、长期方向 |
| 2 | 目标需求源（raw/ 或用户提供） | 本次评审对象 |
| 3 | `docs/retrieval-playbook.md` | 检索策略 |
| 4 | `wiki/overview.md`、`wiki/index.md`、相关 `wiki/sources/` | 站点定位与来源 |
| 5 | `wiki/concepts/`、`wiki/entities/` | 实体与概念口径 |
| 6 | `wiki/truth/`、`wiki/conflicts/`、`wiki/evidence/`、`wiki/proposals/` | 已定事实、冲突、待决 |
| 7 | `wiki/reference/`、`wiki/operations/` | 操作规则与参考 |
| 8 | 相关历史 `raw/**/index.md`、`wiki/sources/` | 历史 PRD、实验、运营规则 |
| 9 | `raw-code/`、`wiki/code/capabilities/`、`wiki/code/traceability/` | 已有实现与能力边界 |

检索目标：

- **影响范围**：需求触及哪些业务域、实体、页面、接口、状态机、账户/资金/权限模型
- **合理性**：与历史规则、已定 truth、已有代码能力是否一致；是否存在重复建设或口径冲突
- **实现差异**：代码已支持但 PRD 未写明的点（仅作备注，不单独作为 UX 缺失 finding）

输出内部摘要（可不在最终报告开头展开，但必须用于评审）：

```text
知识库上下文摘要：
- 相关业务域：
- 冲突/待决 truth：
- 历史类似需求：
- 已有代码能力（支持/缺失/不确定）：
- 建议 MECE 影响面（模块/角色/状态/数据/接口/运营）：
```

## 阶段 C：调用 prd-review-max

1. 确认 `$prd-review-max` 已安装：检查当前 Agent 环境的 skills 目录是否存在 `prd-review-max/SKILL.md`。
2. 若不存在，运行 llm-wiki-skill 包内：

   ```bash
   ./scripts/install_prd_review_max.sh --link --client auto
   ```

3. 读取 **prd-review-max** 包根目录 `SKILL.md`（路径由环境解析，勿写死绝对路径）。
4. 严格按 prd-review-max 的「规则加载方式」读取其 `references/` 下文件；**不要**读取已废弃的本地 `requirement-review/references/review-protocol.md` 等旧文件。
5. 将用户需求与「知识库上下文摘要」一并作为评审输入；映射用户说法到 prd-review-max 的评审范围与模式：

| 用户/旧说法 | prd-review-max |
| --- | --- |
| 完整评审 | 评审范围：业务评审 + 用户体验评审；评审模式：完整 |
| 产品评审 / PM 视角 | 评审范围：业务评审；评审模式：产品 |
| 快速评审 | 评审范围：业务评审（或用户指定范围）；评审模式：快速 |
| 评分概览 | 评审范围：业务评审；评审模式：评分概览 |
| 只看 UX / 前端 | 评审范围：用户体验评审 |
| 未指定 | 默认：业务评审 + 用户体验评审；评审模式：产品 |

6. 执行 prd-review-max 全流程，输出结构**以 prd-review-max routing 为准**，不在中间改写其模板。

## 阶段 D：知识库增量输出（在 prd-review-max 输出之后）

在 prd-review-max 结果之后，追加以下 LLM Wiki 专属章节（无 KB 证据时可写「不适用」）：

```text
## 知识库证据范围
（查询类型、BUSINESS_CONTEXT、raw 状态、图片/zip、代码证据、检索路径）

## MECE 影响范围
（按模块/角色/状态/数据/接口/运营/指标 MECE 展开）

## 历史规则与冲突
（wiki/conflicts、truth、历史 sources 中与本次需求的冲突或继承关系）

## 已有实现差异对照
（raw-code / wiki/code 与 PRD 差异；代码已有实现仅备注：建议 PRD 补录对齐）

## Cwiki 评论版
（无本地路径；用原始 Cwiki 链接；发布前扫描本地路径）

## 建议下一步
（含 raw 同步、update、query-plus、待产品确认项）
```

## 安全与证据纪律

- 不手改 `raw/` 源证据
- 不把 `/Users/...`、`raw/...`、`wiki/sources/...` 写入 Cwiki 评论稿
- 证据不足时明确标注，不把推断当事实
- 「代码已有实现但 PRD 未写」不作为单独 UX 缺失 finding，仅放在「已有实现差异对照」备注

## Finding 格式（与 prd-review-max 并存时）

P0/P1/P2 finding 若来自知识库交叉验证，在「证据」字段注明 KB 来源，例如：

```text
标题：
等级：
证据：（PRD 原文 + wiki/truth/xxx 或 wiki/code/capabilities/xxx）
影响：
建议决策：
是否阻塞开发：
```
