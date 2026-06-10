import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def manifest(rel: str) -> dict:
    return json.loads(read(rel))


def test_command_manifest_is_installed_in_source_and_dist_bundles():
    for rel in [
        "skills/llm-wiki/references/commands/manifest.json",
        "dist/llm-wiki-skill/references/commands/manifest.json",
    ]:
        data = manifest(rel)
        assert data["schemaVersion"] == "llm-wiki-command-manifest/v1"
        assert data["commands"]["pull"] == {
            "command": "llm-wiki pull",
            "readOnly": False,
            "mutatesEvidenceCache": True,
            "publishes": False,
            "requiresModel": False,
            "supportedProviders": ["cursor", "opencode"],
        }
        assert data["commands"]["query"]["readOnly"] is True
        assert data["commands"]["update"]["publishes"] is True


def test_cloud_consumed_commands_document_result_envelope():
    for rel in [
        "skills/llm-wiki/references/commands/pull.md",
        "skills/llm-wiki/references/commands/update.md",
        "dist/llm-wiki-skill/references/commands/pull.md",
        "dist/llm-wiki-skill/references/commands/update.md",
    ]:
        text = read(rel)
        assert "llm-wiki-job-result-json" in text
        assert "llm-wiki-job-result/v1" in text
        assert "schemaVersion" in text
        assert "issues" in text
        assert "phases" in text
