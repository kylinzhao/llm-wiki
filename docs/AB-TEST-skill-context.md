# llm-wiki vs llm-wiki-new A/B（dcn KB）

## 方法

1. **协议层**：按各子入口 SKILL 第一步要求，统计必须读取的文件字节数（本机 `~/.cursor/skills/llm-wiki*` vs worktree `skills-new/llm-wiki-new*`）。
2. **KB 层**：按 `references/commands/doctor.md` 列出的项目文件统计（full / lite 两套）。
3. **功能层**：在 `dcn-llm-wiki` 运行 `tools/doctor.py`、`tools/health.py`；用固定问题检查 query 证据是否可答。
4. **未覆盖**：Cursor 新会话 Context 面板 Conversation token（需人工开两局对比）。

复现：

```bash
cd ~/.config/superpowers/worktrees/llm-wiki-skill/optimize-skill-context
python3 scripts/ab_test_skill_context.py
```

## 结果摘要（2026-06-02）

见 `staging/ab-test-skill-context.json`。
