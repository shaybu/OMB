# Messages, results, structured output, cost and errors (Python)

Python SDK 0.2.188. Messages are **dataclasses** (attribute access: `msg.result`);
config/hook/usage types are **TypedDicts** (plain dicts: `cfg["budget_tokens"]`).

## 1. The message stream

```python
from claude_agent_sdk import (SystemMessage, AssistantMessage, UserMessage, ResultMessage,
                              TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock,
                              TaskStartedMessage, TaskNotificationMessage, RateLimitEvent)
from claude_agent_sdk.types import StreamEvent

async for msg in query(prompt=..., options=...):
    match msg:
        case SystemMessage(subtype="init"):
            print("session", msg.data["session_id"], "model", msg.data.get("model"))
        case AssistantMessage():
            for block in msg.content:
                if isinstance(block, TextBlock): print(block.text)
                elif isinstance(block, ToolUseBlock): print("tool", block.name, block.input)
                elif isinstance(block, ThinkingBlock): pass
        case UserMessage():
            for block in msg.content if isinstance(msg.content, list) else []:
                if isinstance(block, ToolResultBlock) and block.is_error:
                    print("tool error", block.content)
        case ResultMessage():
            print(msg.subtype, msg.result, msg.total_cost_usd)
```

Order: `SystemMessage(init)` → (`AssistantMessage` → `UserMessage` tool results)* →
`ResultMessage`. Task messages are subclasses of `SystemMessage` (check them before a generic
`SystemMessage` branch). Other system subtypes arrive as plain `SystemMessage`
(`compact_boundary`, `session_state_changed` with `CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS=1`,
`hook_callback_failed` warnings in `data["tag"]`).

Typed init payload: `from typing import cast; from claude_agent_sdk import SystemInitData;
init = cast(SystemInitData, msg.data)`.

`AssistantMessage.error` can be `authentication_failed`, `billing_error`, `rate_limit`,
`invalid_request`, `server_error`, `unknown` (or other strings such as `max_output_tokens`).

## 2. ResultMessage

| Field | Meaning |
|-------|---------|
| `subtype` | `success`, `error_during_execution`, `error_max_turns`, `error_max_budget_usd`, `error_max_structured_output_retries` |
| `is_error` | True on all `error_*`; on `success` True means refusal (`stop_reason="refusal"`), deferred tool unavailable, or API error |
| `result` | Final text (success only) |
| `structured_output` | Validated JSON when `output_format` is set |
| `stop_reason` | `end_turn`, `refusal`, `tool_deferred`, ... |
| `terminal_reason` | `completed`, `max_turns`, `api_error`, `aborted_streaming`, `aborted_tools`, ... |
| `api_error_status` | HTTP status of a terminating API error |
| `errors` | Loop-level error strings (error subtypes) |
| `total_cost_usd` | Client-side estimate, includes subagents; cumulative in ClaudeSDKClient sessions |
| `usage` | Main loop tokens only (excludes subagents) |
| `model_usage` | Per model: `inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, `costUSD`, `contextWindow`, ... (camelCase). Use this for accounting |
| `num_turns`, `duration_ms`, `duration_api_ms` | Stats |
| `permission_denials` | Calls that were denied: inspect in headless runs |
| `deferred_tool_use` | Set when a hook returned `defer` |
| `session_id`, `uuid`, `origin` | Identity; `origin["kind"] == "task-notification"` marks turns triggered by background tasks |

Recommended success check:

```python
def ok(r: ResultMessage) -> bool:
    return r.subtype == "success" and not r.is_error
```

## 3. Errors

| Exception | When |
|-----------|------|
| `CLINotFoundError` (⊂ `CLIConnectionError`) | No `claude` binary (bundled CLI missing, bad `cli_path`) |
| `CLIConnectionError` | Can't start/talk to the CLI (incl. refusing `.cmd`/`.bat` on Windows, `on_failure="block"` unsupported) |
| `ResultError` (⊂ `ProcessError`) | Single-shot `query()` ended with an error result. Attributes: `subtype`, `errors`, `result`, `api_error_status`, `terminal_reason`, `session_id`, `data` |
| `ProcessError` | CLI exited non-zero: `exit_code`, `stderr` |
| `CLIJSONDecodeError` | Bad JSON or a message longer than `max_buffer_size` (default 1,048,576 chars) |
| `ClaudeSDKError` | Base class |
| `ValueError` | Invalid options (e.g. `can_use_tool` + `permission_prompt_tool_name`, malformed `skills` names) |

Order of checks for a `ResultError`: `e.data.get("stop_reason") == "refusal"` →
`e.terminal_reason` (e.g. `"api_error"`) → `e.subtype`.

Get stderr for debugging: `ClaudeAgentOptions(stderr=lambda line: log.debug(line))`.
If your async-generator prompt raises, the loop ends silently and the SDK logs
`Prompt stream failed; closing stdin` - wrap the generator body in try/except and log.

## 4. Structured output

```python
from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

class Finding(BaseModel):
    file: str
    line: int
    severity: str
    message: str

class Report(BaseModel):
    summary: str
    findings: list[Finding]

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Glob"],
    output_format={"type": "json_schema", "schema": Report.model_json_schema()},
)
try:
    async for m in query(prompt="Audit src/ for SQL injection", options=options):
        if isinstance(m, ResultMessage) and m.subtype == "success" and m.structured_output:
            report = Report.model_validate(m.structured_output)
except Exception as e:     # error_max_structured_output_retries raises ResultError
    ...
```

- The agent may use tools first; validation happens on the final answer and it re-prompts on
  mismatch.
- JSON Schema draft-07; `enum`, `const`, `$ref`, nested objects supported; `format` is
  accepted but not enforced. An invalid schema fails the run at startup.
- `success` with `structured_output is None` → treat as failure (refusal or unsatisfiable schema).

## 5. Streaming partial output

```python
from claude_agent_sdk.types import StreamEvent
opts = ClaudeAgentOptions(include_partial_messages=True)
async for m in query(prompt="Write a haiku about Python", options=opts):
    if isinstance(m, StreamEvent) and m.event.get("type") == "content_block_delta":
        delta = m.event["delta"]
        if delta.get("type") == "text_delta":
            print(delta["text"], end="", flush=True)
```

Stream events are main-session only (`parent_tool_use_id` is always None). `ping` events may
arrive while a gateway holds a response open - treat as liveness.

## 6. Cost and usage

```python
total = 0.0
async with ClaudeSDKClient(options) as client:
    for prompt in prompts:
        await client.query(prompt)
        async for m in client.receive_response():
            if isinstance(m, ResultMessage):
                total = m.total_cost_usd or 0.0          # cumulative: take latest, don't sum
                for model, u in (m.model_usage or {}).items():
                    print(model, u["inputTokens"], u["outputTokens"], u.get("costUSD"))
```

- Across separate `query()` calls, sum each call's `total_cost_usd` (unless resuming, which
  restores earlier totals).
- Costs are estimates computed client-side; behind a gateway or with custom pricing they may
  be wrong (`costBasis` tells you). Bill from your provider/gateway.
- `max_budget_usd` can be exceeded by one response plus running subagents: leave headroom.
- Thinking: `thinking={"type": "adaptive"}` or `{"type": "enabled", "budget_tokens": N}`,
  `{"type": "disabled"}`; add `"display": "summarized"` to receive thinking text on newer
  models. `effort="low"|"medium"|"high"|"xhigh"|"max"` trades depth for cost.
