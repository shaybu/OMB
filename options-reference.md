# `ClaudeAgentOptions` and related types (Python SDK 0.2.188)

All fields are optional. snake_case here; `AgentDefinition` uses camelCase.
Run `python scripts/check_sdk.py` to list the fields of the installed version.

## Tools and permissions

| Field | Type | Notes |
|-------|------|-------|
| `tools` | `list[str] \| {"type":"preset","preset":"claude_code"} \| None` | Built-ins the model can see. `[]` = none |
| `allowed_tools` | `list[str]` | Auto-approve rules (not a restriction) |
| `disallowed_tools` | `list[str]` | Bare name removes a tool; scoped rule denies matching calls in all modes |
| `permission_mode` | `"default" \| "acceptEdits" \| "plan" \| "dontAsk" \| "bypassPermissions" \| "auto"` | |
| `can_use_tool` | `async (tool_name, input, ToolPermissionContext) -> PermissionResultAllow \| PermissionResultDeny` | For undecided calls |
| `permission_prompt_tool_name` | `str` | MCP tool that answers permission prompts (exclusive with `can_use_tool`) |
| `hooks` | `dict[HookEvent, list[HookMatcher]]` | See hooks.md |
| `sandbox` | `SandboxSettings` dict | `enabled`, `failIfUnavailable`, `autoAllowBashIfSandboxed`, `excludedCommands`, `allowUnsandboxedCommands`, `network`, `filesystem`, `ignoreViolations`, `enableWeakerNestedSandbox` |
| `settings` | `str` | Path or inline JSON of a settings file (permissions, env, apiKeyHelper, ...) |
| `setting_sources` | `list["user" \| "project" \| "local"] \| None` | `None` = all; `[]` = none |
| `add_dirs` | `list[str \| Path]` | Extra accessible directories |
| `user` | `str` | POSIX user to run the CLI as |

## Model and reasoning

| Field | Type | Notes |
|-------|------|-------|
| `model` | `str` | Alias (`opus`, `sonnet`, `haiku`, `fable`) or full ID |
| `fallback_model` | `str` | Comma-separated list allowed |
| `thinking` | `{"type":"adaptive"} \| {"type":"enabled","budget_tokens":N} \| {"type":"disabled"}` | Optional `"display": "summarized" \| "omitted"` |
| `effort` | `"low" \| "medium" \| "high" \| "xhigh" \| "max"` | |
| `max_thinking_tokens` | `int` | Deprecated; use `thinking` |
| `betas` | `list[str]` | e.g. `"context-1m-2025-08-07"` (retired for Sonnet 4/4.5) |
| `task_budget` | `{"total": int}` | API-side token budget |

## Prompt and context

| Field | Type | Notes |
|-------|------|-------|
| `system_prompt` | `str \| {"type":"preset","preset":"claude_code","append"?,"exclude_dynamic_sections"?,"snapshot"?} \| {"type":"custom","prompt",...} \| {"type":"file","path"}` | Default is minimal |
| `skills` | `list[str] \| "all" \| None` | Main-agent skill allowlist |
| `plugins` | `list[{"type":"local","path":str}]` | |
| `agents` | `dict[str, AgentDefinition]` | Subagents |
| `cwd` | `str \| Path` | Working directory (sessions are keyed by it) |
| `verbatim_prompts` | `bool` | Mark prompts as client-composed (SDK ≥ 0.2.158) |

## Limits

| Field | Type | Notes |
|-------|------|-------|
| `max_turns` | `int` | → `error_max_turns` |
| `max_budget_usd` | `float` | → `error_max_budget_usd`; includes subagents |
| `output_format` | `{"type":"json_schema","schema":{...}}` | → `ResultMessage.structured_output` |

## Sessions

| Field | Type | Notes |
|-------|------|-------|
| `continue_conversation` | `bool` | Most recent session in `cwd` |
| `resume` | `str` | Session ID |
| `fork_session` | `bool` | With `resume`: new session ID |
| `resume_session_at` | `str` | Message UUID to truncate history at |
| `resume_drops_turn` | `str` | Safety check for truncation |
| `session_id` | `str` (UUID) | Choose the new session's ID |
| `session_store` | `SessionStore` | External transcript mirror |
| `session_store_flush` | `"batched" \| "eager"` | |
| `load_timeout_ms` | `int` | Store load timeout (60000) |
| `enable_file_checkpointing` | `bool` | Needed for `rewind_files` |

## MCP

| Field | Type | Notes |
|-------|------|-------|
| `mcp_servers` | `dict[str, config] \| str \| Path` | stdio `{"command","args","env"}`, `{"type":"http"\|"sse","url","headers"}`, SDK server from `create_sdk_mcp_server` |
| `strict_mcp_config` | `bool` | Ignore `.mcp.json`, user/plugin servers, connectors |

## Streaming and process

| Field | Type | Notes |
|-------|------|-------|
| `include_partial_messages` | `bool` | Yields `StreamEvent` |
| `include_hook_events` | `bool` | Yields hook lifecycle messages |
| `forward_subagent_text` | `bool` | Include foreground subagent text/thinking |
| `env` | `dict[str,str]` | Merged into the CLI environment |
| `extra_args` | `dict[str, str \| None]` | Raw CLI flags, e.g. `{"replay-user-messages": None}` |
| `cli_path` | `str \| Path` | Custom `claude` binary |
| `stderr` | `Callable[[str], None]` | CLI stderr lines |
| `max_buffer_size` | `int` | Max single message (default 1,048,576 chars) |
| `client_app` | `str` | App identifier for User-Agent (also `CLAUDE_AGENT_SDK_CLIENT_APP`) |
| `debug_stderr` | - | Deprecated, ignored |

## `AgentDefinition`

`description` (req), `prompt` (req), `tools`, `disallowedTools`, `model`, `skills`, `memory`,
`mcpServers`, `initialPrompt`, `maxTurns`, `background`, `effort`, `permissionMode`.

## `HookMatcher`

`matcher: str | None`, `hooks: list[callback]`, `timeout: float | None` (seconds),
`on_failure: "continue" | "block" | None`.

## Permission result types

```text
PermissionResultAllow(updated_input: dict | None = None, updated_permissions: list[PermissionUpdate] | None = None)
PermissionResultDeny(message: str = "", interrupt: bool = False)
PermissionUpdate(type="addRules"|"replaceRules"|"removeRules"|"setMode"|"addDirectories"|"removeDirectories",
                 rules=[PermissionRuleValue(tool_name="Bash", rule_content="npm test *")],
                 behavior="allow"|"deny"|"ask", mode=..., directories=[...],
                 destination="userSettings"|"projectSettings"|"localSettings"|"session")
ToolPermissionContext: suggestions, tool_use_id, agent_id, blocked_path, decision_reason, title, display_name, description
```

## Useful environment variables (pass in `env`)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` | Auth and gateway |
| `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL` | Model mapping |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` | Subagent caps |
| `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS` | Remove `general-purpose` |
| `API_TIMEOUT_MS`, `CLAUDE_CODE_MAX_RETRIES`, `CLAUDE_CODE_RETRY_WATCHDOG` | API robustness |
| `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`, `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | Watchdogs |
| `MCP_TIMEOUT`, `MCP_TOOL_TIMEOUT`, `MAX_MCP_OUTPUT_TOKENS`, `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` | MCP |
| `ENABLE_TOOL_SEARCH`, `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` | Tool search / betas |
| `CLAUDE_CODE_SKIP_PROMPT_HISTORY` | Don't write transcripts |
| `CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS` | `session_state_changed` messages |
| `CLAUDE_CONFIG_DIR` | Relocate `~/.claude` config |
| `CLAUDE_CODE_ENABLE_TELEMETRY` + `OTEL_*` | OpenTelemetry |
