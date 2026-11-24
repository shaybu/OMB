# Custom tools and MCP servers (Python)

Python SDK 0.2.188. Custom tools are in-process MCP servers. Tool names seen by the model
and used in rules are `mcp__<server-key>__<tool-name>`, where `<server-key>` is the key in
`mcp_servers`.

## Contents

1. Define a tool with `@tool`
2. Input schemas (dict, JSON Schema, TypedDict)
3. Results: text, errors, images, resources, structured content
4. Annotations (parallelism, safety hints, result size)
5. Register and allow tools
6. External MCP servers (stdio, HTTP, SSE, `.mcp.json`)
7. Connection timing, status and runtime control
8. Tool search (many tools)
9. Limits and timeouts
10. Best practices
11. Troubleshooting

---

## 1. Define a tool

```python
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions

@tool("get_weather", "Current temperature for a city. Use for any weather question.", {"city": str})
async def get_weather(args: dict[str, Any]) -> dict[str, Any]:
    temp = await lookup_temperature(args["city"])            # your async code
    return {"content": [{"type": "text", "text": f"{args['city']}: {temp}°C"}]}

weather = create_sdk_mcp_server(name="weather", version="1.0.0", tools=[get_weather])

options = ClaudeAgentOptions(
    mcp_servers={"weather": weather},
    allowed_tools=["mcp__weather__get_weather"],
)
```

- The handler must be `async`, take one `args` dict, and return a dict with `content`.
- The decorated object is an `SdkMcpTool`; pass the decorated function in `tools=[...]`.
- The description is what the model reads to decide when to call it: say what it does,
  when to use it, and what it returns.
- Works with a plain string prompt and with `ClaudeSDKClient`. (Old advice that custom
  tools need an async-generator prompt is obsolete.)

## 2. Input schemas

```python
from typing import Annotated, Any
from claude_agent_sdk import tool

# a) Simple mapping (all keys required)
@tool("add", "Add two numbers", {"a": float, "b": float})
async def add(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": str(args["a"] + args["b"])}]}

# b) Annotated descriptions
@tool("search", "Search docs", {"query": Annotated[str, "Full-text query"], "limit": Annotated[int, "Max hits"]})
async def search(args): ...

# c) Full JSON Schema (optional fields, enums, constraints)
@tool("convert", "Convert units", {
    "type": "object",
    "properties": {
        "value": {"type": "number"},
        "unit": {"type": "string", "enum": ["km", "mi", "m"]},
        "precision": {"type": "integer", "minimum": 0, "maximum": 6},
    },
    "required": ["value", "unit"],
})
async def convert(args): ...

# d) TypedDict (NotRequired keys become optional)
from typing import NotRequired, TypedDict     # Python 3.10: from typing_extensions
class ForecastArgs(TypedDict):
    latitude: Annotated[float, "Latitude"]
    hours: NotRequired[Annotated[int, "Hours of forecast"]]

@tool("get_forecast", "Hourly forecast", ForecastArgs)
async def get_forecast(args): ...
```

Optional parameters: declare them optional in the schema and apply the default in the
handler (`args.get("hours", 12)`).

## 3. Results

```python
# Text
{"content": [{"type": "text", "text": "..."}]}

# Error the model should read (agent loop continues; Claude can retry or adapt)
{"content": [{"type": "text", "text": "Order 123 not found. Try search_orders first."}], "is_error": True}

# Image (base64)
{"content": [{"type": "image", "data": b64_png, "mimeType": "image/png"}]}

# Embedded resource
{"content": [{"type": "resource", "resource": {"uri": "file:///report.csv", "mimeType": "text/csv", "text": csv_text}}]}

```

The Python `@tool` decorator forwards only `content` and `is_error`. `structuredContent` is
**dropped** for in-process tools; to return it, run a standalone MCP server (stdio/HTTP)
instead. For in-process tools, put JSON in a text block (`json.dumps(data)`).
Resource `blob` (binary) blocks are also dropped in Python; use `text`.

- An uncaught exception in a handler becomes an error result with the raw exception text;
  it does not crash the query. Catch errors and return `is_error: True` with an actionable
  message instead.
- Python drops `audio` blocks (with a warning) and flattens `resource_link` blocks to text.
- Large text results (>~25k tokens or >50k chars) are written to a file and Claude gets the
  path instead; raise per tool with `ToolAnnotations(maxResultSizeChars=...)` (≤ 500,000) or
  globally with `MAX_MCP_OUTPUT_TOKENS`.

## 4. Annotations

```python
from claude_agent_sdk import tool, ToolAnnotations

@tool("get_user", "Fetch a user by id", {"id": str},
      annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False, maxResultSizeChars=100_000))
async def get_user(args): ...
```

| Hint | Default | Effect |
|------|---------|--------|
| `readOnlyHint` | False | **True lets the tool run in parallel** with other read-only calls |
| `destructiveHint` | True | Informs the auto-mode classifier; set explicitly |
| `idempotentHint` | False | Informational |
| `openWorldHint` | True | Informational (touches external systems) |
| `maxResultSizeChars` | None | Keep results up to this size inline |

camelCase and snake_case keywords both work (SDK ≥ 0.2.140). Hints are not a security boundary.

## 5. Register and allow tools

```python
options = ClaudeAgentOptions(
    mcp_servers={"crm": crm_server},
    allowed_tools=["mcp__crm__get_customer", "mcp__crm__search"],   # read tools auto-approved
    # mcp__crm__delete_customer is NOT listed -> goes to the permission flow
    disallowed_tools=["mcp__crm__purge_all"],                        # never callable
)
```

- `allowed_tools=["mcp__crm__*"]` approves every tool of that server. `["mcp__*"]` in allow
  rules is ignored (must name a server).
- `acceptEdits` does **not** approve MCP tools.
- To gate a dangerous tool behind a human, leave it out of `allowed_tools` and handle it in
  `can_use_tool`, or return `"ask"` from a `PreToolUse` hook. (`permission_policy:
  "always_ask"` exists only in TypeScript.)
- To remove built-in tools so only your tools exist: `tools=[]` (no built-ins) or
  `tools=["Read"]`, plus your `mcp_servers`.

## 6. External MCP servers

```python
import os
options = ClaudeAgentOptions(
    mcp_servers={
        # stdio: a local process
        "filesystem": {"command": "npx",
                       "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
                       "env": {"LOG_LEVEL": "warn"}},
        # Streamable HTTP
        "github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
                   "headers": {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}},
        # Server-Sent Events (legacy remote transport)
        "legacy": {"type": "sse", "url": "https://mcp.example.com/sse"},
    },
    allowed_tools=["mcp__github__list_issues", "mcp__filesystem__read_file"],
)
```

- `mcp_servers` may also be a path to a JSON config file (`mcp_servers="mcp.json"`).
- A project `.mcp.json` loads when the `project` setting source is on (default). Set
  `strict_mcp_config=True` to use **only** the servers you pass (ignores `.mcp.json`, user
  settings, plugin servers, claude.ai connectors). Recommended for servers/CI.
- Pass secrets via `env`/`headers` from your process environment; for OAuth servers, run the
  OAuth flow in your app and pass the access token as a header.
- Give a subagent only some servers with `AgentDefinition(mcpServers=["github"])` or strip them
  with `disallowedTools=["mcp__*"]`.

## 7. Connection timing, status, runtime control

- stdio/HTTP/SSE servers in `mcp_servers` and in-process servers delay the first turn until
  connected, up to `MCP_TIMEOUT` (30 s default, set in `env`, ms).
- Servers from `.mcp.json`/plugins may still be `pending` at init; with tool search on they
  keep connecting in the background. `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` sets the first-turn wait.
- Check status in the init message; treat only `failed`/`needs-auth` as broken (`pending` may
  just be slow or cached):

```python
from claude_agent_sdk import SystemMessage
if isinstance(msg, SystemMessage) and msg.subtype == "init":
    bad = [s for s in msg.data.get("mcp_servers", []) if s.get("status") in ("failed", "needs-auth")]
    mcp_tools = [t for t in msg.data.get("tools", []) if t.startswith("mcp__")]
```

- With `ClaudeSDKClient`: `await client.get_mcp_status()` (returns `{"mcpServers": [...]}`),
  `await client.reconnect_mcp_server("github")`, `await client.toggle_mcp_server("github", False)`.
- A failed MCP connection does not raise; you must check status.

## 8. Tool search

On by default: tool definitions are deferred and Claude searches for them (up to 5 loaded at
a time). Good for large toolsets; adds a round-trip per search. Control with `env`:

| `ENABLE_TOOL_SEARCH` | Behavior |
|----------------------|----------|
| unset / `true` | On (falls back to upfront loading on unsupported models/providers) |
| `auto` / `auto:N` | Upfront until deferrable definitions exceed 10% / N% of context |
| `false` | Off: everything loads every turn (best with < ~10 tools) |

Deny the `ToolSearch` tool or set `false` to disable. A server marked `alwaysLoad: true` in
its Claude Code MCP config (e.g. `.mcp.json`) keeps its tools loaded upfront.

## 9. Limits and timeouts

| Env var | Meaning | Default |
|---------|---------|---------|
| `MCP_TIMEOUT` | Server connect timeout (ms) | 30000 |
| `MCP_TOOL_TIMEOUT` | Tool call timeout (ms) | - |
| `MAX_MCP_OUTPUT_TOKENS` | Inline result size before spilling to a file | 25000 |
| `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` | First-turn wait for pending servers | - |

## 10. Best practices

1. Few, well-described tools beat many overlapping ones. Name tools by action
   (`search_orders`, `get_order`, `refund_order`).
2. Validate inputs in the handler even with a schema; never trust model-provided IDs or paths.
3. Keep credentials inside the handler's process (your code), not in prompts or env the agent can
   read via Bash.
4. Return concise text; paginate large data; return JSON as text for machine-readable data (in-process Python tools drop `structuredContent`).
5. Return `is_error: True` with a next step ("call search_orders first") rather than raising.
6. Mark read-only tools with `readOnlyHint=True` to get parallel execution.
7. Pre-approve read tools; route write/destructive tools through hooks or `can_use_tool`.
8. Use `strict_mcp_config=True` in production so stray `.mcp.json` files can't add servers.
9. Make handlers non-blocking (`await`, `asyncio.to_thread` for sync libraries).
10. Test handlers directly: `await get_weather.handler({"city": "Paris"})`.

## 11. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Tool never called | Check the exact name `mcp__<key>__<tool>` in `allowed_tools`; improve the description; check the init `tools` list |
| Tool call denied in headless mode | Not in `allowed_tools` and no hook/callback approved it (default mode denies) |
| Server `failed` | Command not installed / wrong path / bad credentials; run the command manually; raise `MCP_TIMEOUT` |
| Tool missing from an SDK server | You passed the undecorated function, or forgot to include it in `tools=[...]` |
| Output replaced by "saved to file" error | Result too large: paginate, or raise `maxResultSizeChars` / `MAX_MCP_OUTPUT_TOKENS` |
