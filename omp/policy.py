"""Generate omp/extension/policy.json, the data the harness policy extension enforces.

GENERATED OUTPUT NOTICE (JSON cannot carry a header): omp/extension/policy.json
is written by omp/build.py from opencode.jsonc (global `<server>_*: deny`
rules and per-agent `<server>_*: allow` re-allows), agents/*.md (the agent
set) and the omp `spawns:` lists. Do not edit it; re-run `python3 omp/build.py`.

Shape:
  mcp.servers  every scoped MCP server (raw opencode name), sorted
  mcp.agents   agent -> allowed scoped servers, one entry per agents/*.md
               agent (human-facing build/plan are main sessions and have none)
  spawn        restricted agent -> parent agents allowed to spawn it
"""
import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("claude_build", _REPO / "claude" / "build.py")
_claude_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_claude_build)


def render_policy(config: dict, parsed_agents: dict, spawns: dict[str, list[str]], restricted: set[str]) -> str:
    """JSON text for the extension. `parsed_agents` keys are the agent names."""
    scoped = _claude_build.mcp_servers(config["permission"], "deny")
    agents = {}
    for name in sorted(parsed_agents):
        allowed = _claude_build.mcp_servers(config["agent"].get(name, {}).get("permission", {}), "allow")
        unknown = allowed - scoped
        if unknown:
            raise SystemExit(f"opencode.jsonc allows {sorted(unknown)} for {name}, but no global deny scopes them")
        agents[name] = sorted(allowed)

    spawn = {}
    for agent in sorted(restricted):
        if agent not in parsed_agents:
            raise SystemExit(f"restricted agent {agent!r} is not an agents/*.md agent")
        parents = sorted(name for name, listed in spawns.items() if agent in listed)
        if not parents:
            raise SystemExit(f"restricted agent {agent!r} has no agent whose spawns allow it (remove it from RESTRICTED_SPAWN in omp/build.py or allow it in a parent's permission.task)")
        spawn[agent] = parents

    policy = {"mcp": {"servers": sorted(scoped), "agents": agents}, "spawn": spawn}
    return json.dumps(policy, indent=2, sort_keys=False) + "\n"
