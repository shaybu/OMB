# Sessions, conversations, streaming input and file checkpointing (Python)

Python SDK 0.2.188.

## 1. Choose how to keep context

| Building | Use |
|----------|-----|
| One-shot task | One `query()` call (the agent takes as many turns as it needs inside it) |
| Chat in one process | `ClaudeSDKClient` (session handled for you) |
| Resume after restart, one conversation per directory | `ClaudeAgentOptions(continue_conversation=True)` |
| Resume a specific conversation (multi-user apps) | Capture `session_id`, pass `resume=session_id` |
| Try an alternative without changing the original | `resume=..., fork_session=True` or `fork_session()` |
| Branch from an earlier message | `resume=..., resume_session_at=<message uuid>, fork_session=True` |
| Resume on another host | `session_store=` (external storage) with the same `cwd` |
| Don't write transcripts | `env={"CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1"}` (Python has no `persistSession`) |

Sessions persist the **conversation**, not files. Use checkpointing (section 6) for files.
Transcripts live in `~/.claude/projects/<encoded-cwd>/<session_id>.jsonl`; resume must run
from the same `cwd`.

## 2. Capture and resume

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

session_id = None
async for m in query(prompt="Analyze auth.py", options=ClaudeAgentOptions(allowed_tools=["Read"])):
    if isinstance(m, ResultMessage):
        session_id = m.session_id          # also in the init SystemMessage: m.data["session_id"]

async for m in query(prompt="Now find all callers of login()",
                     options=ClaudeAgentOptions(resume=session_id, allowed_tools=["Read", "Grep"])):
    ...
```

- Pass the same `agents`, `mcp_servers`, hooks etc. when resuming; options are not stored in
  the transcript.
- `session_id=<uuid>` lets you choose the ID of a new session (can't combine with
  `resume`/`continue_conversation` unless `fork_session=True`).
- `max_budget_usd` counts only the current call's spend; `total_cost_usd` on a resumed session
  includes restored totals.

## 3. Session utilities (synchronous functions)

```python
from claude_agent_sdk import (list_sessions, get_session_info, get_session_messages,
                              rename_session, tag_session, fork_session, delete_session,
                              list_subagents, get_subagent_messages)

for s in list_sessions(directory="/repo", limit=10):        # newest first
    print(s.session_id, s.summary, s.git_branch, s.tag)

msgs = get_session_messages(session_id, limit=100)           # SessionMessage(type, uuid, message, parent_tool_use_id)
rename_session(session_id, "Refactor auth")
tag_session(session_id, "needs-review")                      # None clears
forked = fork_session(session_id, up_to_message_id=msgs[5].uuid, title="Try OAuth")
# continue the fork with ClaudeAgentOptions(resume=forked.session_id)
delete_session(session_id)
```

Store-backed variants exist (`list_sessions_from_store`, `get_session_messages_from_store`,
`fork_session_via_store`, ...).

## 4. External session storage

```python
from claude_agent_sdk import InMemorySessionStore, ClaudeAgentOptions

store = InMemorySessionStore()                # dev/test; implement SessionStore for Redis/S3/DB
opts = ClaudeAgentOptions(session_store=store, session_store_flush="batched")  # or "eager"
# Later, on any host with the same cwd:
opts2 = ClaudeAgentOptions(session_store=store, resume=session_id)
```

A `SessionStore` implements async `append(key, entries)` and `load(key)`, optionally
`list_sessions`, `list_session_summaries`, `delete`, `list_subkeys`. Persist entries in order,
return them unchanged. Test an adapter with
`claude_agent_sdk.testing.run_session_store_conformance`.

## 5. ClaudeSDKClient patterns

### Multi-turn chat

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock

async with ClaudeSDKClient(options=ClaudeAgentOptions(allowed_tools=["Read", "Grep"])) as client:
    while (user := input("> ")) not in ("exit", "quit"):
        await client.query(user)
        async for m in client.receive_response():
            if isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, TextBlock):
                        print(b.text, end="")
        print()
```

### Interrupt and redirect

```python
await client.query("Refactor the whole repo")
await asyncio.sleep(5)
await client.interrupt()
async for m in client.receive_response():   # drain the interrupted turn (its ResultMessage has
    pass                                    # terminal_reason "aborted_streaming"/"aborted_tools")
await client.query("Only refactor src/auth instead")
async for m in client.receive_response():
    ...
```

### Change configuration mid-session

```python
await client.set_permission_mode("acceptEdits")
await client.set_model("haiku")          # None resets to default
usage = await client.get_context_usage() # dict: totalTokens, maxTokens, percentage, categories...
```

### Images and assembled messages (streaming input)

```python
import base64
async def message_with_image(path: str, question: str):
    data = base64.b64encode(open(path, "rb").read()).decode()
    yield {"type": "user", "message": {"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
        {"type": "text", "text": question},
    ]}}

await client.query(message_with_image("screenshot.png", "What is wrong in this UI?"))
async for m in client.receive_response():
    ...
```

Pair every `client.query()` with one `receive_response()` loop. `receive_messages()` yields
everything forever (including messages after a result, e.g. `session_state_changed`).

Slash commands work as prompts: `"/compact"`, `"/clear"` (emits `ConversationResetMessage`),
your skills (`"/security-check"`). The init message's `data["slash_commands"]` lists them.

## 6. File checkpointing and rewind

Tracks changes made by `Write`, `Edit`, `NotebookEdit` in the main conversation (not Bash
edits such as `sed -i`, not subagent edits). Each prompt that starts a turn is a checkpoint
identified by its user message UUID.

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, UserMessage

options = ClaudeAgentOptions(
    enable_file_checkpointing=True,
    permission_mode="acceptEdits",
    extra_args={"replay-user-messages": None},     # REQUIRED to receive UUIDs
)
checkpoints: list[str] = []
async with ClaudeSDKClient(options) as client:
    await client.query("Refactor the authentication module")
    async for m in client.receive_response():
        # a prompt (not a tool result) => checkpoint
        if isinstance(m, UserMessage) and m.uuid and m.tool_use_result is None and m.parent_tool_use_id is None:
            checkpoints.append(m.uuid)
    if tests_fail():
        await client.rewind_files(checkpoints[0])  # restore files to before that prompt
```

- Rewind restores files only; the conversation stays.
- Rewind later: resume the session with `enable_file_checkpointing=True`, send `""`, then call
  `rewind_files(uuid)` inside the response loop.
- Forked sessions don't carry checkpoints.
- For full safety (Bash edits, subagents) also use git: commit/stash before the run.
