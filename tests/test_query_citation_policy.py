from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_query_logic_documents_remote_source_and_local_snapshot_policy():
    query_logic_files = [
        read("skills/llm-wiki/references/query-logic.md"),
        read("dist/llm-wiki-skill/references/query-logic.md"),
    ]

    for query_logic in query_logic_files:
        assert "## 11. 证据链接展示规则" in query_logic
        assert "原文链接" in query_logic
        assert "本地快照" in query_logic
        assert "source_url" in query_logic
        assert "普通 query" in query_logic
        assert "Cwiki 评论稿" in query_logic


def test_query_logic_documents_retrieval_budget_and_limited_search():
    query_logic_files = [
        read("skills/llm-wiki/references/query-logic.md"),
        read("dist/llm-wiki-skill/references/query-logic.md"),
    ]

    for query_logic in query_logic_files:
        assert "## 2. 检索预算与限流" in query_logic
        assert "不要在整个 `wiki/` 目录上用高频词做无上限搜索" in query_logic
        assert "`rg` 输出必须限流" in query_logic
        assert "当前重点 / 规划 / 周会进展" in query_logic


def _command_reference_corpus(root: str) -> str:
    base = ROOT / root / "references"
    parts = [read(f"{root}/references/commands.md")]
    commands_dir = base / "commands"
    if commands_dir.is_dir():
        for path in sorted(commands_dir.glob("*.md")):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_command_docs_and_project_agent_rules_include_query_link_policy():
    commands = _command_reference_corpus("skills/llm-wiki")
    dist_commands = _command_reference_corpus("dist/llm-wiki-skill")
    agent_rules = read("skills/llm-wiki/assets/project-template/tools/agent_rules.py")
    dist_agent_rules = read("dist/llm-wiki-skill/assets/project-template/tools/agent_rules.py")
    template_agents = read("skills/llm-wiki/assets/project-template/AGENTS.md")
    dist_template_agents = read("dist/llm-wiki-skill/assets/project-template/AGENTS.md")

    for text in (commands, dist_commands, agent_rules, dist_agent_rules, template_agents, dist_template_agents):
        assert "Prefer remote original wiki links when source_url/page_id metadata is available" in text
        assert "Keep local raw/wiki snapshot links for reproducibility" in text
        assert "Do not expose local raw/wiki paths in Cwiki comment drafts" in text
