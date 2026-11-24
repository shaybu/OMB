# Subagents, parallelism and orchestration (Python)

Python SDK 0.2.188 / Claude Code 2.1.331.

## Contents

1. Pattern catalog: choose by requirements
2. Defining subagents (`AgentDefinition`)
3. What a subagent sees and inherits
4. Foreground vs background, parallel runs
5. Forks, nesting, named agents and SendMessage
6. Observing subagents in the stream
7. Resuming subagents and reading their transcripts
8. Capping depth, concurrency and spend
9. App-level patterns in Python (P4-P11)
10. Coordinator + persistent workers (P12)
11. Best practices
12. Troubleshooting

---

## 1. Pattern catalog: choose by requirements

Every pattern below uses only the Python Agent SDK. None is "the default": pick the one(s)
that fit the app's requirements, and combine them when needed (for example a pipeline whose
steps use subagents). If the requirements are unclear, start with **P1** and move up only
when a concrete need appears.

| # | Pattern | Who controls the flow | Choose it when | Where |
|---|---------|----------------------|----------------|-------|
| P1 | **Single agent** | Claude | One task, one context is enough. Most apps start here | SKILL.md quick start |
| P2 | **Subagents (delegation)** | Claude, turn by turn | Subtasks need isolated context, a different tool/permission profile, or can run in parallel; plan not known up front | §2-§8 |
| P3 | **Parallel subagents in one run** | Claude, with your caps | Several independent reviews/analyses of the same input | §4, recipes §3 |
| P4 | **Fan-out from Python** | Your code | The same job over many items (files, tickets, test cases); you need per-item results, retries, bounded concurrency | §9.1, recipes §4 |
| P5 | **Pipeline / prompt chain** | Your code | Fixed stages (plan → implement → test → report), each with its own options and permissions; structured hand-off between stages | §9.2 |
| P6 | **Router** | Your code (cheap classifier agent) | Requests of different kinds need different specialists, prompts or tool sets | §9.3 |
| P7 | **Evaluator-optimizer loop** | Your code | Output must meet a bar; a separate reviewer agent judges and the worker revises | §9.4 |
| P8 | **Best-of-N with forks** | Your code | Try several approaches from the same starting context, keep the best | §9.5 |
| P9 | **Human approval gate** | Your code + a person | A person must approve plans or risky actions before execution | §9.6, recipes §5, §7 |
| P10 | **Long-lived per-user/per-conversation sessions** | User + Claude | Chat or assistant products; context persists across messages and restarts | §9.7, sessions-state.md |
| P11 | **Background job worker** | Your queue | Agents triggered by events (webhook, ticket, CI) and run unattended | §9.8 |
| P12 | **Coordinator + persistent workers ("chief of staff")** | Coordinator agent inside limits your code enforces | A manager agent must assign, follow up with the same workers, and cross-review over several rounds | §10, recipes §8 |
| P13 | **Peer agents with `SendMessage`** | Claude | Named subagents need to exchange findings directly during one run | §5 |

Questions to decide quickly:
1. Is the sequence of steps known in advance? Yes → P4/P5/P7 (your code). No → P2/P3/P12 (Claude decides).
2. Do steps need **different permissions** (read-only vs edit)? → separate `query()` calls (P5/P12) or subagents with their own `tools` (P2).
3. Must a worker **remember** earlier work? → persistent sessions (P10/P12) or `resume`. Subagents start fresh.
4. Many items? → P4 with a semaphore. A few independent analyses? → P3.
5. Must a person approve? → P9. Unattended? → P11 with `dontAsk` and strict caps.
6. Need guarantees (budget, timeouts, audit, retries)? → keep the loop in Python (P4-P9, P11, P12).

## 2. Defining subagents

```python
from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions

agents = {
    "code-reviewer": AgentDefinition(
        description="Expert code reviewer. Use for quality, security and maintainability reviews.",
        prompt="You review code. Report each issue as `file:line - severity - fix`.",
        tools=["Read", "Grep", "Glob"],
        model="sonnet",
    ),
    "test-runner": AgentDefinition(
        description="Runs the test suite and analyzes failures. Use after code changes.",
        prompt="Run tests, then report failing tests and the likely root cause.",
        tools=["Bash", "Read", "Grep"],
        maxTurns=25,
        effort="low",
    ),
}

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Glob", "Agent", "Bash(pytest *)"],
    agents=agents,
)
```

`AgentDefinition` fields (Python dataclass, **camelCase** names):

| Field | Required | Notes |
|-------|----------|-------|
| `description` | yes | When to use it. Claude routes on this text: be specific ("Use for X. Do not use for Y.") |
| `prompt` | yes | The subagent's system prompt |
| `tools` | no | Allowed tool names; omit = inherit all tools available to subagents. Listing ≠ pre-approval |
| `disallowedTools` | no | Remove tools; accepts `mcp__server`, `mcp__server__*`, `mcp__*` |
| `model` | no | `"opus"`, `"sonnet"`, `"haiku"`, `"fable"`, `"inherit"`, or a full ID |
| `skills` | no | Skill names to preload into its context (first 32) |
| `memory` | no | `"user"`, `"project"`, `"local"` persistent memory (adds Read/Write/Edit) |
| `mcpServers` | no | Server names or inline `{name: config}` dicts for this agent |
| `initialPrompt` | no | First user turn when used as the main-thread agent (ignored as a subagent) |
| `maxTurns` | no | Turn cap; output is marked partial when hit |
| `background` | no | `True` = always run non-blocking |
| `effort` | no | `"low"`..`"max"` or an int |
| `permissionMode` | no | Applies only under a `default`/`dontAsk` parent; never `bypassPermissions` |

Not in Python: `autoCompactWindow`, `omitClaudeMd` (TypeScript-only).

Other ways to get subagents: markdown files in `.claude/agents/` (loaded with the `project`
setting source; programmatic agents with the same name win) and the built-in
`general-purpose` agent (always available unless
`CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1`).

## 3. What a subagent sees

A non-fork subagent starts with a **fresh context** containing:
- its own `prompt` (system prompt) and the task text Claude passes in the Agent call,
- project CLAUDE.md (if the `project` setting source is loaded),
- its tool definitions (inherited or the `tools` subset),
- the parent's extended-thinking configuration,
- the list of other named agents if it has `SendMessage`.

It does **not** see the parent's conversation, tool results, or system prompt. Only its
final message returns to the parent (the parent may summarize it; if you need it verbatim,
say so in the main prompt).

Inherited from the parent: permission rules, hooks (with `agent_id`/`agent_type` in hook
input), MCP servers (unless restricted), and the permission mode in most cases (see
permissions-security.md §3).

## 4. Foreground vs background, parallel runs

- When the **main agent** calls `Agent` without `run_in_background`, the subagent runs in the
  **background**: the tool result is `status: "async_launched"` and the report arrives in a
  later turn (as a task notification). Claude waits (`status: "completed"`) when its next step
  needs the report.
- When a **subagent** spawns another agent, it waits by default (SDK ≥ 0.2.169).
- Force behavior: say "run X and wait for it" in the prompt, or set
  `AgentDefinition(background=True)` to always background that agent.
- Multiple subagents run **concurrently** (default limit 20). Ask for it explicitly:

```python
prompt = (
    "Review the PR in parallel: run code-reviewer on src/, security-reviewer on src/auth/, "
    "and test-runner on the whole repo at the same time. Wait for all three, then merge their "
    "findings into one prioritized list."
)
```

- Background subagents keep all MCP tools plus `Read Grep Glob LSP Bash PowerShell Edit Write
  NotebookEdit WebFetch WebSearch TodoWrite Skill ToolSearch EnterWorktree ExitWorktree Monitor
  TaskStop SendMessage ...`; other built-ins (e.g. `AskUserQuestion`) are silently removed.
- A background subagent that needs permission goes through your normal permission flow
  (hooks/rules/`can_use_tool`); `ToolPermissionContext.agent_id` tells you which one.
- Stop a background task: `await client.stop_task(task_id)` (ClaudeSDKClient).
- Parallel tool calls inside a single agent: read-only tools run concurrently; mark custom
  tools `ToolAnnotations(readOnlyHint=True)` to allow that.

## 5. Forks, nesting, named agents, isolation

- **Fork**: `subagent_type: "fork"` copies the current conversation into the subagent
  (Claude Code ≥ 2.1.302, nothing to configure). Deny with `disallowed_tools=["Agent(fork)"]`.
- **Nesting**: subagents can spawn subagents up to `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`
  (default 3). Set `"1"` to forbid nested spawning.
- **Named agents / SendMessage**: when Claude names a spawned agent, agents that have the
  `SendMessage` tool can message each other by name.
- **Worktree isolation**: the Agent tool accepts `isolation: "worktree"`; the result reports
  `worktreePath` / `worktreeBranch` if the worktree was kept. Ask for it in the prompt
  ("use an isolated worktree for each implementer") when parallel agents edit the same repo.

## 6. Observing subagents in the stream

```python
from claude_agent_sdk import (AssistantMessage, ToolUseBlock, TaskStartedMessage,
                              TaskProgressMessage, TaskNotificationMessage, ResultMessage)

async for msg in query(prompt=prompt, options=options):
    if isinstance(msg, AssistantMessage):
        if msg.parent_tool_use_id:                   # produced inside a subagent
            continue
        for b in msg.content:
            if isinstance(b, ToolUseBlock) and b.name in ("Agent", "Task"):
                print("spawn", b.input.get("subagent_type"), "-", b.input.get("description"))
    elif isinstance(msg, TaskStartedMessage):
        print("task started", msg.task_id, msg.task_type, msg.description)
    elif isinstance(msg, TaskProgressMessage):
        print("progress", msg.task_id, msg.last_tool_name, msg.usage["total_tokens"])
    elif isinstance(msg, TaskNotificationMessage):
        print("task", msg.status, msg.task_id, msg.summary)
    elif isinstance(msg, ResultMessage):
        print("total cost incl. subagents:", msg.total_cost_usd)
```

- Subagent text/thinking blocks of foreground subagents are omitted unless
  `forward_subagent_text=True`.
- `TaskStartedMessage.task_type`: `local_agent` (subagent), `local_bash`, `mcp_task`, `remote_agent`.
- Hooks: `SubagentStart` / `SubagentStop` give `agent_id`, `agent_type`, and the transcript path.
- `ResultMessage.model_usage` and `total_cost_usd` include subagents; `usage` does not.

## 7. Resuming subagents and reading transcripts

The Agent tool result text contains `agentId: <id>` (custom agents and `general-purpose`;
`Explore`/`Plan` may omit it). To continue that subagent later, resume the **same session**
with the **same `agents` definitions** and mention the ID:

```python
async for m in query(prompt=f"Resume agent {agent_id} and list the 3 most complex endpoints",
                     options=ClaudeAgentOptions(agents=AGENTS, resume=session_id,
                                                allowed_tools=["Read", "Grep", "Glob", "Agent"])):
    ...
```

Offline inspection:

```python
from claude_agent_sdk import list_subagents, get_subagent_messages
for agent_id in list_subagents(session_id):
    for m in get_subagent_messages(session_id, agent_id, limit=50):
        print(agent_id, m.type, m.uuid)
```

## 8. Caps

```python
ClaudeAgentOptions(
    max_budget_usd=5.0,                                    # includes subagents; refuses new spawns at the cap
    env={
        "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1",       # default 3
        "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "5",       # default 20
        "CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS": "300000",   # abort a stalled subagent
    },
)
```

At the concurrency cap Claude gets `Concurrent subagent limit reached`; at the budget cap
`Budget limit reached`, running background subagents are stopped, and the query ends with
`error_max_budget_usd`. Newer models (Opus 5.x) delegate readily: the `claude_code` preset
tells them not to call `Agent` unless asked; with a custom prompt, add your own delegation
guidance **and** set the caps.

## 9. App-level patterns in Python (P4-P11)

Use these when you want deterministic control. Each `query()` is an independent session
(its own CLI process), so give each its own options.

### 9.1 Fan-out with bounded concurrency (P4)

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

REVIEW = ClaudeAgentOptions(tools=["Read", "Grep", "Glob"], allowed_tools=["Read", "Grep", "Glob"],
                            permission_mode="dontAsk", max_turns=20, max_budget_usd=0.5,
                            setting_sources=[])

async def run_one(prompt: str, options: ClaudeAgentOptions) -> ResultMessage | None:
    result = None
    try:
        async for m in query(prompt=prompt, options=options):
            if isinstance(m, ResultMessage):
                result = m
    except Exception as e:          # ResultError etc.; keep other workers running
        print(f"worker failed: {e}")
    return result

async def fan_out(files: list[str], limit: int = 4):
    sem = asyncio.Semaphore(limit)          # each query() is a separate process: bound it
    async def guarded(f):
        async with sem:
            return f, await run_one(f"Review {f} for bugs. Reply with a bullet list.", REVIEW)
    return await asyncio.gather(*(guarded(f) for f in files))
```

### 9.2 Pipeline with structured hand-off (P5)

```python
PLAN_SCHEMA = {"type": "object", "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
               "required": ["steps"]}

async def plan_then_implement(task: str):
    plan = await run_one(task, ClaudeAgentOptions(
        permission_mode="plan", tools=["Read", "Grep", "Glob"],
        output_format={"type": "json_schema", "schema": PLAN_SCHEMA}))
    if not plan or not plan.structured_output:
        raise RuntimeError("planning failed")
    for step in plan.structured_output["steps"]:
        await run_one(step, ClaudeAgentOptions(permission_mode="acceptEdits",
                                               allowed_tools=["Read", "Edit", "Bash(pytest *)"],
                                               max_turns=30))
```

### 9.3 Router (P6)

```python
ROUTE_SCHEMA = {"type": "object",
                "properties": {"route": {"type": "string", "enum": ["bug", "feature", "question"]}},
                "required": ["route"]}

SPECIALISTS = {
    "bug": ClaudeAgentOptions(permission_mode="acceptEdits", allowed_tools=["Read", "Edit", "Bash(pytest *)"], max_turns=40),
    "feature": ClaudeAgentOptions(permission_mode="plan", tools=["Read", "Grep", "Glob"], max_turns=30),
    "question": ClaudeAgentOptions(tools=["Read", "Grep", "Glob"], allowed_tools=["Read", "Grep", "Glob"],
                                   permission_mode="dontAsk", max_turns=15),
}

async def route_and_run(request: str):
    r = await run_one(f"Classify this request:\n{request}",
                      ClaudeAgentOptions(model="haiku", tools=[], max_turns=2,
                                         output_format={"type": "json_schema", "schema": ROUTE_SCHEMA}))
    route = r.structured_output["route"] if r and r.structured_output else "question"
    return await run_one(request, SPECIALISTS[route])
```

### 9.4 Evaluator-optimizer loop (P7)

```python
VERDICT = {"type": "object", "properties": {"pass": {"type": "boolean"}, "feedback": {"type": "string"}},
           "required": ["pass", "feedback"]}

async def refine(task: str, rounds: int = 3):
    feedback = ""
    for _ in range(rounds):
        await run_one(f"{task}\n\nReviewer feedback to address:\n{feedback}",
                      ClaudeAgentOptions(permission_mode="acceptEdits", max_turns=30))
        review = await run_one("Evaluate the change against the task. Be strict.",
                               ClaudeAgentOptions(tools=["Read", "Grep", "Glob", "Bash"],
                                                  allowed_tools=["Read", "Grep", "Glob", "Bash(pytest *)"],
                                                  permission_mode="dontAsk",
                                                  output_format={"type": "json_schema", "schema": VERDICT}))
        if review and review.structured_output and review.structured_output["pass"]:
            return True
        feedback = review.structured_output["feedback"] if review and review.structured_output else "Review failed"
    return False
```

### 9.5 Best-of-N with forked sessions (P8)

```python
from claude_agent_sdk import ClaudeAgentOptions

async def best_of_n(base_session_id: str, approaches: list[str]) -> list[tuple[str, ResultMessage | None]]:
    """Each attempt forks the same conversation, so all start with identical context."""
    async def attempt(approach: str):
        opts = ClaudeAgentOptions(resume=base_session_id, fork_session=True,
                                  tools=["Read", "Grep", "Glob"], allowed_tools=["Read", "Grep", "Glob"],
                                  permission_mode="dontAsk", max_turns=20)
        return approach, await run_one(f"Propose a solution using this approach: {approach}", opts)
    return await asyncio.gather(*(attempt(a) for a in approaches))
```

Then judge the candidates with a separate agent (structured output with a `winner` field),
or score them in code (tests, linters). If candidates edit files, give each its own copy of
the repo (`cwd=` per attempt) so they don't overwrite each other.

### 9.6 Human approval gate (P9)

Three places to put the human, from coarse to fine:
- **Between stages**: run a planning stage (`permission_mode="plan"`), show the plan, continue
  only on approval (recipes §7).
- **Per risky tool call**: `can_use_tool` callback, or a `PreToolUse` hook returning `"ask"`
  (recipes §5, hooks.md).
- **Out of band**: a `PreToolUse` hook returns `"defer"`; the turn ends with
  `stop_reason="tool_deferred"`; resume the session after approval arrives (ticket, chat).

### 9.7 Long-lived per-user sessions (P10)

```python
import dataclasses
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage

class SessionManager:
    """One ClaudeSDKClient per conversation; reconnects with resume after a restart."""
    def __init__(self, base: ClaudeAgentOptions):
        self.base, self.clients, self.session_ids = base, {}, {}

    async def send(self, conversation_id: str, text: str) -> str:
        client = self.clients.get(conversation_id)
        if client is None:
            opts = dataclasses.replace(self.base, resume=self.session_ids.get(conversation_id))
            client = self.clients[conversation_id] = ClaudeSDKClient(opts)
            await client.connect()
        await client.query(text)
        reply = ""
        async for m in client.receive_response():
            if isinstance(m, ResultMessage):
                self.session_ids[conversation_id] = m.session_id   # persist this in your DB
                reply = m.result or ""
        return reply

    async def close(self, conversation_id: str):
        if client := self.clients.pop(conversation_id, None):
            await client.disconnect()
```

Close idle clients (each is a process). For
several app servers, add `session_store=` so any host can resume (sessions-state.md §4).

### 9.8 Background job worker (P11)

```python
async def worker(queue: asyncio.Queue, options: ClaudeAgentOptions):
    while True:
        job = await queue.get()
        try:
            result = await asyncio.wait_for(run_one(job["prompt"], options), timeout=900)
            await save_result(job["id"], result)          # your persistence
        except Exception as e:
            await save_failure(job["id"], repr(e))         # retry policy is yours
        finally:
            queue.task_done()

# start N workers: [asyncio.create_task(worker(q, JOB_OPTIONS)) for _ in range(4)]
```

Unattended options: `permission_mode="dontAsk"`, explicit `tools`/`allowed_tools`,
`setting_sources=[]`, `max_turns`, `max_budget_usd`, sandbox, audit hook.

### 9.9 Shared context between steps

Either pass results explicitly in the next prompt (preferred; predictable), or reuse one
session with `ClaudeSDKClient` / `resume=session_id`, or branch with `fork_session=True`
to try alternatives from the same starting point.

## 10. Coordinator + persistent workers (P12)

Use this when you want one agent to **manage a team**: break a goal into tasks, assign them
to specialist workers, run them in parallel, follow up with the same worker, have one worker
review another's output, and write a final report. Everything is plain SDK:
`ClaudeSDKClient` sessions + in-process `@tool`s.

Architecture:

```text
your Python app
├── Coordinator ("chief"): ClaudeSDKClient, tools=[] (no file access),
│     only tools: mcp__team__list_team / assign_task / check_tasks / wait_for_tasks / message_worker
├── Task board (Python dict): id, role, status, result, cost
└── Workers: one long-lived ClaudeSDKClient per role, each with its own
      system prompt, tools, permission profile, budget; remembers its own earlier tasks
```

Why it beats letting the model improvise with subagents for this job:
- Workers **keep context** across tasks (subagents start fresh each time).
- The coordinator can **message a worker again** and get an answer from the same session.
- **Your code enforces** who can do what: per-role tools and permissions, how many workers run
  at once (semaphore), per-worker budgets, timeouts, logging of every assignment and result.
- The coordinator has **no file or shell tools**, so it can only coordinate.

Design rules:
1. Each role gets a least-privilege `ClaudeAgentOptions` (`tools`, `allowed_tools`,
   `disallowed_tools`, `permission_mode="dontAsk"`, `max_turns`, `max_budget_usd`).
2. `assign_task` returns immediately (starts an `asyncio.Task`); `wait_for_tasks` waits with a
   time limit. Keep every tool call bounded so a stuck worker can't hang the coordinator.
3. One task at a time per worker (`asyncio.Lock`); total parallelism capped by a semaphore
   (each worker is its own Claude Code process).
4. Validate tool arguments (unknown role, unknown task id) and return `is_error: True` with
   the valid options so the coordinator can correct itself.
5. Coordinator prompt: plan → list_team → assign independent tasks together → wait once →
   review critically → follow up / cross-review → stop when done → final report with sources.
6. Never give two editing workers the same files at once.
7. Close every worker session in `finally`.
8. Sum costs: coordinator `total_cost_usd` + each worker's (per-session totals are cumulative,
   so track the difference per task).

Full runnable program: [recipes.md §8](recipes.md#8-chief-of-staff-coordinator-managing-persistent-workers).

Not available from the Python SDK: the CLI's "agent teams" feature (teammates are never
spawned in SDK sessions) and the `Workflow` tool (TypeScript SDK only). The chief-of-staff
pattern covers both use cases in Python.

## 11. Best practices

1. Start with one agent; add subagents only for context isolation, parallelism, or a
   different tool/permission profile.
2. Write `description` as a routing rule: what it does, when to use it, when not to.
3. Give each subagent the **minimum tools**; reviewers and researchers should be read-only.
4. Put everything a subagent needs (paths, constraints, output format) into its task text;
   it can't see the parent conversation.
5. Ask for a compact, structured final report ("bullet list, max 15 items, file:line").
   Long reports flood the parent context.
6. Use a cheaper/faster `model` and lower `effort` for mechanical workers; keep the strongest
   model for planning and synthesis.
7. Cap depth, concurrency, turns and budget on every run that can delegate.
8. Parallelize only independent work. Parallel editors on the same files collide: give each a
   disjoint set of paths or worktree isolation.
9. Log `SubagentStart`/`SubagentStop` and `TaskNotificationMessage` so you can see what ran.
10. For deterministic multi-step processes, orchestrate in Python instead of hoping the model
    delegates the same way every time.
11. Bound app-level fan-out with a semaphore: each `query()` is a separate CLI process
    (memory + API rate limits).

## 12. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Claude does the work itself instead of delegating | Name the agent in the prompt ("Use the code-reviewer agent ..."); sharpen `description`; make sure `Agent` isn't denied |
| `subagent_type is required` | Built-in agents disabled; define the agent or unset `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS` |
| `Agent would be spawned with zero tools` | A background subagent's `tools` list contained only filtered tools; add allowed built-ins |
| `Concurrent subagent limit reached` | Lower parallelism in the prompt or raise `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` |
| Many permission prompts from subagents | Use allow rules / `PreToolUse` allow hooks (inherited by subagents) |
| Filesystem agent not loading | `setting_sources` must include `project`; a new `.claude/agents/` dir needs a restart; same-named programmatic agent overrides it |
| Can't resume a subagent | Resume the same session (`resume=`) with the same `agents` and include the `agentId` |
