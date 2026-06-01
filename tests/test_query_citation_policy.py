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
        assert "## 10. 证据链接展示规则" in query_logic
        assert "原文链接" in query_logic
        assert "本地快照" in query_logic
        assert "source_url" in query_logic
        assert "普通 query" in query_logic
        assert "Cwiki 评论稿" in query_logic


def test_command_docs_and_project_agent_rules_include_query_link_policy():
    commands = read("skills/llm-wiki/references/commands.md")
    dist_commands = read("dist/llm-wiki-skill/references/commands.md")
    agent_rules = read("skills/llm-wiki/assets/project-template/tools/agent_rules.py")
    dist_agent_rules = read("dist/llm-wiki-skill/assets/project-template/tools/agent_rules.py")
    template_agents = read("skills/llm-wiki/assets/project-template/AGENTS.md")
    dist_template_agents = read("dist/llm-wiki-skill/assets/project-template/AGENTS.md")

    for text in (commands, dist_commands, agent_rules, dist_agent_rules, template_agents, dist_template_agents):
        assert "Prefer remote original wiki links when source_url/page_id metadata is available" in text
        assert "Keep local raw/wiki snapshot links for reproducibility" in text
        assert "Do not expose local raw/wiki paths in Cwiki comment drafts" in text
