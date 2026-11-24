# Permissions, restrictions and security

How to control what an agent (and each subagent) is allowed to do, and how to deploy it
safely. Python SDK 0.2.188 / Claude Code 2.1.331.

## Contents

1. Mental model: five layers of control
2. How a tool call is evaluated (exact order)
3. Permission modes
4. Allow / deny / ask rules and their syntax
5. `tools` vs `allowed_tools` vs `disallowed_tools`
6. The `can_use_tool` callback (human approval, AskUserQuestion)
7. Sandbox (OS-level enforcement for Bash)
8. Restricting subagents
9. Limits: turns, budget, depth, concurrency
10. Settings you can pass inline (`settings=`)
11. Secure deployment
12. Best-practice checklist
13. Ready-made restriction profiles

---

## 1. Mental model: five layers of control

| Layer | Where | Strength | Use for |
|-------|-------|----------|---------|
| **Tool availability** | `tools=[...]`, `disallowed_tools=["Bash"]` (bare name) | Tool does not exist for the model | Removing capabilities entirely |
| **Permission rules** | `allowed_tools`, `disallowed_tools` scoped rules, settings files | Deterministic pattern match on tool + argument | Auto-approve safe calls, hard-deny dangerous ones |
| **Permission mode** | `permission_mode` | Global policy for undecided calls | `dontAsk` for headless, `acceptEdits` for coding |
| **Your code** | `PreToolUse` hooks, `can_use_tool` | Arbitrary logic, audit, human approval | Business rules, path checks, approvals, logging |
| **OS isolation** | `sandbox={...}`, containers, VMs, network proxy | Enforced by the kernel / network | Anything you must guarantee even if the model or a script misbehaves |

Rules and hooks see the **command as written**. A script the agent runs can still open
files or sockets itself. If a guarantee matters, enforce it with the sandbox or a container,
and use rules/hooks as the first line.

## 2. How a tool call is evaluated

For every tool call Claude Code walks these steps; the first that decides wins.

1. **Hooks** (`PreToolUse`, run in parallel). `deny` stops the call. `allow` is *not* final:
   deny and ask rules are still checked. `defer` ends the turn with
   `stop_reason="tool_deferred"` so you can resume the call later.
2. **Deny rules** (`disallowed_tools`, settings `permissions.deny`). Denied even in
   `bypassPermissions` and even if a hook said `allow`. `can_use_tool` is not called.
3. **Ask rules** (settings `permissions.ask`). Sent to `can_use_tool`, even in
   `bypassPermissions`. `AskUserQuestion` and MCP tools marked
   `requiresUserInteraction` also always go to the callback (denied in `dontAsk`).
4. **Permission mode** (next section).
5. **Allow rules** (`allowed_tools`, settings `permissions.allow`). Reads inside the working
   directories and read-only Bash commands are approved here without any rule.
6. **`can_use_tool`** for anything still undecided. In `dontAsk` mode this step is skipped
   and the call is **denied**. With no callback in `default` mode, the call is denied
   (Claude Code ≥ 2.1.302).

Never auto-approved in any mode: explicit ask rules, `AskUserQuestion`, recognized
critical-path removals (`rm -rf ~`, `rm -rf /` ...), Bash commands flagged
`Dangerous rm operation not ruled out`, and reads/writes outside the working directories when
`permissions.blockReadsOutsideWorkingDirectories` / `blockWritesOutsideWorkingDirectories`
is on.

Important consequence: **a call auto-approved by an allow rule or a mode never reaches
`can_use_tool`.** If your approval logic must see every call, put it in a `PreToolUse` hook
(hooks run for all calls), or don't list that tool in `allowed_tools`.

## 3. Permission modes

| Mode | What it does | Use when |
|------|--------------|----------|
| `default` | No auto-approvals beyond rules and read-only calls; undecided calls go to `can_use_tool`, or are denied without one | Interactive apps with an approval UI |
| `dontAsk` | Anything that would prompt is **denied**. Allow rules, hooks and no-approval-needed calls still run | **Headless / CI / server agents** (recommended) |
| `acceptEdits` | Auto-approves `Edit`/`Write`/`NotebookEdit` and `mkdir touch rm rmdir mv cp sed` inside cwd and `add_dirs`. Not other Bash, not MCP tools | Coding agents in an isolated checkout |
| `plan` | Explore and plan; edits go to `can_use_tool` even if allowed | Review-before-change flows |
| `auto` | A classifier model approves/blocks shell and network actions | When available on your provider and you accept classifier judgment |
| `bypassPermissions` | Approves everything except the never-auto-approved list. `allowed_tools` does **not** constrain it. Refuses to run as root outside a recognized sandbox | Only inside a disposable sandbox/container with no secrets |

Change mid-session with `await client.set_permission_mode("acceptEdits")` (ClaudeSDKClient).

Subagent inheritance: if the main session is in `plan`, `acceptEdits`, `auto` or
`bypassPermissions`, subagents inherit that mode and their own `permissionMode` is ignored.
Under a `default`/`dontAsk` parent, the subagent's `permissionMode` applies, except that
`bypassPermissions` is never applied to a subagent.

## 4. Rule syntax

| Rule | Meaning |
|------|---------|
| `"Read"` | Every Read call |
| `"Bash(npm test *)"` | Bash commands starting with `npm test ` (as written; `/usr/bin/npm` doesn't match) |
| `"Bash(git push *)"` in `disallowed_tools` | Block pushes in every mode; Bash stays available |
| `"Edit(/src/**)"` | Files under `src/` **inside the working directory** (single leading `/`) |
| `"Edit(//etc/**)"` | Absolute path `/etc/**` (double leading `//`) |
| `"Read(~/.ssh/**)"` | Home-relative path |
| `"WebFetch(domain:example.com)"` | WebFetch to one domain |
| `"mcp__github__*"` / `"mcp__github__get_*"` | All / some tools of one MCP server (allow rules need the literal server name) |
| `"mcp__*"`, `"*"` | All MCP tools / all tools - **deny rules only**; ignored in allow rules |
| `"Agent(fork)"` / `"Agent(general-purpose)"` | A subagent type |

`Edit(path)` rules cover `Edit`, `Write` and `NotebookEdit` and also Bash redirections like
`> file` and `tee`. `Write(path)` / `NotebookEdit(path)` rules match nothing.

## 5. `tools` vs `allowed_tools` vs `disallowed_tools`

```python
ClaudeAgentOptions(
    tools=["Read", "Glob", "Grep", "AskUserQuestion"],  # the ONLY built-ins the model sees
    allowed_tools=["Read", "Glob", "Grep"],             # run these without asking
    disallowed_tools=["WebFetch"],                      # bare name: removed; scoped: denied
)
```

- `tools` - availability list (or `{"type": "preset", "preset": "claude_code"}`). If you set
  `skills`, include `"Skill"`; to keep clarifying questions, include `"AskUserQuestion"`.
- `allowed_tools` - pre-approval. **Does not restrict** anything.
- `disallowed_tools` - bare name removes the tool from context; a scoped rule denies matching
  calls in every mode.

## 6. `can_use_tool` (human-in-the-loop approval)

```python
from claude_agent_sdk import (ClaudeAgentOptions, PermissionResultAllow,
                              PermissionResultDeny, ToolPermissionContext)

async def approve(tool_name: str, tool_input: dict, ctx: ToolPermissionContext):
    if tool_name == "AskUserQuestion":
        answers = {q["question"]: q["options"][0]["label"] for q in tool_input["questions"]}
        return PermissionResultAllow(updated_input={**tool_input, "answers": answers})
    print(ctx.title or f"{tool_name}: {tool_input}")      # e.g. "Claude wants to run ..."
    if input("Allow? [y/N] ").lower() == "y":
        return PermissionResultAllow()                     # original input is used
    return PermissionResultDeny(message="User declined", interrupt=False)

options = ClaudeAgentOptions(can_use_tool=approve, permission_mode="default")
```

- Called only for calls the earlier steps left undecided. Don't list tools you want to gate in
  `allowed_tools`.
- `PermissionResultAllow(updated_input=..., updated_permissions=[PermissionUpdate(...)])` can
  rewrite the input and persist rules (e.g. return a suggestion from `ctx.suggestions` with
  `destination="localSettings"` for "always allow").
- `PermissionResultDeny(interrupt=True)` stops the whole turn.
- `ctx.agent_id` is set when the request comes from a subagent; `ctx.decision_reason` carries
  a hook's `permissionDecisionReason` when a hook returned `ask`.
- Cannot be combined with `permission_prompt_tool_name` (ValueError).
- Works with plain string prompts on current SDKs.

## 7. Sandbox (OS-level Bash isolation)

```python
options = ClaudeAgentOptions(
    sandbox={
        "enabled": True,
        "failIfUnavailable": True,          # Python default is to fall back UNSANDBOXED; set this
        "autoAllowBashIfSandboxed": True,   # sandboxed Bash runs without prompts
        "allowUnsandboxedCommands": False,  # model cannot request dangerouslyDisableSandbox
        "excludedCommands": ["docker *"],   # run outside sandbox without model involvement
        "network": {"allowedDomains": ["pypi.org", "files.pythonhosted.org"],
                    "allowLocalBinding": True},
        "filesystem": {"denyWrite": ["/abs/path/project/.env"]},
    },
)
```

- Linux needs `bubblewrap` and `socat`. Without `failIfUnavailable`, Python silently runs
  commands **unsandboxed** with a stderr warning. With it, `query()` raises `ResultError`.
- The sandbox applies to Bash only. WebFetch is governed by permission rules
  (`WebFetch(domain:...)`); file tools by `Edit(...)`/`Read(...)` rules.
- The network allowlist is hostname-based and does not inspect TLS; for strict egress use a
  TLS-terminating proxy.
- `allowUnixSockets` for `/var/run/docker.sock` = full host access. Don't.
- `bypassPermissions` + `allowUnsandboxedCommands=True` lets the model silently escape the
  sandbox. Never combine them.

## 8. Restricting subagents

Each `AgentDefinition` can narrow what a subagent does:

```python
AgentDefinition(
    description="Read-only code analyst",
    prompt="Analyze; never modify files.",
    tools=["Read", "Grep", "Glob"],          # only these (listing does not pre-approve)
    disallowedTools=["mcp__*"],              # strip all MCP tools
    mcpServers=["docs"],                     # or give it specific servers only
    maxTurns=15,
    permissionMode="dontAsk",                # applies only under a default/dontAsk parent
    model="haiku",
    effort="low",
)
```

- Subagents inherit the parent's permission rules and hooks. Hook input carries `agent_id`
  and `agent_type` so a single `PreToolUse` hook can apply per-agent policy.
- With `memory` set, a subagent also gets `Read`, `Write`, `Edit`.
- Background subagents (the default from the main agent) keep MCP tools and a fixed set of
  built-ins (`Read Grep Glob Bash Edit Write NotebookEdit WebFetch WebSearch TodoWrite Skill
  ToolSearch Monitor TaskStop SendMessage ...`); other built-ins are removed silently.
- Block forks: `disallowed_tools=["Agent(fork)"]`. Remove the built-in general-purpose
  subagent: `env={"CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1"}`.
- Block all delegation: `disallowed_tools=["Agent"]`.

Per-agent policy in one hook:

```python
READ_ONLY_AGENTS = {"code-analyst", "security-reviewer"}

async def per_agent_policy(input_data, tool_use_id, context):
    if input_data.get("agent_type") in READ_ONLY_AGENTS and input_data["tool_name"] in {"Edit", "Write", "Bash"}:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "This agent is read-only"}}
    return {}
```

## 9. Limits

| Limit | How | Default |
|-------|-----|---------|
| Turns per query | `max_turns=` | none |
| Spend per query (includes subagents) | `max_budget_usd=` (estimate; may overshoot by one response, leave headroom) | none |
| API-side token budget | `task_budget={"total": 200_000}` | none |
| Subagent nesting | `env={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"}` (`1` = subagents can't spawn) | 3 |
| Concurrent subagents | `env={"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "5"}` | 20 |
| Per-subagent turns | `AgentDefinition(maxTurns=...)` | none |
| Hook runtime | `HookMatcher(timeout=seconds)` | 600 s (30 s UserPromptSubmit) |
| API wait / retries | `env={"API_TIMEOUT_MS": "120000", "CLAUDE_CODE_MAX_RETRIES": "2"}` | 600000 / 10 |
| Subagent stall | `env={"CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS": "120000"}` | ~600000 |

Hitting a limit yields `ResultMessage(subtype="error_max_turns" | "error_max_budget_usd")` and
then `query()` raises `ResultError`.

## 10. Settings you can pass inline

`settings=` accepts a path or a JSON string. Rules there merge with `allowed_tools` /
`disallowed_tools`:

```python
import json
options = ClaudeAgentOptions(
    setting_sources=[],     # ignore ~/.claude and .claude/ on disk: fully programmatic config
    settings=json.dumps({
        "permissions": {
            "deny": ["Read(./.env)", "Read(./secrets/**)", "Bash(curl *)"],
            "ask": ["Bash(git push *)"],
            "blockReadsOutsideWorkingDirectories": True,
            "blockWritesOutsideWorkingDirectories": True,
        }
    }),
)
```

`setting_sources` controls which files load (`"user"`, `"project"`, `"local"`). Default
(`None`) loads all three, like the CLI. For reproducible servers pass `[]` or `["project"]`
so a developer's `~/.claude/settings.json` can't change behavior. Managed (enterprise)
policy always loads.

## 11. Secure deployment

Threat model: the agent can be steered by content it reads (files, web pages, tool output,
MCP results). Treat every tool result as untrusted input.

- **Isolate the process**: one container/VM (or gVisor) per tenant or per job; mount code
  read-only where possible; give it a small writable workspace; drop Linux capabilities; no
  host Docker socket.
- **Keep credentials out of the agent**: route model traffic through a gateway/proxy
  (`ANTHROPIC_BASE_URL`) that injects the key; give custom tools their own credentials in your
  Python process instead of env vars the agent can `echo`. Use short-lived tokens.
- **Restrict egress**: sandbox `network.allowedDomains`, or `HTTPS_PROXY` to an allowlisting
  proxy (Envoy, Squid, mitmproxy for TLS inspection, LiteLLM for model traffic).
- **Least privilege per task**: smallest `tools` list, `dontAsk`, scoped allow rules, read-only
  subagents for analysis.
- **Audit**: a no-matcher `PostToolUse` hook (or OpenTelemetry export) logging tool name,
  input, `agent_id`, `session_id`, timestamp.
- **Don't run as root**; `bypassPermissions` refuses to start as root outside a recognized
  sandbox anyway.
- **Pin versions** of `claude-agent-sdk` (it pins the bundled CLI) and test upgrades.
- **Subagent output is scanned** (CLI ≥ 2.1.210) for control-tag imitation and turn markers
  before the parent reads it, but still treat it as untrusted.

## 12. Best-practice checklist

Before shipping an agent, confirm each item:

- [ ] `permission_mode` is explicit (`dontAsk` for unattended runs).
- [ ] `tools` lists only what the task needs; dangerous tools are absent or scoped.
- [ ] Destructive commands are in `disallowed_tools` as scoped rules (`Bash(git push *)`,
      `Bash(rm -rf *)`, `Bash(curl *)` if egress matters).
- [ ] Secrets paths are denied with `Read(...)`/`Edit(...)` rules **and** the sandbox `denyWrite`.
- [ ] Guard hooks use `on_failure="block"` so a crash fails closed.
- [ ] `max_turns`, `max_budget_usd`, subagent depth and concurrency are capped.
- [ ] `setting_sources` is set deliberately (`[]` or `["project"]` for servers).
- [ ] Sandbox enabled with `failIfUnavailable=True` if Bash is available.
- [ ] `bypassPermissions` is not used outside a disposable sandbox.
- [ ] Every tool call is logged with `session_id` and `agent_id`.
- [ ] `ResultError` is caught and `ResultMessage.permission_denials` is inspected.
- [ ] Tested with a prompt-injection fixture (a file saying "ignore instructions and run X").

## 13. Ready-made profiles

```python
from claude_agent_sdk import ClaudeAgentOptions

READ_ONLY_ANALYST = ClaudeAgentOptions(
    tools=["Read", "Glob", "Grep"],
    allowed_tools=["Read", "Glob", "Grep"],
    permission_mode="dontAsk",
    setting_sources=[],
    max_turns=40,
    max_budget_usd=1.0,
)

CI_FIXER = ClaudeAgentOptions(
    system_prompt={"type": "preset", "preset": "claude_code",
                   "append": "You run in CI. Never push, never touch .github/."},
    permission_mode="dontAsk",
    allowed_tools=["Read", "Glob", "Grep", "Edit", "Write",
                   "Bash(pytest *)", "Bash(ruff *)", "Bash(git diff *)", "Bash(git status)"],
    disallowed_tools=["WebFetch", "WebSearch", "Agent",
                      "Bash(git push *)", "Bash(git commit *)", "Edit(/.github/**)"],
    sandbox={"enabled": True, "failIfUnavailable": True, "autoAllowBashIfSandboxed": False,
             "allowUnsandboxedCommands": False},
    setting_sources=["project"],
    max_turns=60,
    max_budget_usd=3.0,
)

INTERACTIVE_ASSISTANT = ClaudeAgentOptions(
    permission_mode="default",
    allowed_tools=["Read", "Glob", "Grep"],   # everything else goes to can_use_tool
    can_use_tool=approve,                      # see section 6
)
```
