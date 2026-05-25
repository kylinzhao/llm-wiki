# Vendored guazi-sso-login

Source: https://git.guazi-corp.com/yanliwan/agent-skill/tree/master/guazi-sso-login
Repository: https://git.guazi-corp.com/yanliwan/agent-skill.git
Commit: 9d17bae93f22c2d39180c82237dd1ff7403b6dfa

This copy is bundled so llm-wiki can authenticate Cwiki without asking users for an internal skill path.

Local compatibility patch:
- Replaced `@dataclass(slots=True)` with `@dataclass` so the bundled engine tool works with Python 3.9.
