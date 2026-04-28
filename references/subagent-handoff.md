# Subagent Handoff

Use this reference when splitting large `llm-wiki` build, refinement, code wiki, image evidence, or audit work across subagents.

## Task Template

```text
你不独自在代码库里，有其他 worker 并行。

先读：
- BUSINESS_CONTEXT.md
- 与本任务相关的 docs / wiki 入口

只读：
- raw/
- raw-code/（如适用）

绝不修改：
- raw/
- 未分配给你的 wiki / docs / staging 文件

只编辑以下文件或目录：
- ...

不要编辑以下文件或目录：
- ...

不要运行 build / health / graph，除非任务明确要求。
不要调用本地模型 SDK 做摘要、分类、实体归一或语义判断。
不要写入 token、cookie、password、secret、private key、access key 或敏感配置值。

完成后汇报：
- 改了哪些文件
- 每页 / 每图 / 每个 endpoint 的关键事实
- 使用了哪些 source / code evidence
- 哪些是推断
- 哪些证据缺失
- 是否改 raw
- 是否运行命令
- 置信度和剩余风险
```

## Output Formats

### Source Refinement

```text
files_changed:
- wiki/sources/...

source_pages:
- page:
  raw_input:
  canonical_entities:
  key_facts:
  conflicts:
  missing_evidence:
  confidence:
```

### Codebase Scan

```text
codebase_id:
scan_scope:
files_changed:
technology:
entrypoints:
modules:
routes_or_endpoints:
services_or_controllers:
async_or_jobs:
openspec:
secrets_redacted:
evidence_gaps:
confidence:
```

### Endpoint Map

```text
mappings:
- frontend_uri:
  frontend_file:
  backend_endpoint:
  backend_file:
  match_type: exact_uri | base_path | type_match | naming_inference | graphify_inference
  evidence_strength: strong | medium | inference
  notes:
```

### Capability Draft

```text
capability:
aliases:
requirement_evidence:
frontend_evidence:
backend_evidence:
technical_design_evidence:
confirmed_facts:
inferences:
missing_evidence:
proposed_links:
```

### Audit Finding

```text
finding:
severity:
file:
evidence:
recommended_fix:
auto_fix_safe: true | false
business_confirmation_needed: true | false
```

## Ownership Rules

- Subagents may produce local pages, drafts, tables, findings, and mapping fragments.
- Main agent owns global naming, capability deduplication, top-level indexes, cross-layer links, and final validation.
- Never let two subagents write the same file.
- If an assigned file already changed unexpectedly, preserve the change and report the conflict instead of overwriting it.
