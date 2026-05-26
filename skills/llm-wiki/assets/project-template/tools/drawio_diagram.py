#!/usr/bin/env python3
"""Extract text evidence from draw.io diagrams.

The converter is intentionally deterministic and conservative. It turns the
mxGraph cells that draw.io stores inside ``.drawio`` files into a Mermaid
flowchart so the KB text layer can retain process semantics without requiring
image OCR.
"""

from __future__ import annotations

import base64
import html
import re
import zlib
from dataclasses import dataclass
from urllib.parse import unquote
from xml.etree import ElementTree


@dataclass(frozen=True)
class DrawioDiagram:
    name: str
    mermaid: str
    node_count: int
    edge_count: int


def decode_drawio_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if stripped.startswith("<"):
        return stripped
    try:
        payload = base64.b64decode(stripped)
    except Exception:
        return stripped
    for wbits in (-15, zlib.MAX_WBITS):
        try:
            decoded = zlib.decompress(payload, wbits).decode("utf-8", errors="replace")
            return unquote(decoded)
        except Exception:
            continue
    try:
        return payload.decode("utf-8", errors="replace")
    except Exception:
        return stripped


def clean_label(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def mermaid_quote(value: str) -> str:
    text = clean_label(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return text or "未命名节点"


def mermaid_id(cell_id: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", cell_id or "")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"n{index}_{cleaned}" if cleaned else f"n{index}"
    return cleaned


def graph_models(xml_text: str) -> list[ElementTree.Element]:
    root = ElementTree.fromstring(xml_text)
    if root.tag == "mxGraphModel":
        return [root]
    models: list[ElementTree.Element] = []
    for diagram in root.findall(".//diagram"):
        child_model = diagram.find("mxGraphModel")
        if child_model is not None:
            child_model.set("_diagram_name", diagram.get("name") or "")
            models.append(child_model)
            continue
        decoded = decode_drawio_text(diagram.text or "")
        if not decoded.strip().startswith("<"):
            continue
        try:
            model = ElementTree.fromstring(decoded)
        except ElementTree.ParseError:
            continue
        if model.tag == "mxGraphModel":
            model.set("_diagram_name", diagram.get("name") or "")
            models.append(model)
    return models


def model_to_mermaid(model: ElementTree.Element, fallback_name: str, ordinal: int) -> DrawioDiagram | None:
    cells = model.findall(".//mxCell")
    vertices: dict[str, tuple[str, str]] = {}
    edges: list[tuple[str, str, str]] = []
    id_map: dict[str, str] = {}
    edge_labels: dict[str, str] = {}

    for index, cell in enumerate(cells, start=1):
        cell_id = cell.get("id") or f"cell-{index}"
        parent_id = cell.get("parent") or ""
        if cell.get("vertex") == "1" and parent_id:
            label = clean_label(cell.get("value") or "")
            if label:
                edge_labels.setdefault(parent_id, label)
        if cell.get("vertex") == "1":
            label = mermaid_quote(cell.get("value") or "")
            if label == "未命名节点":
                continue
            node_id = mermaid_id(cell_id, index)
            id_map[cell_id] = node_id
            vertices[cell_id] = (node_id, label)

    for cell in cells:
        if cell.get("edge") != "1":
            continue
        source = cell.get("source") or ""
        target = cell.get("target") or ""
        if source not in id_map or target not in id_map:
            continue
        label = clean_label(cell.get("value") or "") or edge_labels.get(cell.get("id") or "", "")
        edges.append((id_map[source], id_map[target], label))

    if not vertices and not edges:
        return None

    lines = ["flowchart TD"]
    for _, (node_id, label) in sorted(vertices.items(), key=lambda item: item[1][0]):
        lines.append(f'  {node_id}["{label}"]')
    for source, target, label in edges:
        if label:
            label_text = label.replace("|", "/").replace('"', "'")
            lines.append(f'  {source} -->|"{label_text}"| {target}')
        else:
            lines.append(f"  {source} --> {target}")

    name = model.get("_diagram_name") or fallback_name or f"diagram-{ordinal}"
    return DrawioDiagram(name=name, mermaid="\n".join(lines), node_count=len(vertices), edge_count=len(edges))


def drawio_to_mermaid(xml_text: str, fallback_name: str = "") -> list[DrawioDiagram]:
    decoded = decode_drawio_text(xml_text)
    if not decoded.strip().startswith("<"):
        return []
    try:
        models = graph_models(decoded)
    except ElementTree.ParseError:
        return []
    diagrams: list[DrawioDiagram] = []
    for ordinal, model in enumerate(models, start=1):
        diagram = model_to_mermaid(model, fallback_name, ordinal)
        if diagram is not None:
            diagrams.append(diagram)
    return diagrams
