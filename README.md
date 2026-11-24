# Claude Agent SDK Skill (Python)

A skill that teaches coding agents (Claude Code, OpenCode, Codex and other agents that load
`SKILL.md` skills) how to build correct, safe Python agents with the
[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview).

**Verified against `claude-agent-sdk` 0.2.188 (bundled Claude Code CLI 2.1.331) and the
official docs as of 2026-11-24.** Run `python skills/claude-agent-sdk/scripts/check_sdk.py`
to compare with your installed version.

## Install

**Plugin:**
```
/install-plugin github:tkwn2080/claude-agent-sdk-skill
```

**Manual:**
```bash
git clone https://github.com/tkwn2080/claude-agent-sdk-skill.git
cp -r claude-agent-sdk-skill/skills/claude-agent-sdk ~/.claude/skills/
```

## What it covers

| Topic | File |
|-------|------|
| Golden rules, quick start, entry points, summaries, obsolete patterns, TS-only features | `SKILL.md` |
| Permissions, rules syntax, modes, `can_use_tool`, sandbox, subagent restrictions, limits, secure deployment, checklist, ready-made profiles | `references/permissions-security.md` |
| All 10 Python hook events, inputs/outputs, `defer`, `on_failure`, timeouts, recipes | `references/hooks.md` |
| Catalog of 13 orchestration patterns with decision questions; subagents, parallel runs, forks, caps, tracking; code for each pattern | `references/subagents-orchestration.md` |
| `@tool`, schemas, results, annotations, external MCP, tool search, MCP timing | `references/tools-mcp.md` |
| Sessions, resume/fork, session store, `ClaudeSDKClient`, streaming input, file checkpointing | `references/sessions-state.md` |
| Message types, `ResultMessage`, errors, structured output, streaming, cost | `references/messages-results-errors.md` |
| System prompts, `setting_sources`, CLAUDE.md, skills, plugins, slash commands | `references/prompts-skills-plugins.md` |
| Hosting, auth, gateways/credential proxies, timeouts, OpenTelemetry | `references/deployment-gateways.md` |
| Every `ClaudeAgentOptions` field and useful env vars | `references/options-reference.md` |
| Eight complete runnable programs | `references/recipes.md` |
| Installed-version introspection | `scripts/check_sdk.py` |

## Changes in 2.0.0

- Rewritten Python-first; TypeScript reference removed (TypeScript-only features are listed in
  `SKILL.md` so you know when a doc example doesn't apply).
- Fixed outdated/incorrect guidance: `Task` → `Agent`; Python now supports
  `PostToolUseFailure`, `SubagentStart`, `PermissionRequest`, `Notification` hooks;
  `output_format` type is `json_schema`; `sandbox` is a dict; `rewind_files()` takes a message
  UUID; `thinking`/`effort` replace `max_thinking_tokens`; `dontAsk` and `auto` modes;
  `ResultError`; `on_failure="block"`; `defer` hook decision.
- Removed obsolete workarounds (stream-closed generator pattern, dummy hooks, mandatory
  `break`, background-subagent MCP limitation) and listed them as "do not use".
- New: permissions/security guide with checklists and profiles, subagent caps
  (depth/concurrency/budget), forks, chief-of-staff coordinator pattern, session store,
  tool search, MCP timing, gateway/credential-proxy setup, OpenTelemetry, recipes, `check_sdk.py`.

## Sources

- Docs: https://code.claude.com/docs/en/agent-sdk/overview (index: https://code.claude.com/docs/llms.txt)
- Python reference: https://code.claude.com/docs/en/agent-sdk/python
- SDK source and changelog: https://github.com/anthropics/claude-agent-sdk-python

## License

MIT
