# LLM Wiki Project Rules

## Evidence Boundaries

- `raw/` is immutable source evidence. Read it; do not edit it.
- `raw-code/` is immutable code evidence. Read it; do not edit it.
- Do not commit `raw/` unless the owner explicitly asks for that.
- Do not write secrets, cookies, tokens, private keys, or full sensitive config values into `wiki/`.

## Build Commands

Use these deterministic commands before and after AI-native refinement:

```bash
uv run python tools/build_wiki.py
uv run python tools/scan_code.py
uv run python tools/build_traceability.py
uv run python tools/health.py --json
uv run python tools/build_graph.py
```

Use Codex-native work for summaries, entity normalization, business judgment, implementation judgment, and final traceability strength.

