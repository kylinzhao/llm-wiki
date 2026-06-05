from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_code_trace_command_is_documented_and_routed_in_skill_bundle():
    commands_index = read("skills/llm-wiki/references/commands.md")
    shared_command = read("skills/llm-wiki/references/commands/_shared.md")
    main_skill = read("skills/llm-wiki/SKILL.md")
    update_command = read("skills/llm-wiki/references/commands/update.md")
    code_trace_command = read("skills/llm-wiki/references/commands/code-trace.md")
    code_trace_entry = read("skills/llm-wiki-code-trace/SKILL.md")

    assert "| `llm-wiki code-trace` | [`code-trace.md`](./commands/code-trace.md) |" in commands_index
    assert "| `llm-wiki code-trace` |" in shared_command
    assert "- `llm-wiki code-trace`" in main_skill
    assert "llm-wiki code-trace refine" in update_command
    assert "Do not label the command complete until AI refinement is actually complete" in code_trace_command
    assert "Distributed execution is allowed" in code_trace_command
    assert "llm-wiki code-trace rebuild" in code_trace_command
    assert "llm-wiki code-trace doctor" in code_trace_command
    assert "references/commands/code-trace.md" in code_trace_entry
    assert "llm-wiki code-trace" in code_trace_entry


def test_dist_bundle_contains_code_trace_command_contract():
    commands_index = read("dist/llm-wiki-skill/references/commands.md")
    shared_command = read("dist/llm-wiki-skill/references/commands/_shared.md")
    main_skill = read("dist/llm-wiki-skill/SKILL.md")
    update_command = read("dist/llm-wiki-skill/references/commands/update.md")
    code_trace_command = read("dist/llm-wiki-skill/references/commands/code-trace.md")

    assert "| `llm-wiki code-trace` | [`code-trace.md`](./commands/code-trace.md) |" in commands_index
    assert "| `llm-wiki code-trace` |" in shared_command
    assert "- `llm-wiki code-trace`" in main_skill
    assert "llm-wiki code-trace refine" in update_command
    assert "Do not label the command complete until AI refinement is actually complete" in code_trace_command


def test_install_script_does_not_prune_code_trace_entry():
    install_script = read("install.sh")
    deprecated_block = install_script.split("DEPRECATED_SKILLS=(", 1)[1].split(")", 1)[0]

    assert '"llm-wiki-code-trace"' not in deprecated_block
