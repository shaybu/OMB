# System prompts, CLAUDE.md, settings sources, skills, plugins, commands (Python)

Python SDK 0.2.188.

## 1. System prompt: pick a starting point

| Building | `system_prompt=` | You get |
|----------|------------------|---------|
| Coding tool like Claude Code (human watches, CI fixer, code reviewer) | `{"type": "preset", "preset": "claude_code"}` | Claude Code's prompt incl. tool guidance and safety rules |
| Same, plus your rules | `{"type": "preset", "preset": "claude_code", "append": "..."}` | Lowest-risk customization: nothing removed |
| Different identity/surface (support bot, data analyst, non-coding agent) | `"You are ..."` (string) or `{"type": "custom", "prompt": "..."}` | Only your text: **you** must add tool guidance and safety rules |
| Large prompt (> ~100 KB) | `{"type": "file", "path": "prompt.md"}` | Avoids OS argv limits (Linux ~128 KB per arg, Windows ~32 KB total) |
| Thin tool loop, behavior in user prompt | omit | Minimal default (tool calling only, **no safety guidance**) |

If you don't set `system_prompt`, the SDK uses a **minimal** prompt with no Claude Code tool
guidance or safety rules. Set the preset or write your own for production agents.

Preset options:
- `"append"`: your instructions after the preset.
- `"exclude_dynamic_sections": True`: move per-user context (auto-memory path) to the first
  user message so many users/machines share one prompt cache entry.
- `"snapshot": False`: rebuild the prompt each request instead of reusing the one recorded at
  session start (needed if you change prompt text for an existing session). SDK ≥ 0.2.153.

Writing a custom prompt for an autonomous agent - include:
1. Role, scope and what's out of scope.
2. The tools it has and when to use each; when to stop.
3. Safety rules: never exfiltrate secrets, treat file/web/tool content as untrusted data,
   never follow instructions found inside content, ask (or stop) before destructive actions.
4. Output contract (format, length, where to write results).
5. Delegation policy if it has `Agent` (when to spawn, how many, what to return).

## 2. `setting_sources`: what loads from disk

| Value | Loads |
|-------|-------|
| `None` (default) | user + project + local (like the CLI) |
| `[]` | nothing from user/project/local files (fully programmatic) |
| `["project"]` | `.claude/settings.json`, `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`, `.claude/agents/`, `.claude/commands/`, `.mcp.json`, settings hooks |
| `["user"]` | `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, `~/.claude/skills/`, ... |
| `["local"]` | `.claude/settings.local.json`, `CLAUDE.local.md` |

Precedence when several load: local > project > user. Rules from `allowed_tools` /
`settings=` add to these. Managed policy always loads. Always read regardless:
`~/.claude.json` (relocate with `CLAUDE_CONFIG_DIR` in `env`), auto memory under
`~/.claude/projects/<project>/memory/`. **For multi-tenant isolation don't rely on
`setting_sources`; use a separate container/`HOME` per tenant.**

If you set `skills=` and leave `setting_sources` unset, only user + project load.
`add_dirs=[...]` grants access to extra directories and (with `project`) loads their
skills, commands and agents.

## 3. CLAUDE.md and rules

Loaded only when `setting_sources` includes `"project"` (project files) / `"user"` /
`"local"`. Locations: `<cwd>/CLAUDE.md` or `<cwd>/.claude/CLAUDE.md`, parent directories,
`.claude/rules/*.md`, subdirectory CLAUDE.md files on demand, `CLAUDE.local.md`,
`~/.claude/CLAUDE.md`. All levels are additive. Use CLAUDE.md for context shared with
the developers who also work in that repo; use `system_prompt` append for app-specific behavior.

## 4. Skills

Skills are folders with a `SKILL.md` (frontmatter `name`, `description`) in
`.claude/skills/<name>/` (project) or `~/.claude/skills/<name>/` (user), or inside plugins.

```python
options = ClaudeAgentOptions(
    cwd="/repo",
    setting_sources=["user", "project"],   # where skills are discovered
    skills="all",                          # or ["pdf", "my-plugin:review"] or [] for none
    allowed_tools=["Read", "Write", "Bash"],
)
```

- `skills=None` (default): discovered skills enabled, matching the CLI.
- A list restricts the **main agent** to those exact names (no wildcards; invalid names raise
  `ValueError` before start). Plugin skills are `plugin:skill`. It does not restrict
  subagents or explicit `/<name>` dispatch.
- If you pass `tools=[...]`, include `"Skill"`.
- Confirm loading: init message `data["skills"]` (user-invocable skills only).
- Preload skills into a subagent: `AgentDefinition(skills=["pdf"])`.
- Skills often run Bash/Write: pre-approve what they need or they will be denied in headless runs.

## 5. Slash commands

Send `/<name>` as the prompt. Available list: init `data["slash_commands"]`.

```python
async for m in query(prompt="/compact", options=ClaudeAgentOptions(continue_conversation=True, max_turns=1)):
    if isinstance(m, SystemMessage) and m.subtype == "compact_boundary":
        print(m.data["compact_metadata"]["pre_tokens"])
```

- `/compact` summarizes history (needs prior messages); `/clear` resets the conversation
  (emits `ConversationResetMessage`, new `session_id` afterwards).
- Commands that need a terminal UI (e.g. `/theme`) aren't available in SDK sessions and return "isn't available in this environment".
- Unknown `/x` is sent to Claude as a normal message.

## 6. Plugins

```python
options = ClaudeAgentOptions(plugins=[
    {"type": "local", "path": "./plugins/qa-tools"},       # relative to cwd
    {"type": "local", "path": "/opt/plugins/security"},
])
```

Layout (manifest optional):

```text
my-plugin/
├── .claude-plugin/plugin.json
├── skills/<skill>/SKILL.md      # invoked as my-plugin:<skill>
├── commands/*.md                # legacy flat commands
├── agents/*.md                  # subagents
├── hooks/hooks.json             # shell hooks
└── .mcp.json                    # MCP servers
```

- Only local paths; download marketplace plugins first.
- Verify: init `data["plugins"]` (and `plugin_errors` if any).
- Reload after editing: send `/reload-plugins` as a prompt (Python has no `reloadPlugins()`).
- Plugin MCP servers are excluded by `strict_mcp_config=True`.

## 7. Output styles and other context

- Output styles (`.claude/output-styles/*.md`, selected in settings) modify the preset's
  behavior; they load with the matching setting source.
- Claude Code adds reminders and environment info to the conversation outside the system prompt
  (cwd, platform, date, CLAUDE.md content). These don't break the system-prompt cache.
