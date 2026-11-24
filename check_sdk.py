#!/usr/bin/env python3
"""Print what the installed claude-agent-sdk actually supports.

Run this before writing code when you are unsure whether an option, hook event or
permission mode exists in the user's installed version:

    python scripts/check_sdk.py            # summary
    python scripts/check_sdk.py --json     # machine-readable

It only imports the package; it does not start Claude Code or call any API.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import typing


def literal_values(tp: typing.Any) -> list[str]:
    """Flatten a Literal / Union-of-Literals type into its string values."""
    out: list[str] = []
    for arg in typing.get_args(tp):
        if typing.get_origin(arg) is typing.Literal:
            out.extend(literal_values(arg))
        else:
            out.append(arg)
    return out


def main() -> int:
    try:
        import claude_agent_sdk as sdk
        from claude_agent_sdk import types as t
    except ImportError:
        print("claude-agent-sdk is not installed. Run: pip install claude-agent-sdk")
        return 1

    try:
        from claude_agent_sdk._cli_version import __cli_version__ as cli_version
    except Exception:  # private module; may move
        cli_version = "unknown"

    info = {
        "sdk_version": sdk.__version__,
        "bundled_cli_version": cli_version,
        "hook_events": literal_values(t.HookEvent),
        "permission_modes": literal_values(t.PermissionMode),
        "claude_agent_options_fields": [f.name for f in dataclasses.fields(t.ClaudeAgentOptions)],
        "agent_definition_fields": [f.name for f in dataclasses.fields(t.AgentDefinition)],
        "hook_matcher_fields": [f.name for f in dataclasses.fields(t.HookMatcher)],
        "client_methods": sorted(
            n for n in dir(sdk.ClaudeSDKClient) if not n.startswith("_")
        ),
        "exports": sorted(n for n in sdk.__all__ if not n.startswith("_")),
    }

    if "--json" in sys.argv:
        print(json.dumps(info, indent=2))
        return 0

    print(f"claude-agent-sdk {info['sdk_version']} (bundled Claude Code CLI {info['bundled_cli_version']})")
    for key in ("hook_events", "permission_modes", "agent_definition_fields",
                "hook_matcher_fields", "client_methods", "claude_agent_options_fields"):
        print(f"\n{key.replace('_', ' ')}:")
        print("  " + ", ".join(info[key]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
