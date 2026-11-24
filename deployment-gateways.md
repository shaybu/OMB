# Deployment, authentication, gateways, timeouts, observability (Python)

Python SDK 0.2.188.

## 1. How the SDK runs

Each `query()` / `ClaudeSDKClient` spawns one `claude` CLI subprocess (bundled in the wheel,
pinned to the SDK version) and talks to it over stdio. N concurrent sessions = N processes.
The subprocess owns the shell, working directory and transcript files (`~/.claude/projects/`).

- Runtime: Python ≥ 3.10. No Node.js needed for the bundled binary.
- Sizing start point: ~1 GiB RAM, 5 GiB disk, 1 CPU per concurrent agent; memory grows with
  session length - recycle long sessions.
- Override the binary with `cli_path=`; on Windows never point it at a `.cmd`/`.bat` shim.
- Upgrade the CLI by upgrading `claude-agent-sdk`; pin it in production.
- No session wall-clock timeout exists: bound with `max_turns`, `max_budget_usd`, per-agent
  `maxTurns`, stall watchdog, and your own `asyncio.wait_for` if needed.

Session patterns: **ephemeral** (container per task, then destroy - simplest and safest),
**long-running** (one process per user conversation, `ClaudeSDKClient`), **hybrid**
(ephemeral containers + `session_store` / `resume` to continue later).

## 2. Authentication

| Setup | `env` |
|-------|-------|
| Anthropic API (default) | `ANTHROPIC_API_KEY` |
| Through a gateway / credential proxy | `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` (sent as `Authorization: Bearer`) or `ANTHROPIC_API_KEY` (sent as `x-api-key`) |

Products built on the SDK must use API-key style auth; offering claude.ai login/rate limits
to your users requires Anthropic approval.

`env` in Python is **merged** on top of `os.environ` (TypeScript replaces it).

## 3. Gateway / credential proxy

Routing model traffic through a proxy keeps the real API key out of the agent's environment
and gives you one place to log, rate-limit and allowlist (see permissions-security.md §11).

```python
import os
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_BASE_URL": "https://llm-gateway.internal.example.com",
        "ANTHROPIC_AUTH_TOKEN": os.environ["GATEWAY_TOKEN"],
        "ANTHROPIC_CUSTOM_HEADERS": "X-Team: qa",     # optional, newline-separated pairs
    },
)
```

- The gateway must forward the Anthropic Messages API (`/v1/messages`, streaming, tool use,
  `anthropic-beta` headers).
- Wrong credential variable for the gateway's header → 401/403. Default to
  `ANTHROPIC_AUTH_TOKEN` when unsure.
- **Rotating / SSO tokens**: use `apiKeyHelper` (a command that prints only the current token)
  in a settings file or `settings='{"apiKeyHelper": "/path/get-token.sh"}'` instead of a static
  env var. A 401/403 mid-run usually means the token expired.
- If the gateway rejects beta headers, set `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` (this also
  turns tool search off).
- Keep-alive pings from a gateway arrive as `ping` stream events with
  `include_partial_messages=True`; treat them as liveness.
- Test the gateway outside the SDK first:
  `curl $ANTHROPIC_BASE_URL/v1/messages -H "Authorization: Bearer $ANTHROPIC_AUTH_TOKEN" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d '{"model":"claude-haiku-5-5","max_tokens":20,"messages":[{"role":"user","content":"hi"}]}'`.

## 4. Timeouts, retries, stalls

```python
ClaudeAgentOptions(env={
    "API_TIMEOUT_MS": "120000",                  # per attempt, waiting for headers (default 600000)
    "CLAUDE_CODE_MAX_RETRIES": "3",              # default 10, max 15
    "CLAUDE_STREAM_IDLE_TIMEOUT_MS": "300000",   # stream watchdog (on by default, min 300000)
    "CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS": "300000",  # subagent stall watchdog
    "MCP_TIMEOUT": "60000",                      # MCP connect
    "MCP_TOOL_TIMEOUT": "120000",                # MCP tool call
})
```

`CLAUDE_CODE_RETRY_WATCHDOG=1` retries transient capacity errors indefinitely (unattended jobs).

## 5. Observability (OpenTelemetry)

```python
OTEL_ENV = {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",   # needed for traces
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318",
}
options = ClaudeAgentOptions(env=OTEL_ENV)
```

- Never use the `console` exporter (stdout is the SDK's message channel).
- Short tasks may drop spans; shorten export intervals (`OTEL_METRIC_EXPORT_INTERVAL`, etc.).
- Identify your app in User-Agent with `CLAUDE_AGENT_SDK_CLIENT_APP` (or `client_app=`).
- Cheap alternative: an audit `PreToolUse`/`PostToolUse` hook + logging every `ResultMessage`
  (`session_id`, `subtype`, `num_turns`, `total_cost_usd`, `permission_denials`).

## 6. Production checklist

- [ ] One container (or at least one `cwd` + `HOME`) per tenant/job; non-root user.
- [ ] `setting_sources` set explicitly; `strict_mcp_config=True`.
- [ ] Permission profile from permissions-security.md; sandbox with `failIfUnavailable`.
- [ ] `max_turns`, `max_budget_usd`, subagent caps, API timeouts.
- [ ] Concurrency bounded (semaphore / worker pool); batch large fan-outs (rate limits).
- [ ] `ResultError` handled; `stderr` callback wired to logs.
- [ ] Credentials via gateway/proxy or tool handlers, not in the agent's environment where possible.
- [ ] SDK version pinned; upgrades tested.

## 7. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `CLINotFoundError` in a service | Different `PATH`/broken install; `pip install --force-reinstall claude-agent-sdk` or set `cli_path` |
| `Failed to start Claude Code` | Wrong arch/libc in image, lost execute bit |
| `Not logged in` / `Invalid API key` | Env not passed to the process; wrong credential variable for the gateway |
| 403 from gateway | Expired SSO token, wrong header type, model not allowed for the key |
| `There's an issue with the selected model` | Model name not served by the provider/gateway; set alias env vars |
| Tool calls all denied in production | No allow rules/hooks/callback and `default` mode denies; add `allowed_tools` |
| `Argument list too long` | Huge `system_prompt` string: use `{"type": "file", "path": ...}` |
| `CLIJSONDecodeError` on big tool output | Raise `max_buffer_size` |
| Process memory keeps growing | Recycle long sessions; `/compact`; shorter sessions |
