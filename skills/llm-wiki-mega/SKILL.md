---
name: llm-wiki-mega
description: LLM Wiki 超大知识库聚合入口。用于将多个已有 KB 的 raw/raw-code/BUSINESS_CONTEXT 整合到一个统一的 mega KB 中，验证 LLM-WIKI 模式在大规模文档/代码/业务规模下的可行性。
---

# LLM Wiki Mega KB 聚合

将多个已有 LLM Wiki KB 聚合为一个统一的超大知识库，用于验证 LLM-WIKI 模式在大规模场景下的可行性。

## 语言要求

使用中文，与 llm-wiki 主 skill 保持一致。

## 适用场景

- 需要将多个业务域 KB 聚合为一个统一大 KB
- 验证 LLM-WIKI 在 ~4000+ raw 目录、20+ 代码仓库、8+ 业务域规模下的表现
- 跨业务域的实体/概念归一化和知识关联分析

## 前置条件

1. 同一工作空间下存在多个已构建的 LLM Wiki KB
2. 每个源 KB 至少具备 `raw/` 和 `BUSINESS_CONTEXT.md`
3. 足够的磁盘空间（symlink 模式几乎不增加磁盘占用）

## 架构设计

### 证据层（symlink 命名空间）

每个源 KB 的 `raw/` 和 `raw-code/` 通过 **带 KB 前缀的 symlink** 引入 mega KB：

```text
mega-llm-wiki/
  raw/
    c1--{pageId}-{slug}/          → ../../c1llmwiki/raw/{pageId}-{slug}/
    dcn--{pageId}-{slug}/         → ../../dcn-llm-wiki/raw/{pageId}-{slug}/
    dealer-crm--{pageId}-{slug}/  → ../../dealer-crm-llm-wiki/raw/{pageId}-{slug}/
    ...
  raw-code/                       (可选，需解决元数据冲突)
    c1--sell-station/             → ../../c1llmwiki/raw-code/sell-station/
    ...
```

**KB 前缀规则**：`{kb_id}--{原始目录名}`，kb_id 取自 `kb.manifest.yaml` 的 `id` 字段。

### BUSINESS_CONTEXT.md

8 个域的 BUSINESS_CONTEXT.md 合并为一份统一文档，每个域作为 `## 域名 (kb_id)` 二级标题。

### Wiki 层

- `wiki/_imported/{kb_id}/` — 各源 KB 已有 wiki 的历史快照，作为参考
- `wiki/sources/` — 由 build_wiki.py 基于 symlink raw/ 重新生成的源页面
- 其他 wiki 层（concepts/entities/truth/...）— 由 AI 精修阶段构建

### 配置文件

- `config/source-registry.yaml` — 记录每个源 KB 的路径映射和元数据
- `kb.manifest.yaml` — mega KB 的 manifest
- `kb-profile.json` — mega KB 的 profile

## 工具链适配

Python 3.12+ 的 `Path.rglob()` 默认不跟踪 symlink 目录。以下工具需要 `os.walk(followlinks=True)` 适配：

| 文件 | 函数 | 说明 |
|------|------|------|
| `tools/build_wiki.py` | `discover_sources()` | 源文件发现（关键路径） |
| `tools/wiki_preflight.py` | `raw_dir_has_files()` | raw 证据预检 |
| `tools/cjira_registry.py` | `discover_project_sources()` | Cjira 注册表源发现 |

构建脚本 `scripts/build-mega-kb.py` 在安装模板后自动打补丁。

## 构建流程

### Phase 1: 目录结构与 symlink

```bash
python3 scripts/build-mega-kb.py
```

此脚本：
1. 创建 `mega-llm-wiki/` 目录结构
2. 为每个源 KB 创建带前缀的 symlink
3. 合并 BUSINESS_CONTEXT.md
4. 复制已有 wiki 到 `_imported/`
5. 生成 config 文件

### Phase 2: 安装模板与打补丁

```bash
cd mega-llm-wiki
python3 "$HOME/.qoder/skills/llm-wiki/scripts/install_project_template.py" --project "$PWD"
uv sync
```

### Phase 3: 确定性构建

```bash
LLM_WIKI_NO_AUTO_RAW_SYNC=1 LLM_WIKI_UPDATE_MODE=local \
  uv run python tools/update_wiki.py --local --no-auto-raw-sync
```

此阶段运行：
- `build_wiki.py` — 源文件扫描 + source-manifest 生成 + source 页面脚手架
- `cjira_registry.py` — Cjira 状态注册
- `scan_code.py` — 代码扫描（如有 raw-code）
- `build_traceability.py` — 追踪矩阵
- `health.py` — 健康检查
- `build_graph.py` — 知识图谱
- `anchor_check.py` — 锚点检查

### Phase 4: AI 精修（按需）

确定性构建完成后，wiki 页面是脚手架状态。AI 精修阶段负责：
1. 全量 source summary
2. 跨域实体/概念归一化
3. 分层页面构建（concepts/entities/truth/conflicts/...）
4. overview 综合
5. G+ 质量审计

由于 4000+ 源的规模，AI 精修建议分批进行，按域或按主题分批处理。

## raw-code 限制

当前 symlink 方案与 raw-code 的 `.llm-wiki-metadata.json` 元数据校验冲突（metadata 中记录原始 codebase_id，不含 KB 前缀）。解决方案：

1. **暂不包含 raw-code**：聚焦 raw 文档层的聚合验证
2. **后续方案**：为每个 symlink 创建薄包装目录，内含正确的 metadata 和指向源码的 symlink

## 规模参考（首次实验数据）

| 指标 | 值 |
|------|-----|
| 源 KB 数 | 8 |
| Raw 目录 | 4,040 |
| Raw-code 仓库 | 29（暂未启用） |
| Source 页面 | 4,806 |
| 图谱节点 | 11,718 |
| 图谱边 | 70,284 |
| Cjira 活跃页 | 2,993 |
| Draw.io 源页 | 321 |
| 合并 BUSINESS_CONTEXT | 939 行 |

## 最终报告格式

构建完成后输出：
- 目录结构与文件统计
- 确定性构建各阶段结果
- 健康检查摘要
- 图谱状态（节点/边/断边）
- AI 精修进度（如已执行）
- 建议下一步操作
