from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pull_command_is_documented_and_routed_in_skill_bundle():
    commands_index = read("skills/llm-wiki/references/commands.md")
    shared_command = read("skills/llm-wiki/references/commands/_shared.md")
    main_skill = read("skills/llm-wiki/SKILL.md")
    update_command = read("skills/llm-wiki/references/commands/update.md")
    pull_command = read("skills/llm-wiki/references/commands/pull.md")
    pull_entry = read("skills/llm-wiki-pull/SKILL.md")

    assert "| `llm-wiki pull` | [`pull.md`](./commands/pull.md) |" in commands_index
    assert "| `llm-wiki pull` |" in shared_command
    assert "- `llm-wiki pull`" in main_skill
    assert "engine-v1.0.17" in update_command
    assert "llm-wiki pull" in update_command
    assert "local-only" in pull_command
    assert "now - last_update_time" in pull_command
    assert "Verdict" in pull_command
    assert "1 day" in pull_command or "1 天" in pull_command
    assert "wiki/" in pull_command and "staging/" in pull_command and "graph/" in pull_command
    assert "references/commands/pull.md" in pull_entry
    assert "llm-wiki pull" in pull_entry
    assert "local-only" in pull_entry
    assert "建议下一步" in pull_entry


def test_dist_bundle_contains_pull_command_contract():
    commands_index = read("dist/llm-wiki-skill/references/commands.md")
    shared_command = read("dist/llm-wiki-skill/references/commands/_shared.md")
    main_skill = read("dist/llm-wiki-skill/SKILL.md")
    update_command = read("dist/llm-wiki-skill/references/commands/update.md")
    pull_command = read("dist/llm-wiki-skill/references/commands/pull.md")

    assert "| `llm-wiki pull` | [`pull.md`](./commands/pull.md) |" in commands_index
    assert "| `llm-wiki pull` |" in shared_command
    assert "- `llm-wiki pull`" in main_skill
    assert "engine-v1.0.17" in update_command
    assert "llm-wiki pull" in update_command
    assert "local-only" in pull_command
    assert "now - last_update_time" in pull_command


def test_install_script_does_not_prune_pull_entry():
    install_script = read("install.sh")
    deprecated_block = install_script.split("DEPRECATED_SKILLS=(", 1)[1].split(")", 1)[0]

    assert '"llm-wiki-pull"' not in deprecated_block
