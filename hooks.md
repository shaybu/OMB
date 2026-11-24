# Hooks (Python)

Hooks are async callbacks the CLI calls at points in the agent loop. Use them to block,
rewrite, approve, audit, or add context. Python SDK 0.2.188.

## Contents

1. Events available in Python
2. Registering hooks (`HookMatcher`)
3. Callback signature and inputs
4. Outputs: what each event can return
5. Failure, timeouts, ordering
6. Recipes
7. Troubleshooting

---

## 1. Events available in Python

`HookEvent` in Python is exactly these 10 values:

| Event | Fires | Can it change behavior? | `matcher` matches |
|-------|-------|-------------------------|-------------------|
| `PreToolUse` | Before a tool runs | Yes: allow / deny / ask / defer, rewrite input, add context | tool name |
| `PostToolUse` | After a tool succeeds | Add context, replace output (`updatedToolOutput`), `decision: "block"` adds `reason` next to the result | tool name |
| `PostToolUseFailure` | After a tool fails | Add context | tool name |
| `UserPromptSubmit` | A prompt is submitted (incl. turns Claude Code starts itself) | Add context, block (`decision: "block"`) | ignored (no matcher support) |
| `Stop` | Main agent is about to stop | Block stopping (`decision: "block"`, `reason`) to make it continue | ignored |
| `SubagentStart` | A subagent starts | Add context to the subagent | agent type |
| `SubagentStop` | A subagent finishes | Block stopping, aggregate results | agent type |
| `PreCompact` | Before context compaction | Side effects (archive transcript) | `manual` / `auto` |
| `Notification` | Status notifications (`permission_prompt` after ~6 s waiting on `can_use_tool`, elicitation events, plugin notifications) | Add context | notification type |
| `PermissionRequest` | A call needs a permission decision | Return a decision dict | tool name |

Not available as Python callbacks (TypeScript-only): `SessionStart`, `SessionEnd`,
`PostToolBatch`, `PostCompact`, `StopFailure`, `UserPromptExpansion`, `MessageDisplay`,
`PreModelSwitch`, `PostModelSwitch`, `PermissionDenied`, `Setup`, `TeammateIdle`,
`TaskCreated`, `TaskCompleted`, `Elicitation`, `ElicitationResult`, `ConfigChange`,
`InstructionsLoaded`, `WorktreeCreate`, `WorktreeRemove`, `CwdChanged`, `FileChanged`,
`DirectoryAdded`.

Workarounds in Python:
- Session start logic: run it before/after the `query()` call, or on the first message
  (`SystemMessage` with `subtype == "init"`).
- Any CLI hook event can still run as a **shell command hook** in `.claude/settings.json`
  when `setting_sources` includes `"project"` (or passed via `settings=`).

## 2. Registering hooks

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(matcher="Bash", hooks=[check_bash], timeout=30, on_failure="block"),
            HookMatcher(matcher="Write|Edit|NotebookEdit", hooks=[check_paths]),
            HookMatcher(matcher="^mcp__", hooks=[audit_mcp]),     # regex
            HookMatcher(hooks=[log_everything]),                   # no matcher = all tools
        ],
        "PostToolUse": [HookMatcher(hooks=[log_result])],
        "SubagentStop": [HookMatcher(hooks=[collect_subagent])],
    }
)
```

`HookMatcher` fields: `matcher: str | None`, `hooks: list[callable]`,
`timeout: float | None` (seconds), `on_failure: "continue" | "block" | None`.

Matcher rules: a plain name or `A|B|C` list is an exact match; anything with regex
characters is a regex. Matchers see the **tool name only**, never arguments; filter on
`tool_input` inside the callback. MCP tool names are `mcp__<server>__<tool>`.
A `"Bash"` matcher also fires for `Monitor` commands on `PreToolUse`/`PermissionRequest`
(they can be denied, not approved).

Hooks from settings files (`.claude/settings.json`) also run when those sources load
(default `setting_sources=None` loads them). Use `setting_sources=[]` to run only your
programmatic hooks.

## 3. Callback signature and inputs

```python
from typing import Any
from claude_agent_sdk import HookContext

async def my_hook(input_data: dict[str, Any], tool_use_id: str | None, context: HookContext) -> dict[str, Any]:
    ...
    return {}
```

- `input_data` is a dict (TypedDict at type-check time). Every event has `session_id`,
  `transcript_path`, `cwd`, `hook_event_name`, optional `permission_mode`.
- `tool_use_id` correlates Pre/Post events of the same call.
- `context` is reserved (`{"signal": None}`); there is no cancellation signal in Python.

Event-specific input keys:

| Event | Extra keys |
|-------|-----------|
| `PreToolUse` | `tool_name`, `tool_input`, `tool_use_id`, optional `agent_id`, `agent_type` |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, optional `agent_id`, `agent_type` |
| `PostToolUseFailure` | `tool_name`, `tool_input`, `tool_use_id`, `error`, optional `is_interrupt`, `agent_id`, `agent_type` |
| `UserPromptSubmit` | `prompt` |
| `Stop` | `stop_hook_active` |
| `SubagentStart` | `agent_id`, `agent_type` |
| `SubagentStop` | `agent_id`, `agent_type`, `agent_transcript_path`, `stop_hook_active` |
| `PreCompact` | `trigger` (`manual`/`auto`), `custom_instructions` |
| `Notification` | `message`, `notification_type`, optional `title` |
| `PermissionRequest` | `tool_name`, `tool_input`, optional `permission_suggestions`, `agent_id`, `agent_type` |

`agent_id`/`agent_type` present on a tool event means the call comes from a subagent.

## 4. Outputs

Return `{}` for "no opinion". Otherwise return a dict with:

Top-level fields (any event):

| Field | Effect |
|-------|--------|
| `continue_` | `False` stops the agent after this hook (`stopReason` explains why) |
| `stopReason` | Message when `continue_` is False |
| `systemMessage` | Message shown to the **user/app**, not the model |
| `decision: "block"` + `reason` | Block (used by `Stop`, `SubagentStop`, `UserPromptSubmit`, `PostToolUse`); `reason` is fed back to Claude |
| `suppressOutput` | No effect in the SDK |
| `hookSpecificOutput` | Event-specific control (below). Always include `hookEventName` |

`hookSpecificOutput` per event (shape reference, not runnable code):

```text
# PreToolUse
{"hookEventName": "PreToolUse",
 "permissionDecision": "allow" | "deny" | "ask" | "defer",
 "permissionDecisionReason": "shown to Claude (deny) or the approver (ask)",
 "updatedInput": {...full replacement input...},     # include unchanged fields too
 "additionalContext": "extra text for Claude"}

# PostToolUse
{"hookEventName": "PostToolUse",
 "additionalContext": "appended to the tool result",
 "updatedToolOutput": "replaces what Claude sees (built-in and MCP tools)"}

# PostToolUseFailure / UserPromptSubmit / Notification / SubagentStart
{"hookEventName": "<event>", "additionalContext": "..."}

# PermissionRequest
{"hookEventName": "PermissionRequest",
 "decision": {"behavior": "allow", "updatedInput": {...}, "updatedPermissions": [...]}}
# or {"behavior": "deny", "message": "why", "interrupt": False}
# A PermissionRequest hook can't approve what a deny rule refuses; a "block" from it only
# counts if it arrives before your can_use_tool callback answers.
```

Rules for `updatedInput`:
- It replaces the whole input: copy `tool_input` and change fields (`{**tool_input, "file_path": new}`).
- Pair with `"allow"` to auto-approve, `"ask"` to show the rewritten call, or omit the
  decision to let normal permissions evaluate it. Ignored with `"defer"`.
- Don't mutate `input_data["tool_input"]` in place.

`defer`: ends the turn with a `ResultMessage` whose `stop_reason` is `"tool_deferred"` and
`deferred_tool_use` set; resume the session later to run the call (for out-of-band
approval, e.g. a ticket or Slack approval).

Async (fire-and-forget) output, for side effects only:

```python
async def audit(input_data, tool_use_id, context):
    asyncio.create_task(ship_to_siem(input_data))
    return {"async_": True, "asyncTimeout": 30000}   # agent does not wait; cannot block
```

## 5. Failure, timeouts, ordering

- **All matching hooks for an event run in parallel.** Don't rely on order. Most
  restrictive decision wins: `deny` > `defer` > `ask` > `allow`.
- **Failure default is fail-open**: if a callback raises, returns `None`, or returns invalid
  output, the action proceeds and a `SystemMessage` with `data["tag"] == "hook_callback_failed"`
  is emitted. For guards, set `on_failure="block"` (SDK ≥ 0.2.177). With `block`, a path that
  returns nothing blocks - return `{}` explicitly. `Stop`/`SubagentStop` ignore `on_failure`.
- **Timeouts** (seconds, per matcher): default 600 s, 30 s for `UserPromptSubmit`. On timeout:
  `PreToolUse` blocks the call; `PostToolUse` keeps the result; `UserPromptSubmit` blocks the
  prompt; `Stop`/`SubagentStop` count as no decision.
- A hook `allow` does **not** override deny rules or ask rules, and cannot approve critical
  `rm` removals.
- Hooks may not fire when the run hits `max_turns`.
- Use `asyncio.to_thread()` for blocking I/O inside hooks; never block the event loop.
- `systemMessage` goes to the app (may surface as an informational `SystemMessage`), not to the
  model. To tell the model something, use `additionalContext` or `permissionDecisionReason`.
- `include_hook_events=True` adds hook lifecycle `HookEventMessage`s to the stream for debugging.

## 6. Recipes

### Block dangerous Bash (fail closed)

```python
import re
DANGEROUS = [r"\brm\s+-rf\b", r"\bsudo\b", r"\bmkfs\b", r"\bdd\s+if=", r":\(\)\s*\{", r"\bcurl\b.*\|\s*(ba)?sh"]

async def check_bash(input_data, tool_use_id, context):
    cmd = input_data["tool_input"].get("command", "")
    for pat in DANGEROUS:
        if re.search(pat, cmd):
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked by policy: matches {pat}",
            }}
    return {}

HookMatcher(matcher="Bash", hooks=[check_bash], on_failure="block")
```

Pattern checks are bypassable (aliases, scripts, encodings). Combine with
`disallowed_tools` scoped rules and the sandbox.

### Confine file writes to a directory

```python
from pathlib import Path
WORKSPACE = Path("/srv/agent/workspace").resolve()

async def confine_writes(input_data, tool_use_id, context):
    raw = input_data["tool_input"].get("file_path") or input_data["tool_input"].get("notebook_path", "")
    target = (Path(input_data["cwd"]) / raw).resolve()
    if not target.is_relative_to(WORKSPACE):
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Writes allowed only under {WORKSPACE}"}}
    return {}

HookMatcher(matcher="Write|Edit|NotebookEdit", hooks=[confine_writes], on_failure="block")
```

### Require approval for pushes (route to `can_use_tool`)

```python
async def ask_on_push(input_data, tool_use_id, context):
    if "git push" in input_data["tool_input"].get("command", ""):
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "Pushing requires human approval"}}
    return {}
```

The reason arrives in `can_use_tool` as `context.decision_reason`.

### Redact secrets from tool output

```python
import re
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})")

async def redact_bash(input_data, tool_use_id, context):
    resp = input_data.get("tool_response")
    if not isinstance(resp, dict):
        return {}
    out, err = resp.get("stdout", ""), resp.get("stderr", "")
    if SECRET.search(out) or SECRET.search(err):
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                # Must match the tool's output shape; Bash returns this object.
                "updatedToolOutput": {**resp,
                                      "stdout": SECRET.sub("[REDACTED]", out),
                                      "stderr": SECRET.sub("[REDACTED]", err)}}}
    return {}

HookMatcher(matcher="Bash", hooks=[redact_bash])
```

`updatedToolOutput` must match the tool's output shape (built-in tools return objects; a
mismatched value is ignored). MCP tool output is passed through unvalidated. It only changes
what Claude sees: the tool already ran, and telemetry captured the original. Redact
*inputs* in `PreToolUse`.

### Audit log (JSONL)

```python
import json, time, asyncio

def _append(line: str):
    with open("agent_audit.jsonl", "a") as f:
        f.write(line + "\n")

async def audit(input_data, tool_use_id, context):
    record = {"ts": time.time(), "event": input_data["hook_event_name"],
              "session": input_data["session_id"], "agent": input_data.get("agent_type", "main"),
              "tool": input_data.get("tool_name"), "input": input_data.get("tool_input"),
              "tool_use_id": tool_use_id}
    await asyncio.to_thread(_append, json.dumps(record, default=str))
    return {}

hooks = {"PreToolUse": [HookMatcher(hooks=[audit])], "PostToolUseFailure": [HookMatcher(hooks=[audit])]}
```

### Inject project context into every prompt

```python
async def add_context(input_data, tool_use_id, context):
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
            "additionalContext": "Repo conventions: pytest, ruff, type hints required."}}
```

### Don't let the agent stop until tests pass

```python
import subprocess

async def require_green_tests(input_data, tool_use_id, context):
    if input_data.get("stop_hook_active"):
        return {}                                   # already continued once; avoid loops
    r = await asyncio.to_thread(subprocess.run, ["pytest", "-q"], capture_output=True, text=True)
    if r.returncode != 0:
        return {"decision": "block", "reason": f"Tests still fail:\n{r.stdout[-2000:]}"}
    return {}

hooks = {"Stop": [HookMatcher(hooks=[require_green_tests], timeout=300)]}
```

### Track subagents

```python
async def on_subagent_start(input_data, tool_use_id, context):
    print(f"start {input_data['agent_type']} {input_data['agent_id']}")
    return {"hookSpecificOutput": {"hookEventName": "SubagentStart",
            "additionalContext": "Report findings as a bullet list with file:line."}}

async def on_subagent_stop(input_data, tool_use_id, context):
    print(f"done  {input_data['agent_type']} transcript={input_data['agent_transcript_path']}")
    return {}
```

### Rate-limit a tool

```python
import time
from collections import deque
_calls: deque[float] = deque()

async def rate_limit_web(input_data, tool_use_id, context):
    now = time.monotonic()
    while _calls and now - _calls[0] > 60:
        _calls.popleft()
    if len(_calls) >= 10:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Rate limit: 10 web calls/minute. Wait and retry."}}
    _calls.append(now)
    return {}
```

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Hook never fires | Event name is case-sensitive (`PreToolUse`); matcher must match the tool name (`Agent`, not `Task`); event must be one of the 10 Python events |
| Tool still runs although hook denied | Check `hookSpecificOutput.hookEventName` is set and the dict is returned, not printed |
| `updatedInput` ignored | It must be inside `hookSpecificOutput`; not with `defer`; include all original fields |
| "returned updatedInput that failed schema validation" | You dropped required fields; start from `{**tool_input}` |
| Tool blocked unexpectedly | Another parallel hook denied it, or a hook timed out (PreToolUse timeout blocks) |
| Guard crashed and the call went through | Set `on_failure="block"` |
| Permission prompts multiply with many subagents | Auto-approve in a `PreToolUse` hook or with allow rules (subagents inherit rules) |
| Infinite loop with `UserPromptSubmit`/`Stop` hooks | Check `stop_hook_active`; scope hooks by `agent_type` |
| `systemMessage` not seen by Claude | Expected; use `additionalContext` |
