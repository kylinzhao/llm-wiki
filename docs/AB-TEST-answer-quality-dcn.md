# dcn KB：旧 llm-wiki vs 新 llm-wiki-new — 回答/诊断效果对比

**方法**：同一 KB、同一批证据（`staging/doctor/latest.json`、`health`、`BUSINESS_CONTEXT`、`wiki/*`），按两套 skill **输出格式**各写一份；不跑 Cursor 双会话 token 面板。

**用户问题（诊断）**：「dcn 这个 wiki 现在健康吗？缺什么？」  
**用户问题（query）**：「DCN、同行找车、源头找车是什么关系？B2 在哪里用？」  
**用户问题（query-plus）**：「B2 源头列表/详情在前端和后端怎么实现？」

---

## 一、诊断效果对比

### 1.1 事实层（应完全一致）

两边都应先读 `tools/doctor.py` 产出或 `staging/doctor/latest.json`。**事实相同**：

| 项 | 值 |
|----|-----|
| health | pass，448 wiki 页，381 source |
| P0 | 0 |
| G+ | ok，concept 覆盖率 ~97.9% |
| refinement | ok，pending 0 |
| P1（提权） | 图片证据 unknown（1326 图）；Cjira 43 stale；3 orphan prototype source |

**结论**：诊断的 **P0/P1 清单、verdict 依据** 不会因 skill 包而变；变的是 agent **叙述篇幅** 和 **是否夹带协议噪音**。

### 1.2 旧包 `$llm-wiki-doctor` 风格输出（模拟）

```text
诊断类型：llm-wiki doctor
已使用 BUSINESS_CONTEXT.md：是
读取路径：
  llm-wiki/SKILL.md、references/commands.md（全文）
  README.md、bootstrapping.md、build-and-maintenance.md（阅读顺序常连带）
  BUSINESS_CONTEXT.md、wiki/index.md、wiki/overview.md
  docs/retrieval-playbook.md、docs/build-and-maintenance.md
  staging/refinement-status.md（~162KB）、staging/health/latest.json
  graph/summary.md、wiki/code/*、docs/query-acceptance.md、docs/gplus-quality-audit.md
  staging/doctor/latest.json

总体 verdict：usable-with-gaps

状态画像：
- 输入层：raw/、BUSINESS_CONTEXT 齐全；raw-code：csp-rn-dcn、dcn-center
- 文档层：381 source；G+ 通过；主导概念「同行找车产品全景」181 页
- 图片证据层：1326 张图，164 notes，status=unknown
- 代码层：code wiki / traceability 存在（本诊断未逐条展开矩阵）
- 追踪矩阵：有索引页（未在本轮抽样强度分布）
- 校验层：health pass，graph 正常
- 发布/维护状态：refinement_contract ok；最近增量 2026-05-26

主要问题：
- P1 image_evidence_status_unknown（promoted_from P2）
- P1 cjira_status_quality_gaps（43 stale，30 低置信主单）
- P1 orphan_source_pages（3 个 *.prototype.md 侧车页）

建议下一步：
1. llm-wiki update — 收口 orphan、刷新 Cjira registry
2. llm-wiki image — 高价值流程/状态/费用类截图
3. 无 P0；可暂停日常查询，raw/ 大变更后再 update
```

### 1.3 新包 `$llm-wiki-new-doctor` 风格输出（模拟）

```text
诊断类型：llm-wiki-new doctor
已使用 BUSINESS_CONTEXT.md：是
读取路径：
  references/core-rules.md、commands/_shared.md、commands/doctor.md
  BUSINESS_CONTEXT.md、wiki/overview.md
  staging/health/latest.json、staging/doctor/latest.json、graph/summary.md
  （未整文件加载 staging/refinement-status.md 除非用户追问精修明细）

总体 verdict：usable-with-gaps

状态画像：
- 输入层：raw/raw-code 证据齐全
- 文档层：448 页 / 381 source；G+ ok
- 图片证据层：1326 图，证据状态 unknown → 非阻塞但应进阶段 H
- 代码层：双 codebase 已接入
- 校验层：health pass；doctor 工具 p0=0

主要问题：
- P1 image_evidence_status_unknown
- P1 cjira_status_quality_gaps
- P1 orphan_source_pages（3）

建议下一步：
1. llm-wiki-new update — orphan + Cjira
2. llm-wiki-new image — 按 health 候选页筛选
3. 当前可做业务/代码 query；lifecycle 问题前先刷新 Cjira
```

### 1.4 诊断差异小结

| 维度 | 旧 | 新 | 差异 |
|------|----|----|------|
| **结论/verdict** | usable-with-gaps | usable-with-gaps | **无** |
| **P0/P1 条目** | 3 条 P1 | 3 条 P1 | **无** |
| **可操作性** | update + image | update + image | **无**（仅命令名 `-new`） |
| **叙述** | 易列出 README/阶段/G+ 长清单 | 更贴 doctor.md 模板 | **新更短、少跑题** |
| **风险** | 易误读 162KB refinement-status | 默认用 JSON 摘要 | **新更稳** |

---

## 二、Query 回答效果对比

### 2.1 业务题（应走 query，不带代码细节）

**问题**：DCN、同行找车、源头找车是什么关系？B2 在哪里用？

#### 旧 `$llm-wiki-query`（严格按 commands 业务路径）

**查询类型**：业务/术语  
**检索路径**：BUSINESS_CONTEXT.md §4–§6 → wiki/concepts/dcn-product-overview.md  

**结论**：  
在公司口径里，**源头找车、同行找车、DCN 是同一概念**（车优多 DCN 售卖平台）。**B2 国内同行找车车商**在 **车优多 APP「源头找车」频道**对车源出价拍车，即 DCN 场景。另有多类车源可进入 **「同行找车同售(DCN)」** 售卖维度。

**支撑**：`BUSINESS_CONTEXT.md`（需求方 B2-国内同行找车；平台 车优多DCN；同售 DCN）  
**未决点**：无  
**（按协议未展开）** Controller、URI、RN 页面名。

#### 新 `$llm-wiki-new-query`

**查询类型**：业务/术语  
**检索路径**：同上 + query-logic 业务默认不展开 code  

**结论**：（与旧 **相同**）源头找车 = 同行找车 = DCN；B2 在车优多源头找车频道出价拍车，同售场景见 BUSINESS_CONTEXT §6。

**支撑**：同上  
**未决点**：无  
**提示**：若要接口/RN 实现，用 `llm-wiki-new-query-plus`。

#### Query 业务题差异

| 维度 | 旧 | 新 |
|------|----|----|
| **事实正确性** | ✓ | ✓ |
| **是否夹带代码** | 协议禁止；**若 agent 先读了 30KB 主 SKILL 易误带 code** | 协议更短，**误带 code 概率更低** |
| **篇幅** | 相当 | 相当 |

---

### 2.2 联合题（query-plus）

**问题**：B2 源头列表/详情怎么实现？

#### 旧 / 新（证据相同，回答应一致）

**查询类型**：实现 + 业务边界  
**检索路径**：BUSINESS_CONTEXT（DCN 别名）→ wiki/code/capabilities/source-list-detail.md  

**结论**：  
- **前端**：`csp-rn-dcn` 中 `DCNList`、`CarDetail` 等；列表拉 `/dcncenter/list/sourcelist`（`mixKey=100` 等）。  
- **后端**：`dcn-center` 的 `SourceListService`、详情组装、`DcnCarSourceDService` 等；另有 dealer 侧 Dubbo `querySourceList` 复用列表能力。  
- **证据强度**：列表 URI ↔ 服务边界 **partial~strong**（能力页已写，部分待 controller 下钻）。

**业务边界**：DCN = 源头找车 = 同行找车（与 BUSINESS_CONTEXT 一致）。

**缺口**：未在本答逐条打开 Controller 方法；矩阵级 traceability 未全表展开。

#### Query-plus 差异

| 维度 | 旧 | 新 |
|------|----|----|
| **技术事实** | 相同 | 相同 |
| **证据强度标注** | 旧 commands 较长，agent 可能写更啰嗦 | 新 query-plus.md 强调 strong/partial/inferred | **新格式更规范** |

---

## 三、总评：回答效果有没有差别？

| 问题 | 答案 |
|------|------|
| **诊断结论会不会变？** | **不会**（同一 `tools/doctor.py` + 同一 JSON） |
| **查询事实会不会变？** | **不会**（同一 wiki/raw 证据） |
| **用户看到的报告会不会变？** | **会有一点**：旧版更易冗长、多读无关章节；新版更贴模板、更短 |
| **错误风险会不会变？** | **新版更低**：业务 query 误带代码、诊断被 162KB status 淹没的概率更小 |
| **质量提升是否来自「更聪明」？** | **否**；来自 **更少干扰 + 更清晰的 scope**，不是新模型能力 |

---

## 四、你若要在 Cursor 里肉眼对比

1. 新聊天 A：`用 $llm-wiki-doctor 诊断 /Users/zhaoliang/guazi/work/multi-knowledge-base-space/dcn-llm-wiki`  
2. 新聊天 B：`用 $llm-wiki-new-doctor` 同上  
3. 对比：**verdict、P1 列表应一致**；B 的「读取路径」应更短、且无 `llm-wiki/SKILL.md` 全文  

Query 同理：`$llm-wiki-query` vs `$llm-wiki-new-query` 问同一业务句，看 B 是否更少出现 `/dcncenter/`、`DCNList`。
