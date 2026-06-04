from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_refine_command_is_documented_and_routed_in_skill_bundle():
    commands_index = read("skills/llm-wiki/references/commands.md")
    main_skill = read("skills/llm-wiki/SKILL.md")
    update_command = read("skills/llm-wiki/references/commands/update.md")
    refine_command = read("skills/llm-wiki/references/commands/refine.md")
    refine_entry = read("skills/llm-wiki-refine/SKILL.md")

    assert "| `llm-wiki refine` | [`refine.md`](./commands/refine.md) |" in commands_index
    assert "- `llm-wiki refine`" in main_skill
    assert "update 可以自动进入 source refinement" in update_command
    assert "主动触发" in refine_command
    assert "commit and push" in refine_command
    assert "references/commands/refine.md" in refine_entry
    assert "llm-wiki refine" in refine_entry


def test_dist_bundle_contains_refine_command_contract():
    commands_index = read("dist/llm-wiki-skill/references/commands.md")
    refine_command = read("dist/llm-wiki-skill/references/commands/refine.md")

    assert "| `llm-wiki refine` | [`refine.md`](./commands/refine.md) |" in commands_index
    assert "主动触发" in refine_command
    assert "commit and push" in refine_command


def test_install_script_does_not_prune_refine_entry():
    install_script = read("install.sh")
    deprecated_block = install_script.split("DEPRECATED_SKILLS=(", 1)[1].split(")", 1)[0]

    assert '"llm-wiki-refine"' not in deprecated_block
