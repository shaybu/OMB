# Complete recipes (Python SDK 0.2.188)

Each recipe is a full program. Copy, then adjust paths, tools and prompts.

## 1. Locked-down read-only analyst (headless, JSON output)

```python
import asyncio, json
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, ResultError

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "issues": {"type": "array", "items": {
            "type": "object",
            "properties": {"file": {"type": "string"}, "line": {"type": "integer"},
                           "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                           "message": {"type": "string"}},
            "required": ["file", "severity", "message"]}},
    },
    "required": ["summary", "issues"],
}

async def analyze(repo: str) -> dict | None:
    options = ClaudeAgentOptions(
        cwd=repo,
        tools=["Read", "Glob", "Grep"],
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="dontAsk",
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
        max_turns=40,
        max_budget_usd=1.0,
    )
    try:
        async for m in query(prompt="Find error-handling bugs in this repo.", options=options):
            if isinstance(m, ResultMessage) and m.subtype == "success" and not m.is_error:
                return m.structured_output
    except ResultError as e:
        print(f"failed: {e.subtype} {e.terminal_reason} {e.errors}")
    return None

if __name__ == "__main__":
    print(json.dumps(asyncio.run(analyze(".")), indent=2))
```

## 2. Coding agent with guards, audit log and checkpoint rollback

```python
import asyncio, json, re, time
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions, HookMatcher,
                              ResultMessage, UserMessage)

def deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": reason}}

async def guard_bash(inp, tool_use_id, ctx):
    cmd = inp["tool_input"].get("command", "")
    if re.search(r"\b(sudo|curl|wget|ssh|scp)\b|git\s+push|rm\s+-rf", cmd):
        return deny(f"Command not allowed: {cmd}")
    return {}

async def guard_paths(inp, tool_use_id, ctx):
    path = inp["tool_input"].get("file_path", "")
    if any(p in path for p in (".env", ".git/", "secrets")):
        return deny("Protected path")
    return {}

async def audit(inp, tool_use_id, ctx):
    with open("audit.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), "tool": inp.get("tool_name"),
                            "agent": inp.get("agent_type", "main"),
                            "input": inp.get("tool_input")}, default=str) + "\n")
    return {}

async def main():
    options = ClaudeAgentOptions(
        cwd="/work/repo",
        system_prompt={"type": "preset", "preset": "claude_code",
                       "append": "Make minimal changes. Run pytest after editing."},
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Glob", "Grep", "Bash(pytest *)", "Bash(git diff *)"],
        disallowed_tools=["WebFetch", "WebSearch"],
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[guard_bash], on_failure="block"),
                HookMatcher(matcher="Write|Edit|NotebookEdit", hooks=[guard_paths], on_failure="block"),
                HookMatcher(hooks=[audit]),
            ],
        },
        enable_file_checkpointing=True,
        extra_args={"replay-user-messages": None},
        max_turns=50,
        max_budget_usd=3.0,
    )
    first_checkpoint = None
    async with ClaudeSDKClient(options) as client:
        await client.query("Fix the failing test in tests/test_auth.py")
        result = None
        async for m in client.receive_response():
            if isinstance(m, UserMessage) and m.uuid and first_checkpoint is None \
                    and m.tool_use_result is None and m.parent_tool_use_id is None:
                first_checkpoint = m.uuid
            if isinstance(m, ResultMessage):
                result = m
        if result is None or result.is_error or result.subtype != "success":
            if first_checkpoint:
                await client.rewind_files(first_checkpoint)
                print("Rolled back file changes")
        else:
            print(result.result)

asyncio.run(main())
```

## 3. Parallel review with subagents + tracking

```python
import asyncio
from claude_agent_sdk import (query, ClaudeAgentOptions, AgentDefinition, HookMatcher,
                              ResultMessage, TaskNotificationMessage)

READ_ONLY = ["Read", "Glob", "Grep"]

AGENTS = {
    "style-checker": AgentDefinition(
        description="Checks style, naming and readability. Use for style reviews.",
        prompt="Report style issues as `file:line - issue`. Max 15 items.",
        tools=READ_ONLY, model="haiku", maxTurns=15),
    "security-scanner": AgentDefinition(
        description="Finds security vulnerabilities. Use for security reviews.",
        prompt="Report vulnerabilities as `file:line - severity - issue - fix`. Max 15 items.",
        tools=READ_ONLY, model="sonnet", maxTurns=25),
    "test-coverage": AgentDefinition(
        description="Finds untested code paths. Use for test coverage reviews.",
        prompt="List important untested functions with file:line. Max 15 items.",
        tools=READ_ONLY + ["Bash"], maxTurns=20),
}

async def on_stop(inp, tool_use_id, ctx):
    print(f"  ✓ {inp['agent_type']} finished")
    return {}

async def main():
    options = ClaudeAgentOptions(
        allowed_tools=READ_ONLY + ["Agent", "Bash(pytest --co *)"],
        permission_mode="dontAsk",
        agents=AGENTS,
        hooks={"SubagentStop": [HookMatcher(hooks=[on_stop])]},
        env={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1",
             "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "3"},
        max_budget_usd=4.0,
        max_turns=30,
    )
    prompt = ("Review src/ by running style-checker, security-scanner and test-coverage IN PARALLEL. "
              "Wait for all three, then produce one prioritized list (security first).")
    try:
        async for m in query(prompt=prompt, options=options):
            if isinstance(m, TaskNotificationMessage):
                print(f"  task {m.status}: {m.summary[:80]}")
            elif isinstance(m, ResultMessage):
                print(m.result)
                print(f"cost ${m.total_cost_usd:.3f}")
    except Exception as e:
        print(f"ended with error: {e}")

asyncio.run(main())
```

## 4. Fan-out over many items from Python (deterministic orchestration)

```python
import asyncio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

OPTS = ClaudeAgentOptions(tools=["Read"], allowed_tools=["Read"], permission_mode="dontAsk",
                          setting_sources=[], model="haiku", max_turns=5, max_budget_usd=0.2)

async def summarize(path: Path, sem: asyncio.Semaphore) -> tuple[str, str]:
    async with sem:
        text = "ERROR"
        try:
            async for m in query(prompt=f"Summarize {path} in 2 sentences.", options=OPTS):
                if isinstance(m, ResultMessage) and m.subtype == "success":
                    text = m.result or ""
        except Exception as e:
            text = f"ERROR: {e}"
        return str(path), text

async def main():
    files = sorted(Path("docs").glob("*.md"))
    sem = asyncio.Semaphore(4)                 # each query() is a separate CLI process
    for path, summary in await asyncio.gather(*(summarize(f, sem) for f in files)):
        print(f"{path}: {summary}")

asyncio.run(main())
```

## 5. Interactive assistant with approvals and clarifying questions

```python
import asyncio
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock,
                              PermissionResultAllow, PermissionResultDeny, ToolPermissionContext)

async def ask_user(tool_input: dict) -> PermissionResultAllow:
    answers = {}
    for q in tool_input.get("questions", []):
        print(f"\n{q['question']}")
        for i, opt in enumerate(q["options"], 1):
            print(f"  {i}. {opt['label']} - {opt.get('description', '')}")
        raw = input("Choice(s), comma-separated, or free text: ").strip()
        picks = [q["options"][int(x) - 1]["label"] for x in raw.split(",") if x.strip().isdigit()]
        answers[q["question"]] = ", ".join(picks) if picks else raw
    return PermissionResultAllow(updated_input={**tool_input, "answers": answers})

async def approve(tool_name: str, tool_input: dict, ctx: ToolPermissionContext):
    if tool_name == "AskUserQuestion":
        return await ask_user(tool_input)
    print(f"\n[{ctx.title or tool_name}] {tool_input}")
    if input("Allow? [y/N] ").strip().lower() == "y":
        return PermissionResultAllow()
    return PermissionResultDeny(message="User declined this action")

async def main():
    options = ClaudeAgentOptions(
        permission_mode="default",
        allowed_tools=["Read", "Glob", "Grep"],   # everything else asks
        can_use_tool=approve,
    )
    async with ClaudeSDKClient(options) as client:
        while (prompt := input("\nYou: ").strip()) not in ("", "exit"):
            await client.query(prompt)
            async for m in client.receive_response():
                if isinstance(m, AssistantMessage) and not m.parent_tool_use_id:
                    for b in m.content:
                        if isinstance(b, TextBlock):
                            print(b.text, end="")

asyncio.run(main())
```

## 6. Custom tools + MCP status check (optionally through a gateway)

```python
import asyncio, json, os
from typing import Any
from claude_agent_sdk import (query, tool, create_sdk_mcp_server, ClaudeAgentOptions,
                              ToolAnnotations, ResultMessage, SystemMessage)

TICKETS = {"QA-1": {"status": "open", "title": "Login fails on Android 15"}}

@tool("get_ticket", "Get a QA ticket by key, e.g. QA-1", {"key": str},
      annotations=ToolAnnotations(readOnlyHint=True))
async def get_ticket(args: dict[str, Any]) -> dict[str, Any]:
    t = TICKETS.get(args["key"])
    if not t:
        return {"content": [{"type": "text", "text": f"No ticket {args['key']}. Known: {list(TICKETS)}"}],
                "is_error": True}
    return {"content": [{"type": "text", "text": json.dumps(t)}]}

qa = create_sdk_mcp_server(name="qa", version="1.0.0", tools=[get_ticket])

async def main():
    options = ClaudeAgentOptions(
        mcp_servers={"qa": qa},
        strict_mcp_config=True,
        tools=["Read", "Grep"],
        allowed_tools=["mcp__qa__get_ticket", "Read", "Grep"],
        permission_mode="dontAsk",
        model="sonnet",
        env={
            "ANTHROPIC_BASE_URL": os.environ.get("GATEWAY_URL", "https://api.anthropic.com"),
            "ANTHROPIC_AUTH_TOKEN": os.environ.get("GATEWAY_TOKEN", ""),
            "API_TIMEOUT_MS": "180000",
        },
        max_turns=10,
    )
    async for m in query(prompt="Summarize ticket QA-1 and suggest a test case.", options=options):
        if isinstance(m, SystemMessage) and m.subtype == "init":
            bad = [s for s in m.data.get("mcp_servers", []) if s.get("status") in ("failed", "needs-auth")]
            if bad:
                print("MCP problems:", bad)
        elif isinstance(m, ResultMessage):
            print(m.result)

asyncio.run(main())
```

## 7. Plan, approve, then execute (human gate between phases)

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage

async def main():
    async with ClaudeSDKClient(ClaudeAgentOptions(permission_mode="plan",
                                                  allowed_tools=["Read", "Glob", "Grep"])) as client:
        await client.query("Plan how to add rate limiting to the API. Don't change files yet.")
        async for m in client.receive_response():
            if isinstance(m, ResultMessage):
                print(m.result)
        if input("Execute this plan? [y/N] ").lower() != "y":
            return
        await client.set_permission_mode("acceptEdits")
        await client.query("Implement the plan now, then run the tests.")
        async for m in client.receive_response():
            if isinstance(m, ResultMessage):
                print(m.subtype, m.result)

asyncio.run(main())
```

## 8. Chief of staff: coordinator managing persistent workers

A coordinator agent with no file access manages a team of long-lived worker sessions through
five tools your code implements (`list_team`, `assign_task`, `check_tasks`, `wait_for_tasks`,
`message_worker`). Design notes: subagents-orchestration.md §10. Edit `ROLES` to define your
team. Run: `python chief_of_staff.py "your goal"`.

```python
from __future__ import annotations

import asyncio
import itertools
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

PROJECT_DIR = "."
MAX_PARALLEL_WORKERS = 3          # each worker is its own Claude Code process
WAIT_LIMIT_S = 240                # keep each tool call bounded

# --------------------------------------------------------------------------- team roster
# Each role gets its own least-privilege profile. Edit freely.
ROLES: dict[str, dict[str, Any]] = {
    "researcher": {
        "about": "Reads code and docs, answers questions, maps the codebase. Read-only.",
        "options": dict(tools=["Read", "Glob", "Grep"], allowed_tools=["Read", "Glob", "Grep"],
                        permission_mode="dontAsk", model="sonnet", max_turns=30),
    },
    "security": {
        "about": "Finds security issues (auth, injection, secrets). Read-only.",
        "options": dict(tools=["Read", "Glob", "Grep"], allowed_tools=["Read", "Glob", "Grep"],
                        permission_mode="dontAsk", model="sonnet", max_turns=30),
    },
    "engineer": {
        "about": "Implements code changes and runs tests. Can edit files and run pytest.",
        "options": dict(tools=["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
                        allowed_tools=["Read", "Glob", "Grep", "Edit", "Write", "Bash(pytest *)"],
                        disallowed_tools=["Bash(git push *)", "Bash(rm -rf *)", "WebFetch", "WebSearch"],
                        permission_mode="dontAsk", max_turns=50),
    },
}


# --------------------------------------------------------------------------- task board
@dataclass
class Task:
    id: str
    role: str
    title: str
    instructions: str
    status: str = "queued"          # queued | running | done | failed
    result: str = ""
    cost_usd: float = 0.0
    future: asyncio.Task | None = field(default=None, repr=False)

    def view(self, full: bool = False) -> dict[str, Any]:
        r = self.result if full else self.result[:300]
        return {"id": self.id, "role": self.role, "title": self.title,
                "status": self.status, "result": r, "cost_usd": round(self.cost_usd, 4)}


# --------------------------------------------------------------------------- workers
class Worker:
    """A persistent Claude session for one role. Remembers its earlier tasks."""

    def __init__(self, role: str, spec: dict[str, Any]):
        self.role = role
        self.options = ClaudeAgentOptions(
            cwd=PROJECT_DIR,
            setting_sources=["project"],
            system_prompt={"type": "preset", "preset": "claude_code", "append": (
                f"You are the team's {role}. {spec['about']} "
                "You report to a chief of staff. Finish with a concise report: "
                "what you did, findings as `file:line - issue`, and open questions."
            )},
            max_budget_usd=2.0,
            **spec["options"],
        )
        self.client: ClaudeSDKClient | None = None
        self.lock = asyncio.Lock()          # one task at a time per worker
        self.spent = 0.0

    async def ask(self, prompt: str) -> tuple[str, float]:
        async with self.lock:
            if self.client is None:
                self.client = ClaudeSDKClient(self.options)
                await self.client.connect()
            await self.client.query(prompt)
            text, total = [], self.spent
            async for m in self.client.receive_response():
                if isinstance(m, AssistantMessage) and not m.parent_tool_use_id:
                    text += [b.text for b in m.content if isinstance(b, TextBlock)]
                elif isinstance(m, ResultMessage):
                    total = m.total_cost_usd or total   # cumulative for this session
                    if m.is_error or m.subtype != "success":
                        raise RuntimeError(f"{m.subtype}: {m.result or m.errors}")
                    if m.result:
                        text = [m.result]
            cost, self.spent = total - self.spent, total
            return "\n".join(text).strip(), cost

    async def close(self):
        if self.client:
            await self.client.disconnect()


class Team:
    def __init__(self):
        self.workers = {r: Worker(r, s) for r, s in ROLES.items()}
        self.tasks: dict[str, Task] = {}
        self.ids = itertools.count(1)
        self.slots = asyncio.Semaphore(MAX_PARALLEL_WORKERS)

    async def _run(self, task: Task):
        async with self.slots:
            task.status = "running"
            log(f"▶ {task.id} [{task.role}] {task.title}")
            try:
                task.result, task.cost_usd = await self.workers[task.role].ask(
                    f"Task {task.id}: {task.title}\n\n{task.instructions}")
                task.status = "done"
            except Exception as e:
                task.status, task.result = "failed", f"{type(e).__name__}: {e}"
            log(f"■ {task.id} {task.status} (${task.cost_usd:.3f})")

    def assign(self, role: str, title: str, instructions: str) -> Task:
        task = Task(f"T{next(self.ids)}", role, title, instructions)
        task.future = asyncio.create_task(self._run(task))
        self.tasks[task.id] = task
        return task

    async def close(self):
        await asyncio.gather(*(w.close() for w in self.workers.values()), return_exceptions=True)


def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


def text(obj: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": obj if isinstance(obj, str) else json.dumps(obj, indent=2)}]}


def error(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": msg}], "is_error": True}


# --------------------------------------------------------------------------- chief's tools
def build_team_server(team: Team):
    @tool("list_team", "List the available worker roles and what each can do.", {})
    async def list_team(args):
        return text({r: s["about"] for r, s in ROLES.items()})

    @tool("assign_task",
          "Assign a task to a worker role. Returns immediately with a task id; the worker runs "
          "in parallel. Include everything the worker needs (paths, goals, constraints, output format).",
          {"role": str, "title": str, "instructions": str})
    async def assign_task(args):
        if args["role"] not in ROLES:
            return error(f"Unknown role {args['role']!r}. Roles: {list(ROLES)}")
        t = team.assign(args["role"], args["title"], args["instructions"])
        return text({"task_id": t.id, "status": t.status})

    @tool("check_tasks", "Show the status of all tasks (results truncated).", {})
    async def check_tasks(args):
        return text([t.view() for t in team.tasks.values()])

    @tool("wait_for_tasks",
          "Wait until the given tasks finish (or a time limit passes) and return their full results.",
          {"task_ids": list})
    async def wait_for_tasks(args):
        ids = [i for i in args["task_ids"] if i in team.tasks]
        if not ids:
            return error(f"No such tasks. Known: {list(team.tasks)}")
        pending = [team.tasks[i].future for i in ids if team.tasks[i].future]
        await asyncio.wait(pending, timeout=WAIT_LIMIT_S)
        return text([team.tasks[i].view(full=True) for i in ids])

    @tool("message_worker",
          "Send a follow-up to a worker. The worker keeps context from its earlier tasks. "
          "Waits for and returns its reply.",
          {"role": str, "message": str})
    async def message_worker(args):
        if args["role"] not in ROLES:
            return error(f"Unknown role {args['role']!r}. Roles: {list(ROLES)}")
        try:
            reply, _ = await asyncio.wait_for(team.workers[args["role"]].ask(args["message"]), WAIT_LIMIT_S)
            return text(reply)
        except Exception as e:
            return error(f"{type(e).__name__}: {e}")

    return create_sdk_mcp_server("team", "1.0.0",
                                 [list_team, assign_task, check_tasks, wait_for_tasks, message_worker])


CHIEF_PROMPT = """You are the chief of staff for a small team of AI workers.
You do not do the work yourself and you cannot read or edit files. You:
1. Break the goal into clear tasks and assign each to the best role (call list_team first).
2. Run independent tasks in parallel: assign them all, then wait_for_tasks once.
3. Review results critically. If something is missing or contradictory, send a follow-up
   with message_worker or assign a new task (e.g. ask security to review engineer's change).
4. Never assign the same files to two engineers at once.
5. Stop when the goal is met. Finish with a final report: summary, decisions, open risks,
   and which task produced each finding."""


async def main(goal: str):
    team = Team()
    chief_options = ClaudeAgentOptions(
        cwd=PROJECT_DIR,
        system_prompt=CHIEF_PROMPT,
        mcp_servers={"team": build_team_server(team)},
        strict_mcp_config=True,
        tools=[],                                  # no built-in tools: coordination only
        allowed_tools=["mcp__team__*"],
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=40,
        max_budget_usd=2.0,                        # chief only; workers have their own budgets
        env={"API_TIMEOUT_MS": "300000"},
    )
    try:
        async with ClaudeSDKClient(chief_options) as chief:
            await chief.query(goal)
            async for m in chief.receive_response():
                if isinstance(m, AssistantMessage):
                    for b in m.content:
                        if isinstance(b, TextBlock):
                            print(b.text)
                elif isinstance(m, ResultMessage):
                    workers = sum(t.cost_usd for t in team.tasks.values())
                    log(f"\nchief ${m.total_cost_usd or 0:.3f} + workers ${workers:.3f}")
    finally:
        await team.close()


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Map the architecture of this repo and list the top 5 risks."))
```
