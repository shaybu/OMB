---
name: claude-agent-sdk
description: >
  Build, review, or debug Python agents with the Claude Agent SDK (package
  claude-agent-sdk, import claude_agent_sdk). Use when code calls query(),
  ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition, HookMatcher, @tool or
  create_sdk_mcp_server, or when the task is: building an autonomous agent,
  adding custom tools or MCP servers, writing hooks, restricting tools and
  permissions, sandboxing, running subagents in parallel, orchestrating
  multiple agents, managing sessions, structured output, file checkpointing,
  cost limits, or deploying an agent. Python-first;
  notes which features are TypeScript-only.
---

# Claude Agent SDK (Python)

The Agent SDK runs Claude Code's agent loop as a library: built-in tools, permissions,
hooks, subagents, sessions, MCP, skills and plugins. You do NOT write the tool loop;
the agent plans, calls tools and decides when it is done.

> **Verified against:** `claude-agent-sdk` **0.2.188** (bundles Claude Code CLI **2.1.331**)
> and the official docs at `https://code.claude.com/docs/en/agent-sdk/` on **2026-11-24**.
> The SDK ships often. If something here disagrees with the installed version, the installed
> version wins: run `python scripts/check_sdk.py` (in this skill folder) to print the real
> option fields, hook events and permission modes.

## How to use this skill (any AI agent)

Follow these steps in order for every Agent SDK task:

1. Read the **Golden rules** below. They apply to every task.
2. If you can run commands, run `python scripts/check_sdk.py` once to see the installed SDK
   version, option fields, hook events and permission modes. Use only names it lists.
3. Find your task in this table and read **only** that reference file (all paths are relative
   to this skill's folder):

   | Task | Read |
   |------|------|
   | First agent / basic `query()` / chat app | this file only |
   | Restrict tools, approvals, sandbox, "make it safe", deploy to production | `references/permissions-security.md` |
   | Intercept / block / log / modify tool calls | `references/hooks.md` |
   | Choosing an app architecture, subagents, parallel work, multi-agent orchestration | `references/subagents-orchestration.md` (start at the §1 pattern catalog) |
   | Custom tools, MCP servers | `references/tools-mcp.md` |
   | Resume, fork, multi-turn, interrupt, images, undo file changes | `references/sessions-state.md` |
   | Parse messages, errors, JSON output, streaming, cost | `references/messages-results-errors.md` |
   | System prompt, CLAUDE.md, skills, plugins, slash commands | `references/prompts-skills-plugins.md` |
   | Hosting, API keys/proxies, timeouts, telemetry | `references/deployment-gateways.md` |
   | Look up one option or env var | `references/options-reference.md` |
   | Need a complete working program to start from | `references/recipes.md` |

4. Start from the closest example in that file and change it. Don't invent option names,
   hook events or message fields; if something isn't in this skill or in `check_sdk.py`
   output, look it up in the official docs (Sources at the end) instead of guessing.
5. Before finishing, check your code against the Golden rules again, and make sure every run
   has `max_turns`, a budget, an explicit `permission_mode`, and `try/except` around `query()`.

Conventions in this skill: all code is Python 3.10+ and async; `options` means a
`ClaudeAgentOptions` instance; "the CLI" means the Claude Code binary the SDK starts for you;
tables marked "TypeScript-only" describe features you **cannot** use from Python.

## Golden rules (read before writing any code)

These are the mistakes models make most often with this SDK. Follow them exactly.

1. **Package and import names:** `pip install claude-agent-sdk`, `import claude_agent_sdk`.
   Never `claude_code_sdk` / `ClaudeCodeOptions` (old names, removed).
2. **Everything is async.** Wrap code in `async def main()` and call `asyncio.run(main())`.
3. **The subagent tool is `Agent`**, not `Task`. Put `"Agent"` in `allowed_tools` when you
   define subagents. (The init message still lists it as `Task`; match both names when
   detecting subagent calls.)
4. **`allowed_tools` auto-approves; it does NOT restrict.** Unlisted tools are still
   available. To remove a tool, use `disallowed_tools=["Bash"]` or pass an explicit
   `tools=[...]` list. To make "only these tools, deny the rest" use
   `allowed_tools=[...]` + `permission_mode="dontAsk"`.
5. **`AgentDefinition` fields are camelCase** (`disallowedTools`, `maxTurns`,
   `permissionMode`, `mcpServers`). `ClaudeAgentOptions` fields are snake_case.
   A snake_case keyword on `AgentDefinition` raises `TypeError`.
6. **Structured output type is `"json_schema"`**: `output_format={"type": "json_schema", "schema": {...}}`.
   Read the result from `ResultMessage.structured_output`.
7. **`sandbox` is a dict**, not a bool: `sandbox={"enabled": True, ...}`.
8. **`rewind_files(user_message_id)` needs a message UUID**, and you must set
   `enable_file_checkpointing=True` plus `extra_args={"replay-user-messages": None}` to get one.
9. **Prefer `thinking={...}` / `effort=`** over the deprecated `max_thinking_tokens`.
10. **A single-shot `query()` raises `ResultError` after yielding an error result**
    (max turns, budget, API error). Wrap the `async for` in `try/except`.
11. **Hook callbacks return a dict** (`{}` = no opinion). Use `continue_` and `async_`
    (with underscore) in Python. Always put decisions inside `hookSpecificOutput` with
    `hookEventName`.
12. **Python supports only 10 hook events** (see Hooks below). `SessionStart`, `SessionEnd`,
    `PostToolBatch`, `TeammateIdle`, `TaskCreated`, etc. are TypeScript-only as SDK callbacks.
13. **Do not `break` out of `receive_response()` / `receive_messages()`** unless you are
    done with the client; let `receive_response()` end at the `ResultMessage` by itself.
14. **The default system prompt is minimal** (no Claude Code safety/tool guidance). For a
    coding agent use `system_prompt={"type": "preset", "preset": "claude_code", "append": "..."}`.
15. **Always bound a run**: set `max_turns` and `max_budget_usd`, and cap subagents with
    `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` / `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` in `env`.

Workarounds that are **obsolete** in current versions (do not add them to new code) are
listed in [Obsolete patterns](#obsolete-patterns-do-not-use).

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install claude-agent-sdk          # bundles the Claude Code CLI; Python 3.10+
export ANTHROPIC_API_KEY=sk-ant-...   # or a gateway/proxy, see deployment-gateways.md
```

## Quick start

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock

async def main():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep", "Edit"],   # auto-approved
        permission_mode="acceptEdits",                     # auto-approve file edits in cwd
        cwd="/path/to/project",
        max_turns=30,
        max_budget_usd=2.0,
    )
    try:
        async for message in query(prompt="Find and fix the bug in auth.py", options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print(f"[{message.subtype}] cost=${message.total_cost_usd or 0:.4f}")
    except Exception as e:  # ResultError on error_max_turns / error_max_budget_usd / API errors
        print(f"Run ended with an error: {e}")

asyncio.run(main())
```

## Choose the entry point

| Need | Use |
|------|-----|
| One task, one prompt, no follow-up | `query(prompt=..., options=...)` |
| Multi-turn chat in one process, interrupts, change model/permission mode mid-run, MCP control, rewind files | `ClaudeSDKClient` |
| Continue the most recent session after a restart | `query(..., options=ClaudeAgentOptions(continue_conversation=True))` |
| Continue a specific session | `ClaudeAgentOptions(resume=session_id)` |
| Branch a session | `resume=session_id, fork_session=True` or `fork_session(session_id)` |

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage

async with ClaudeSDKClient(options=ClaudeAgentOptions(allowed_tools=["Read", "Grep"])) as client:
    await client.query("Read the auth module")          # async with already connected
    async for msg in client.receive_response():          # stops after the ResultMessage
        ...
    await client.query("Now list every caller of login()")   # same session, full context
    async for msg in client.receive_response():
        ...
```

Client methods: `query`, `receive_response`, `receive_messages`, `interrupt`,
`set_permission_mode`, `set_model`, `rewind_files`, `get_mcp_status`, `get_context_usage`,
`reconnect_mcp_server`, `toggle_mcp_server`, `stop_task`, `get_server_info`, `disconnect`.
After `interrupt()`, drain the interrupted turn with `receive_response()` before reading
the next answer.

## Messages you will receive

| Type | When | Key fields |
|------|------|------------|
| `SystemMessage` (`subtype="init"`) | First | `data["session_id"]`, `data["tools"]`, `data["mcp_servers"]`, `data["skills"]`, `data["slash_commands"]` |
| `AssistantMessage` | Each model reply | `content` (`TextBlock`, `ThinkingBlock`, `ToolUseBlock`), `parent_tool_use_id` (set inside subagents), `usage` |
| `UserMessage` | Tool results, replayed prompts | `content` (`ToolResultBlock`), `uuid`, `tool_use_result` |
| `TaskStartedMessage` / `TaskProgressMessage` / `TaskNotificationMessage` | Background subagents, background Bash, Monitor | `task_id`, `status`, `summary`, `usage` |
| `StreamEvent` | Only with `include_partial_messages=True` | raw API stream `event` |
| `RateLimitEvent` | Rate-limit state changes | `rate_limit_info.status` |
| `ResultMessage` | Last message of a turn | `subtype`, `result`, `structured_output`, `is_error`, `stop_reason`, `terminal_reason`, `total_cost_usd`, `model_usage`, `num_turns`, `session_id`, `permission_denials` |

`ResultMessage.subtype` is one of `success`, `error_during_execution`, `error_max_turns`,
`error_max_budget_usd`, `error_max_structured_output_retries`. `success` can still have
`is_error=True` (refusal or API error) - check `stop_reason` then `terminal_reason`.
Details: [references/messages-results-errors.md](references/messages-results-errors.md).

## Built-in tools (names to use in rules)

`Read`, `Write`, `Edit`, `NotebookEdit`, `Glob`, `Grep`, `Bash`, `Monitor`, `WebFetch`,
`WebSearch`, `Agent` (subagents), `Skill`, `AskUserQuestion`, `TodoWrite`, `TaskCreate`,
`TaskUpdate`, `TaskGet`, `TaskList`, `TaskOutput`, `TaskStop`, `ToolSearch`, `ExitPlanMode`,
`ListMcpResources`, `ReadMcpResource`, `SendMessage`. MCP tools are `mcp__<server>__<tool>`.
(`BashOutput`/`KillBash` from old docs are replaced by `TaskOutput`/`TaskStop`.)

Read-only tools (`Read`, `Glob`, `Grep`, MCP tools with `readOnlyHint=True`) run in
parallel inside one turn; `Edit`, `Write`, `Bash` run sequentially.

## Permissions and restrictions (summary)

Every tool call is checked in this order; the first step that decides wins:

1. **Hooks** (`PreToolUse`) - can deny, ask, allow, defer, or rewrite input. A hook `allow` does not skip deny/ask rules.
2. **Deny rules** - `disallowed_tools` + settings files. Applies even in `bypassPermissions`.
3. **Ask rules** - from settings; go to `can_use_tool`.
4. **Permission mode** - `default`, `acceptEdits`, `plan`, `dontAsk`, `bypassPermissions`, `auto`.
5. **Allow rules** - `allowed_tools` + settings.
6. **`can_use_tool` callback** - only for calls still undecided (skipped in `dontAsk`: denied).

Rule syntax: `"Bash"` (whole tool), `"Bash(npm test *)"` (command prefix), `"Edit(/src/**)"`
(path inside cwd), `"Edit(//etc/**)"` (absolute path), `"mcp__github__*"` (all tools of one
server), `"Agent(fork)"` (a subagent type), deny-only globs `"*"` / `"mcp__*"`.
Use `Edit(...)` for all file-writing tools; `Write(path)` rules never match.

Recommended presets:

```python
# Locked-down headless agent: only these tools may run, everything else is denied.
ClaudeAgentOptions(allowed_tools=["Read", "Glob", "Grep"], permission_mode="dontAsk")

# Coding agent in a sandboxed workspace with hard guards.
ClaudeAgentOptions(
    permission_mode="acceptEdits",
    allowed_tools=["Read", "Glob", "Grep", "Bash(pytest *)", "Bash(git diff *)"],
    disallowed_tools=["WebFetch", "WebSearch", "Bash(git push *)", "Bash(rm -rf *)", "Edit(//etc/**)"],
    sandbox={"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False},
)
```

Never combine `bypassPermissions` with untrusted input; `allowed_tools` does not constrain it.
Full guide with best practices and checklists:
[references/permissions-security.md](references/permissions-security.md).

## Hooks (summary)

Python callback hook events (exactly these 10): `PreToolUse`, `PostToolUse`,
`PostToolUseFailure`, `UserPromptSubmit`, `Stop`, `SubagentStart`, `SubagentStop`,
`PreCompact`, `Notification`, `PermissionRequest`.

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

async def block_secrets(input_data, tool_use_id, context):
    path = input_data["tool_input"].get("file_path", "")
    if path.endswith((".env", ".pem")):
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",           # allow | deny | ask | defer
            "permissionDecisionReason": "Secrets files are protected",
        }}
    return {}                                        # no opinion

options = ClaudeAgentOptions(hooks={
    "PreToolUse": [HookMatcher(matcher="Write|Edit|Read", hooks=[block_secrets],
                               timeout=30, on_failure="block")],
})
```

Matching hooks run **in parallel**; the most restrictive decision wins
(`deny` > `defer` > `ask` > `allow`). `on_failure="block"` (SDK ≥ 0.2.177) makes a crashing
guard block instead of silently allowing. Full reference:
[references/hooks.md](references/hooks.md).

## Subagents, parallelism, orchestration (summary)

```python
from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Glob", "Grep", "Agent"],
    agents={
        "security-reviewer": AgentDefinition(
            description="Security review specialist. Use for auth, injection and secrets issues.",
            prompt="You are a security reviewer. Report findings with file:line and severity.",
            tools=["Read", "Glob", "Grep"],      # read-only
            model="sonnet",                        # alias or full ID, or "inherit"
            maxTurns=20,
        ),
        "test-runner": AgentDefinition(
            description="Runs the test suite and summarizes failures.",
            prompt="Run tests and report failing tests with the likely cause.",
            tools=["Bash", "Read", "Grep"],
        ),
    },
    max_budget_usd=5.0,
    env={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1", "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "5"},
)
```

- Subagents start with a **fresh context**: only their `prompt` plus the Agent tool's task
  text. Put file paths and decisions in the task text.
- From the main agent, subagents run **in the background by default** (`async_launched`);
  ask Claude to "wait for it" or set `background=True` explicitly to control this.
- Several subagents run **concurrently** (default cap 20). Ask for parallel work explicitly:
  "Run security-reviewer and test-runner in parallel".
- There are 13 supported orchestration patterns (single agent, subagents, parallel subagents,
  fan-out, pipeline, router, evaluator loop, best-of-N forks, human gates, per-user sessions,
  background workers, coordinator + persistent workers, peer messaging). **Don't default to
  one**: use the pattern catalog and decision questions in
  `references/subagents-orchestration.md` §1 to choose from the app's requirements.

Full guide: [references/subagents-orchestration.md](references/subagents-orchestration.md).

## Custom tools and MCP (summary)

```python
import os
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, ToolAnnotations

@tool("get_order", "Look up an order by ID", {"order_id": str},
      annotations=ToolAnnotations(readOnlyHint=True))
async def get_order(args: dict[str, Any]) -> dict[str, Any]:
    try:
        order = await fetch_order(args["order_id"])          # your code
        return {"content": [{"type": "text", "text": str(order)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Lookup failed: {e}"}], "is_error": True}

shop = create_sdk_mcp_server(name="shop", version="1.0.0", tools=[get_order])

options = ClaudeAgentOptions(
    mcp_servers={
        "shop": shop,                                                     # in-process
        "github": {"type": "http", "url": "https://mcp.example.com/mcp",
                   "headers": {"Authorization": f"Bearer {os.environ['GH_TOKEN']}"}},  # remote
        "db": {"command": "python", "args": ["db_server.py"]},             # stdio
    },
    allowed_tools=["mcp__shop__get_order", "mcp__github__*"],
)
```

Tool search is on by default (definitions load on demand). Full guide:
[references/tools-mcp.md](references/tools-mcp.md).

## Other features (where to look)

| Feature | Key option | Reference |
|---------|-----------|-----------|
| Sessions: resume, fork, list, rename, tag, external store | `resume`, `fork_session`, `session_store`, `list_sessions()` | [sessions-state.md](references/sessions-state.md) |
| File checkpointing / rewind | `enable_file_checkpointing`, `rewind_files()` | [sessions-state.md](references/sessions-state.md) |
| Structured output | `output_format={"type": "json_schema", ...}` | [messages-results-errors.md](references/messages-results-errors.md) |
| Cost and limits | `max_budget_usd`, `max_turns`, `task_budget`, `model_usage` | [messages-results-errors.md](references/messages-results-errors.md) |
| System prompt, CLAUDE.md, skills, plugins, slash commands | `system_prompt`, `setting_sources`, `skills`, `plugins` | [prompts-skills-plugins.md](references/prompts-skills-plugins.md) |
| Auth, gateways/credential proxies, timeouts, OpenTelemetry, hosting | `env`, `model`, `fallback_model` | [deployment-gateways.md](references/deployment-gateways.md) |
| Every `ClaudeAgentOptions` field and type | - | [options-reference.md](references/options-reference.md) |
| Complete runnable programs | - | [recipes.md](references/recipes.md) |

## Model selection

`model="opus" | "sonnet" | "haiku" | "fable"` (aliases track the latest), or a full ID such as
`"claude-sonnet-5-5"`, `"claude-opus-5-5"`, `"claude-haiku-5-5"`. `fallback_model` accepts a
comma-separated list. Subagent `model="inherit"` uses the parent's model. Pin what an alias
resolves to with `ANTHROPIC_DEFAULT_OPUS_MODEL` / `_SONNET_MODEL` / `_HAIKU_MODEL` in `env`.

## Error handling

```python
from claude_agent_sdk import CLINotFoundError, CLIConnectionError, ResultError, ProcessError, CLIJSONDecodeError

try:
    async for m in query(prompt="...", options=options):
        ...
except CLINotFoundError:          # CLI missing (reinstall claude-agent-sdk or set cli_path)
    ...
except ResultError as e:          # catch BEFORE ProcessError (it is a subclass)
    print(e.subtype, e.terminal_reason, e.errors, e.data.get("stop_reason"))
except ProcessError as e:
    print(e.exit_code, e.stderr)
except CLIJSONDecodeError:        # message larger than max_buffer_size (default 1 MiB)
    ...
except CLIConnectionError:
    ...
```

## Obsolete patterns (do not use)

| Old advice | Current behavior |
|------------|------------------|
| `from claude_code_sdk import ClaudeCodeOptions` | `from claude_agent_sdk import ClaudeAgentOptions` |
| `"Task"` in `allowed_tools` for subagents | Use `"Agent"` (`"Task"` still works as an alias) |
| Custom tools / `can_use_tool` need an async-generator prompt and a "keep generator alive" `stream_done` event | String prompts work. The SDK keeps stdin open until the run ends whenever hooks, `can_use_tool` or SDK MCP servers are configured |
| Dummy `PreToolUse` hook to keep the stream open for `can_use_tool` | Not needed on current SDKs (some doc examples still show it; harmless) |
| Must `break` after `ResultMessage` or `query()` deadlocks | Let the loop finish; `query()` ends when the run ends |
| Always pass `updated_input=` in `PermissionResultAllow` or the tool gets empty args | Fixed: omitted `updated_input` falls back to the original input |
| Background subagents cannot use MCP tools | Background subagents keep every MCP tool (other built-ins are filtered) |
| In-process MCP servers fail with parallel subagents | Fixed (write lock, MCP 2.x transport). Still prefer stdio/HTTP servers for heavy multi-process use |
| `output_format={"type": "json", ...}` | `{"type": "json_schema", "schema": ...}` |
| `sandbox=True` | `sandbox={"enabled": True, ...}` |
| `max_thinking_tokens=10000` | `thinking={"type": "enabled", "budget_tokens": 10000}` or `{"type": "adaptive"}`, or `effort="high"` |
| `await client.connect()` inside `async with ClaudeSDKClient()` | `async with` already connects |
| `client.rewind_files()` with no argument | `client.rewind_files(user_message_uuid)` |
| "Headless SDK prompts and fails with Stream closed" | Since CLI 2.1.302 a call that needs approval and has no allow rule/hook/callback is **denied** in `default` mode |
| `PostToolUseFailure`, `SubagentStart`, `PermissionRequest`, `Notification` are TS-only | All four are supported in Python now |

## TypeScript-only features (not available in Python)

Hook events `SessionStart`, `SessionEnd`, `PostToolBatch`, `PostCompact`, `StopFailure`,
`UserPromptExpansion`, `MessageDisplay`, `PreModelSwitch`, `PostModelSwitch`,
`PermissionDenied`, `Setup`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`,
`Elicitation*`, `ConfigChange`, `InstructionsLoaded`, `Worktree*`, `CwdChanged`,
`FileChanged`, `DirectoryAdded` (in Python, use shell hooks in `.claude/settings.json` with
`setting_sources=["project"]`); the `Workflow` tool; `permission_policy` (`always_ask`) on
custom tools; `persistSession: false` (Python: set `CLAUDE_CODE_SKIP_PROMPT_HISTORY` in
`env`); `reloadPlugins()` (Python: send `/reload-plugins` as a prompt);
`AgentDefinition.autoCompactWindow` and `omitClaudeMd`; `permissionPrompts: 'none'`.
If a doc page shows only a TypeScript example, check this list before porting it.

## Sources

- Docs index: https://code.claude.com/docs/llms.txt (append `.md` to any page URL for raw markdown)
- Python reference: https://code.claude.com/docs/en/agent-sdk/python
- Changelog: https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md
