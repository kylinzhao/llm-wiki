#!/usr/bin/env python3
"""Deterministic LLM Wiki seed builder.

This script creates the stable file structure that Codex refines afterwards.
It intentionally does not summarize, classify, or normalize semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from cjira_registry import classify_page, update_registry_for_sources
from drawio_diagram import drawio_to_mermaid
from wiki_preflight import raw_evidence_preflight_failed

TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".html",
    ".htm",
    ".csv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".xml",
    ".drawio",
    ".dio",
}

REQUIRED_DIRS = [
    "wiki/sources",
    "wiki/concepts",
    "wiki/entities",
    "wiki/truth",
    "wiki/conflicts",
    "wiki/evidence",
    "wiki/proposals",
    "wiki/reference",
    "wiki/operations",
    "wiki/code/codebases",
    "wiki/code/capabilities",
    "wiki/code/traceability",
    "docs",
    "graph",
    "staging/health",
    "staging/graph",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._\-\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "source"


def read_text(path: Path, limit: int | None = None) -> str:
    data = path.read_bytes()
    if limit is not None:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def title_for(path: Path) -> str:
    if path.suffix.lower() in {".md", ".markdown"}:
        for line in read_text(path, limit=32_000).splitlines():
            match = re.match(r"^#\s+(.+?)\s*$", line)
            if match:
                return match.group(1).strip()
    return path.stem.replace("-", " ").replace("_", " ").strip() or path.name


def discover_sources(raw_dir: Path) -> list[dict[str, object]]:
    sources: list[dict[str, object]] = []
    used_slugs: set[str] = set()
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rel = path.relative_to(raw_dir)
        if "assets" in rel.parts and "prototypes" in rel.parts and path.suffix.lower() not in {".md", ".markdown"}:
            continue
        base = slugify(str(rel.with_suffix("")).replace("/", "-"))
        slug = base
        counter = 2
        while slug in used_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        used_slugs.add(slug)
        stat = path.stat()
        sources.append(
            {
                "title": title_for(path),
                "slug": slug,
                "raw_path": f"raw/{rel.as_posix()}",
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "sha256": sha256_file(path),
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            }
        )
    return sources


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def source_cjira_record(source: dict[str, object], project: Path) -> dict[str, object]:
    raw_path = str(source["raw_path"])
    raw_file = project / raw_path
    text = raw_file.read_text(encoding="utf-8", errors="replace") if raw_file.is_file() else ""
    record = classify_page(str(source["title"]), raw_path, text)
    page_id_match = re.search(r"^page_id:\s*['\"]?(.*?)['\"]?\s*$", text, re.M)
    record["page_id"] = page_id_match.group(1).strip() if page_id_match else ""
    return record


def source_page(source: dict[str, object], project: Path) -> str:
    cjira = source_cjira_record(source, project)
    source_metadata = {
        "page_kind": "source",
        "schema_version": "source-v2",
        "source_slug": source["slug"],
        "page_id": cjira["page_id"],
        "raw_rel": source["raw_path"],
        "raw_hash": source["sha256"],
        "primary_cjira": cjira["primary_cjira"],
        "supporting_cjira": cjira["supporting_cjira"],
        "primary_cjira_status": cjira["primary_cjira_status"],
        "last_checked_at": cjira["last_checked_at"],
        "cjira_confidence": cjira["confidence"],
        "ai_refinement_state": "pending",
    }
    supporting = ", ".join(f"`{key}`" for key in cjira["supporting_cjira"]) or "`none`"
    drawio_block = drawio_source_block(project / str(source["raw_path"]))
    return f"""# {source['title']}

> 确定性种子页。Codex 需要基于原始证据补全摘要、关键事实和 AI 原生精修内容。

## 来源

- 原始路径: `{source['raw_path']}`
- SHA-256: `{source['sha256']}`
- 大小: `{source['size_bytes']}` bytes
- 修改时间: `{source['mtime']}`

## Delivery Tracking

- Primary Jira: `{cjira['primary_cjira'] or 'none'}`
- Supporting Jira: {supporting}
- Jira Status: `{cjira['primary_cjira_status']}`
- Last Checked: `{cjira['last_checked_at']}`
- Confidence: `{cjira['confidence']}`

## 摘要

待完成 AI 原生摘要。

## 关键事实

- 待从来源证据中提取。

{drawio_block}

## 业务链接

- 概念: 待补充
- 实体: 待补充
- 相关分层页面: 待补充

## 证据说明

本页作为来源证据节点使用。不要把原始材料中的敏感值复制到 wiki 正文。

## Source Metadata
```json
{json.dumps(source_metadata, ensure_ascii=False, indent=2)}
```
"""


def drawio_source_block(path: Path) -> str:
    if path.suffix.lower() not in {".drawio", ".dio", ".xml"}:
        return ""
    if not path.is_file():
        return ""
    diagrams = drawio_to_mermaid(path.read_text(encoding="utf-8", errors="replace"), fallback_name=path.stem)
    if not diagrams:
        return ""
    lines = ["## Draw.io Diagrams", ""]
    for diagram in diagrams:
        lines.extend(
            [
                f"### {diagram.name}",
                "",
                f"- Nodes: `{diagram.node_count}`",
                f"- Edges: `{diagram.edge_count}`",
                "",
                "```mermaid",
                diagram.mermaid,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def delivery_tracking_block(cjira: dict[str, object]) -> str:
    supporting = ", ".join(f"`{key}`" for key in cjira["supporting_cjira"]) or "`none`"
    return (
        "## Delivery Tracking\n\n"
        f"- Primary Jira: `{cjira['primary_cjira'] or 'none'}`\n"
        f"- Supporting Jira: {supporting}\n"
        f"- Jira Status: `{cjira['primary_cjira_status']}`\n"
        f"- Last Checked: `{cjira['last_checked_at']}`\n"
        f"- Confidence: `{cjira['confidence']}`\n"
    )


def source_metadata_payload(
    source: dict[str, object],
    cjira: dict[str, object],
    existing: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata = dict(existing or {})
    metadata.update(
        {
            "page_kind": "source",
            "schema_version": "source-v2",
            "source_slug": source["slug"],
            "page_id": cjira["page_id"],
            "raw_rel": source["raw_path"],
            "raw_hash": source["sha256"],
            "primary_cjira": cjira["primary_cjira"],
            "supporting_cjira": cjira["supporting_cjira"],
            "primary_cjira_status": cjira["primary_cjira_status"],
            "last_checked_at": cjira["last_checked_at"],
            "cjira_confidence": cjira["confidence"],
            "ai_refinement_state": metadata.get("ai_refinement_state", "pending"),
        }
    )
    return metadata


def source_metadata_block(metadata: dict[str, object]) -> str:
    return "## Source Metadata\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```\n"


def replace_or_insert_section(text: str, heading: str, block: str, *, before_headings: tuple[str, ...] = ()) -> str:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\n.*?(?=^## |\Z)")
    replacement = block.rstrip() + "\n\n"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    for marker in before_headings:
        needle = f"## {marker}"
        idx = text.find(needle)
        if idx != -1:
            return text[:idx].rstrip() + "\n\n" + replacement + text[idx:]
    return text.rstrip() + "\n\n" + replacement


def refresh_source_header(text: str, source: dict[str, object]) -> str:
    text = re.sub(
        r"(?m)^- (?:Raw path|原始路径): `[^`]+`",
        f"- Raw path: `{source['raw_path']}`",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^- SHA-256: `?[a-f0-9]{64}`?",
        f"- SHA-256: `{source['sha256']}`",
        text,
        count=1,
    )
    return text


def backfill_source_page(path: Path, source: dict[str, object], project: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    cjira = source_cjira_record(source, project)
    text = refresh_source_header(text, source)
    text = replace_or_insert_section(text, "Delivery Tracking", delivery_tracking_block(cjira), before_headings=("Summary", "摘要"))
    metadata = source_metadata_payload(source, cjira, source_page_metadata(path))
    text = replace_or_insert_section(text, "Source Metadata", source_metadata_block(metadata))
    path.write_text(text, encoding="utf-8")


def index_page(sources: list[dict[str, object]], codebases: list[str]) -> str:
    source_lines = "\n".join(
        f"- [[sources/{source['slug']}|{source['title']}]]"
        for source in sources
    ) or "- 尚未发现来源页面。"
    code_lines = "\n".join(
        f"- [[code/codebases/{codebase}/index|{codebase}]]"
        for codebase in codebases
    ) or "- 尚未发现 raw-code 代码库。"
    return f"""# LLM Wiki

生成时间: {utc_now()}

## 入口

- [[overview|总览]]
- [[concepts/index|概念]]
- [[entities/index|实体]]
- [[truth/index|事实]]
- [[conflicts/index|冲突]]
- [[evidence/index|证据]]
- [[proposals/index|方案]]
- [[reference/index|参考]]
- [[operations/index|运营]]
- [[code/index|代码 Wiki]]

## 来源

{source_lines}

## 代码库

{code_lines}
"""


def simple_page(title: str, body: str) -> str:
    return f"# {title}\n\n{body.rstrip()}\n"


def create_layer_pages(project: Path) -> None:
    pages = {
        "wiki/overview.md": (
            "总览",
            "待基于 `BUSINESS_CONTEXT.md`、`wiki/sources/` 和可选的 `wiki/code/` 证据完成综合梳理。",
        ),
        "wiki/concepts/index.md": (
            "概念",
            "AI 原生精修后，在这里沉淀规范业务概念。",
        ),
        "wiki/entities/index.md": (
            "实体",
            "在这里沉淀规范实体、别名和冲突口径。",
        ),
        "wiki/truth/index.md": (
            "事实",
            "在这里沉淀跨来源稳定事实。",
        ),
        "wiki/conflicts/index.md": (
            "冲突",
            "在这里记录冲突需求、冲突术语和待确认业务口径。",
        ),
        "wiki/evidence/index.md": (
            "证据",
            "在这里建立高价值证据索引。",
        ),
        "wiki/proposals/index.md": (
            "方案",
            "在这里沉淀产品、流程或实现方案建议。",
        ),
        "wiki/reference/index.md": (
            "参考",
            "在这里沉淀稳定参考资料、术语表和外部边界。",
        ),
        "wiki/operations/index.md": (
            "运营",
            "在这里沉淀 SOP、操作流程、运行手册和支持流程。",
        ),
        "wiki/code/index.md": (
            "代码 Wiki",
            "这里承载代码库事实、能力页和需求到代码追踪矩阵。",
        ),
        "wiki/code/capabilities/index.md": (
            "代码能力",
            "在这里沉淀跨层业务能力实现页。",
        ),
        "wiki/code/traceability/index.md": (
            "追踪矩阵",
            "在这里沉淀需求到代码的可审计追踪矩阵。",
        ),
    }
    for rel, (title, body) in pages.items():
        write_if_missing(project / rel, simple_page(title, body))


def create_codebase_pages(project: Path, codebases: list[str]) -> None:
    for codebase in codebases:
        path = project / "wiki" / "code" / "codebases" / codebase / "index.md"
        write_if_missing(
            path,
            simple_page(
                f"代码库: {codebase}",
                "待完成代码扫描。在这里记录技术栈、入口、模块边界、API、服务、任务、数据访问和证据缺口。",
            ),
        )


def create_docs(project: Path) -> None:
    write_if_missing(
        project / "docs" / "retrieval-playbook.md",
        """# 检索手册

本文件是查询路由说明书，不是业务证据本身。回答业务、产品、需求、术语、实现状态或代码追踪问题时，先用它决定检索路径，再引用 `wiki/` 或 `raw/` 中的证据。

## 基线步骤

1. 先读取 `BUSINESS_CONTEXT.md`。它是业务语义基线，也是 init/fast/update 的硬性前置，不能是模板 TODO 占位。
2. 判断查询意图，不要直接从模型记忆、单个 `rg` 命中或孤立代码片段下结论。
3. 先查 `wiki/overview.md`，确认站点范围、主链路和已知缺口。
4. 按查询意图进入对应专项目录层。
5. 用 `wiki/concepts/` 和 `wiki/entities/` 做通用扩展层，扩展主题、实体、别名和相关来源。
6. 回到 `wiki/sources/` 找直接需求/业务证据；必要时再回查 `raw/`。
7. 只有当问题涉及实现、架构、接口、调用链、落地状态、测试追踪，或用户明确要求 `query-plus` 时，才进入 `wiki/code/`。
8. 明确区分需求证据、代码证据、推断和缺失证据。

## 查询意图路由

| 查询意图 | 优先检索路径 |
| --- | --- |
| 业务知识 / 产品规则 / 需求口径 / 术语解释 | `BUSINESS_CONTEXT.md` -> `wiki/overview.md` -> 专项目录层 -> `wiki/concepts/` / `wiki/entities/` -> `wiki/sources/` -> 必要时 `raw/` |
| 问题 / 风险 / 冲突 / 未决项 | `wiki/conflicts/` -> `wiki/evidence/` -> `wiki/proposals/` -> `wiki/sources/` |
| 证据 / 结果 / 实验 / 复盘 / 数据结论 | `wiki/evidence/` -> `wiki/sources/` -> 必要时 `raw/` |
| 方案 / 规划 / 草案 / 设计 | `wiki/proposals/` -> `wiki/sources/` |
| 接口 / 字段 / 规则 / 参数 / 字典 | `wiki/reference/` -> `wiki/truth/` -> `wiki/sources/` |
| 当前事实 / 稳定状态 / 明确说明 | `wiki/truth/` -> `wiki/reference/` -> `wiki/sources/` |
| SOP / 活动执行 / 流程落地 / 运营动作 | `wiki/operations/` -> `wiki/sources/` |
| 代码实现 / 架构 / 调用链 / 源码位置 | `wiki/code/traceability/` -> `wiki/code/capabilities/` -> `wiki/code/codebases/` -> `wiki/concepts/` / `wiki/entities/` -> `wiki/sources/` |
| 业务逻辑是否已实现 / 需求落在哪里 / 线上行为和代码是否一致 | `BUSINESS_CONTEXT.md` -> `wiki/concepts/` / `wiki/entities/` -> `wiki/sources/` -> `wiki/code/traceability/` -> `wiki/code/capabilities/` -> `wiki/code/codebases/` |

## 通用扩展层

`wiki/concepts/` 和 `wiki/entities/` 不是最终证据层，而是跨来源的导航和归一化层。

- `wiki/concepts/` 用于按主题扩展相关需求、规则、方案、风险和证据。
- `wiki/entities/` 用于统一业务对象、角色、系统、页面、状态、历史别名和冲突叫法。
- 当用户问题里的词和 `BUSINESS_CONTEXT.md` 或来源页口径不一致时，先按规范概念/实体归一，再回到 `wiki/sources/` 找证据。

## 专项目录层

`wiki/evidence/`、`wiki/operations/`、`wiki/proposals/`、`wiki/reference/`、`wiki/truth/`、`wiki/conflicts/` 是按问题类型组织的投影视图。它们用于缩小范围和发现候选证据，但结论仍应回到 `wiki/sources/` 或 `raw/` 核验。

不要把 `wiki/concepts/` / `wiki/entities/` 和这些专项目录层理解成互斥关系：前者负责扩展和归一，后者负责按意图定位事实视图。

## 代码证据边界

- 不要把 `wiki/code/` 作为业务规则的主证据。
- 不要把“代码里有接口/类/任务”直接写成“业务一定生效”。
- 当业务证据不足时，说清楚证据不足；不要用代码实现补成需求口径。
- 当回答涉及代码时，必须说明使用了哪些 codebase、哪些 `wiki/code/` 页面、哪些结论来自需求文档、哪些来自代码实现、哪些只是推断。

## 维护说明

本文件由 `tools/build_wiki.py` 为新 KB 生成。已有 KB 的本文件不会被 `update` 静默覆盖；如果需要升级旧 KB 的查询路由，请显式执行迁移或人工确认后再替换。
""",
    )
    write_if_missing(
        project / "docs" / "build-and-maintenance.md",
        """# 构建与维护

标准确定性命令：

```bash
uv run python tools/build_wiki.py
uv run python tools/scan_code.py
uv run python tools/build_traceability.py
uv run python tools/health.py --json
uv run python tools/build_graph.py
uv run python tools/anchor_check.py
```

摘要、实体归一、来源精修和能力判断由 agent / reviewer 完成；追踪矩阵的模型步骤必须按 `docs/traceability-contract.md` 输出 proposals，再由确定性工具合并 state 并渲染 Markdown。
本地脚本只负责扫描、生成种子页、校验和构建图谱文件。
""",
    )
    write_if_missing(
        project / "docs" / "tooling-dependencies.md",
        """# 工具依赖

必需：

- Python 3.10+
- `uv`

可选：

- 当存在 `raw-code/` 时，可使用 `graphify` 提取代码图谱。

随模板提供的 Python 脚本只做确定性处理，不调用本地模型 SDK。
""",
    )
    write_if_missing(
        project / "docs" / "implementation-workflow.md",
        """# 实施流程

执行：

```bash
uv run python tools/update_wiki.py
```

如果存在 `raw-code/` 且 graphify 可用：

```bash
uv run python tools/update_wiki.py --graphify
```

确定性种子页生成后，使用 agent / reviewer 完成来源摘要、分层页面、概念、实体和能力页。追踪证据强度只能在有可审计需求证据和代码锚点时提升。
""",
    )


def source_page_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"SHA-256:\s*`?([a-f0-9]{64})`?", text)
    if match:
        return match.group(1)
    metadata = source_page_metadata(path)
    raw_hash = metadata.get("raw_hash") if isinstance(metadata, dict) else None
    if isinstance(raw_hash, str) and re.fullmatch(r"[a-f0-9]{8,64}", raw_hash):
        return raw_hash
    return None


def source_page_metadata(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"## Source Metadata\s*```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def source_page_raw_rel(path: Path) -> str | None:
    metadata = source_page_metadata(path)
    raw_rel = metadata.get("raw_rel") if isinstance(metadata, dict) else None
    if isinstance(raw_rel, str) and raw_rel.strip():
        return raw_rel.strip()
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    match = re.search(r"Raw path:\s*`([^`]+)`", text)
    return match.group(1).strip() if match else None


def hash_matches(existing: str | None, current: str) -> bool:
    if not existing:
        return False
    return current.startswith(existing) or existing.startswith(current)


def is_operational_metadata_source(source: dict[str, object]) -> bool:
    raw_path = str(source.get("raw_path") or "")
    return (
        raw_path.startswith("raw/.obsidian-wiki-export/")
        or raw_path == "raw/export-state.json"
        or raw_path.startswith("raw/progress/")
        or raw_path.startswith("raw/rss/")
        or raw_path.startswith("raw/staging/rss/")
    )


def legacy_source_page_for(source: dict[str, object], source_dir: Path) -> Path | None:
    raw_path = str(source.get("raw_path") or "")
    slug = str(source.get("slug") or "")
    if not raw_path.endswith("/index.md") or not slug.endswith("-index"):
        return None
    return source_dir / f"{slug[:-len('-index')]}.md"


def maybe_migrate_legacy_source_page(source: dict[str, object], canonical_page: Path) -> None:
    legacy_page = legacy_source_page_for(source, canonical_page.parent)
    if legacy_page is None or not legacy_page.is_file():
        return
    raw_rel = source_page_raw_rel(legacy_page)
    if raw_rel != source.get("raw_path"):
        return
    if canonical_page.exists():
        legacy_page.unlink()
        return
    canonical_page.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_page), str(canonical_page))


def is_refreshable_seed_source_page(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return "Deterministic seed page." in text or "确定性种子页。" in text


def source_refinement_state(path: Path) -> str:
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata = source_page_metadata(path)
    state = metadata.get("ai_refinement_state") if isinstance(metadata, dict) else None
    if isinstance(state, str) and state.strip():
        return state.strip()
    if (
        "Pending AI-native summary" in text
        or "Deterministic seed page." in text
        or "待完成 AI 原生摘要" in text
        or "确定性种子页。" in text
    ):
        return "pending"
    return "applied"


def build_refinement_plan(
    project: Path,
    sources: list[dict[str, object]],
    stale_sources: list[dict[str, object]],
    orphan_source_pages: list[str],
) -> dict[str, object]:
    stale_pages = {str(item.get("page") or "") for item in stale_sources}
    required_source_pages: list[dict[str, object]] = []
    allowed_write_paths: list[str] = []
    for source in sources:
        wiki_path = f"wiki/sources/{source['slug']}.md"
        page = project / wiki_path
        state = source_refinement_state(page)
        is_stale = wiki_path in stale_pages
        if state in {"pending", "stale", "missing"} or is_stale:
            reason = "stale_raw_page" if is_stale else "new_raw_page"
            required_source_pages.append(
                {
                    "raw_path": source["raw_path"],
                    "wiki_path": wiki_path,
                    "reason": reason,
                    "required": True,
                    "current_state": "stale" if is_stale else state,
                }
            )
            allowed_write_paths.append(wiki_path)

    candidate_dependents = [
        {"path": "wiki/overview.md", "reason": "layered_summary_candidate"},
        {"path": "wiki/concepts/index.md", "reason": "linked_concept_candidate"},
        {"path": "wiki/entities/index.md", "reason": "entity_name_candidate"},
    ]
    if orphan_source_pages:
        candidate_dependents.append({"path": "wiki/sources/index.md", "reason": "source_index_candidate"})
    for item in candidate_dependents:
        if (project / item["path"]).exists():
            allowed_write_paths.append(item["path"])

    allowed_write_paths.append("staging/refinement-status.md")
    semantic_update_required = bool(required_source_pages)
    trigger = "raw_changed" if semantic_update_required else "none"
    return {
        "version": 1,
        "semantic_update_required": semantic_update_required,
        "trigger": trigger,
        "required_source_pages": required_source_pages,
        "candidate_dependents": candidate_dependents if semantic_update_required else [],
        "allowed_write_paths": sorted(dict.fromkeys(allowed_write_paths)),
        "forbidden_write_paths": ["raw/**", "raw-code/**"],
        "verification": ["tools/check_refinement.py", "tools/health.py --json", "tools/build_graph.py"],
        "user_next_command": "llm-wiki update" if semantic_update_required else "",
        "user_next_action": (
            "Continue `llm-wiki update` to complete source-grounded AI-native refinement, "
            "record refinement status, then close with health and graph checks."
            if semantic_update_required
            else ""
        ),
    }


def update_status(
    project: Path,
    sources: list[dict[str, object]],
    codebases: list[str],
    stale_sources: list[dict[str, object]],
    orphan_source_pages: list[str],
) -> None:
    status = {
        "task_id": "deterministic-build",
        "phase": "C",
        "status": "deterministic_seed_complete",
        "updated_at": utc_now(),
        "source_count": len(sources),
        "codebases": codebases,
        "stale_source_count": len(stale_sources),
        "orphan_source_page_count": len(orphan_source_pages),
        "checkpoint": "Deterministic seed is complete; semantic refinement remains part of llm-wiki update.",
        "next_command": "llm-wiki update",
        "next_action": "Continue llm-wiki update for source-grounded AI-native refinement and validation closure.",
    }
    write(project / "staging" / "refinement-status.md", "# Refinement Status\n\n```json\n" + json.dumps(status, ensure_ascii=False, indent=2) + "\n```\n")
    write(project / "staging" / "source-manifest.json", json.dumps({"generated_at": utc_now(), "sources": sources}, ensure_ascii=False, indent=2) + "\n")
    status["cjira_registry"] = update_registry_for_sources(project, sources, refresh_status=False)
    write(project / "staging" / "refinement-status.md", "# Refinement Status\n\n```json\n" + json.dumps(status, ensure_ascii=False, indent=2) + "\n```\n")
    write(
        project / "staging" / "source-drift.json",
        json.dumps(
            {
                "generated_at": utc_now(),
                "stale_sources": stale_sources,
                "orphan_source_pages": orphan_source_pages,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    plan = build_refinement_plan(project, sources, stale_sources, orphan_source_pages)
    write(project / "staging" / "refinement-plan.json", json.dumps(plan, ensure_ascii=False, indent=2) + "\n")


def main_for_project(project: Path) -> int:
    project = project.resolve()
    err = raw_evidence_preflight_failed(project)
    if err:
        raise SystemExit(err)
    raw_dir = project / "raw"
    if not raw_dir.is_dir():
        raw_dir.mkdir(parents=True, exist_ok=True)

    for rel in REQUIRED_DIRS:
        (project / rel).mkdir(parents=True, exist_ok=True)

    sources = discover_sources(raw_dir)
    stale_sources: list[dict[str, object]] = []
    for source in sources:
        page = project / "wiki" / "sources" / f"{source['slug']}.md"
        maybe_migrate_legacy_source_page(source, page)
        existing_sha = source_page_sha(page)
        created = write_if_missing(page, source_page(source, project))
        if not created and not hash_matches(existing_sha, str(source["sha256"])) and is_refreshable_seed_source_page(page):
            write(page, source_page(source, project))
            existing_sha = str(source["sha256"])
        if page.is_file():
            backfill_source_page(page, source, project)
            existing_sha = source_page_sha(page)
        if (
            not created
            and not hash_matches(existing_sha, str(source["sha256"]))
            and not is_operational_metadata_source(source)
        ):
            stale_sources.append(
                {
                    "slug": source["slug"],
                    "title": source["title"],
                    "raw_path": source["raw_path"],
                    "previous_sha256": existing_sha,
                    "current_sha256": source["sha256"],
                    "page": f"wiki/sources/{source['slug']}.md",
                }
            )

    codebases = []
    raw_code = project / "raw-code"
    if raw_code.is_dir():
        codebases = sorted(path.name for path in raw_code.iterdir() if path.is_dir() and not path.name.startswith("."))

    create_layer_pages(project)
    create_codebase_pages(project, codebases)
    create_docs(project)
    write(project / "wiki" / "index.md", index_page(sources, codebases))
    current_pages = {f"{source['slug']}.md" for source in sources}
    source_dir = project / "wiki" / "sources"
    orphan_source_pages = sorted(
        f"wiki/sources/{path.name}"
        for path in source_dir.glob("*.md")
        if path.name != "index.md" and path.name not in current_pages
    )
    update_status(project, sources, codebases, stale_sources, orphan_source_pages)

    print(f"project={project}")
    print(f"sources={len(sources)}")
    print(f"stale_sources={len(stale_sources)}")
    print(f"orphan_source_pages={len(orphan_source_pages)}")
    print(f"codebases={len(codebases)}")
    print("status=deterministic_seed_complete")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()
    return main_for_project(Path(args.project))


if __name__ == "__main__":
    raise SystemExit(main())
