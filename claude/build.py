#!/usr/bin/env python3
"""Generate the Claude Code config that derives from the opencode files.

  claude/CLAUDE.md   = the "Global engineering principles" section of
                       AGENTS.md + claude/routing.md (Claude Code's roster;
                       AGENTS.md's routing section names opencode agents)
  claude/agents/*.md = agents/*.md, converted as described below

agents/*.md stays the single source of truth for every prompt. This script
maps each opencode frontmatter to Claude Code's and rewrites the few
opencode-specific mechanics in the body (Task tool, task_id resume). Run it
after editing anything under agents/ or a model pin in opencode.jsonc;
claude/install.sh runs it too. The output is committed so diffs are
reviewable.

Mapping:
  model                         -> model (provider prefix dropped); agents
                                   without one take their pin from
                                   opencode.jsonc `agent.<name>.model`, else
                                   `inherit` (opencode subagents run the
                                   caller's model too)
  permission.task: deny         -> disallowedTools: Agent
  permission.edit: deny         -> disallowedTools: Edit, Write, NotebookEdit
  permission.webfetch: deny     -> disallowedTools: WebFetch
  permission.todowrite: deny    -> disallowedTools: TodoWrite
  permission.question: deny     -> dropped: Claude Code withholds
                                   AskUserQuestion from every subagent
  temperature, mode             -> dropped (no Claude Code equivalent)
  MCP scoping in opencode.jsonc -> disallowedTools: mcp__<server> for every
                                   server the global `permission` block
                                   denies (`<server>_*: deny`) and the
                                   agent's `agent.<name>.permission` does
                                   not re-allow. An agent with no entry
                                   there (harness-recovery) gets no scoped
                                   server. Claude Code defers MCP schemas,
                                   so this is about which servers an agent
                                   may call (several are write-capable),
                                   no longer about per-turn token cost.
"""
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = REPO / "agents"
OUT_DIR = REPO / "claude" / "agents"

# Ordered: specific rewrites before the generic `task_id` -> `agent ID`.
BODY_SUBS = [
    # harness-pipeline's warm retry: opencode resumes with Task(task_id: ...),
    # Claude Code with SendMessage to the agent ID the first call returned.
    (
        'Task(subagent_type: "harness-impl", task_id: impl_task_id,\n          prompt:',
        "SendMessage(to: impl_agent_id,\n                message:",
    ),
    ("Save the returned task_id as impl_task_id.", "Save the returned agent ID as impl_agent_id."),
    ("Record every `task_id` you receive.", "Record every agent ID you receive."),
    ("via `task_id`", "via SendMessage to your agent ID"),
    ("via task_id resumption", "via SendMessage to the saved agent ID"),
    ("(task_id resumption)", "(SendMessage to the saved agent ID)"),
    ("using the saved task_id", "via SendMessage to its saved agent ID"),
    ("Use task_id resumption", "Use SendMessage to the saved agent ID"),
    ("Task(subagent_type:", "Agent(subagent_type:"),
    ("the Task tool", "the Agent tool"),
    ("~/.config/opencode/skills", "~/.claude/skills"),
]

# Appended to specific agents, where Claude Code enforces less than opencode.
CLAUDE_NOTES = {
    "harness-pipeline": """
## Spawn allowlist (Claude Code)

Under opencode a `task` permission allowlist physically limited you to
`harness-impl`, `harness-test` and `harness-debug`. Claude Code has no
per-subagent equivalent (an `Agent(type, ...)` restriction is honoured only
for an agent running as the main thread), so here the allowlist is this
rule: spawn **only** those three types. Never spawn `harness-review`,
`harness-recovery`, `harness-pipeline` or any general-purpose agent. Your
children cannot spawn further: each has `Agent` in `disallowedTools`.
""",
}


def strip_jsonc(text: str) -> str:
    """Drop // comments outside strings, and trailing commas."""
    out, i, in_str = [], 0, False
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            i = text.index("\n", i) - 1
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def rewrite_body(text: str) -> str:
    for old, new in BODY_SUBS:
        text = text.replace(old, new)
    text = text.replace("task_id", "agent ID")
    leftovers = re.findall(r".*\b(?:opencode|Task\(|todowrite)\b.*", text)
    if leftovers:
        raise SystemExit(f"opencode-specific text left after rewrite: {leftovers}")
    return text


def block_scalar(key: str, value: str) -> str:
    lines = value.rstrip("\n").split("\n")
    return f"{key}: |-\n" + "\n".join(f"  {line}" if line else "" for line in lines) + "\n"


MCP_RULE = re.compile(r"^(.+)_\*$")


def mcp_servers(rules: dict, verdict: str) -> set[str]:
    """Servers named by `<server>_*: <verdict>` rules in an opencode permission block."""
    return {m.group(1) for key, value in rules.items() if value == verdict and (m := MCP_RULE.match(key))}


def mcp_denials(name: str, config: dict) -> list[str]:
    scoped = mcp_servers(config["permission"], "deny")
    allowed = mcp_servers(config["agent"].get(name, {}).get("permission", {}), "allow")
    unknown = allowed - scoped
    if unknown:
        raise SystemExit(f"opencode.jsonc allows {sorted(unknown)} for {name}, but no global deny scopes them")
    return [f"mcp__{server}" for server in sorted(scoped - allowed)]


def convert(src: Path, config: dict) -> str:
    name = src.stem
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", src.read_text(), re.S)
    if not m:
        raise SystemExit(f"{src}: no frontmatter")
    fm, body = yaml.safe_load(m.group(1)), m.group(2)
    perm = fm["permission"]

    pin = config["agent"].get(name, {}).get("model")
    model = (fm.get("model") or pin or "inherit").removeprefix("anthropic/")

    disallowed = []
    task = perm.get("task")
    if task == "deny":
        disallowed.append("Agent")
    elif task is not None and not isinstance(task, dict):
        raise SystemExit(f"{src}: unexpected task permission {task!r}")
    if perm.get("edit") == "deny":
        disallowed += ["Edit", "Write", "NotebookEdit"]
    if perm.get("webfetch") == "deny":
        disallowed.append("WebFetch")
    if perm.get("todowrite") == "deny":
        disallowed.append("TodoWrite")
    disallowed += mcp_denials(name, config)

    header = (
        f"# GENERATED by claude/build.py from agents/{name}.md.\n"
        f"# Edit that file (or a pin in opencode.jsonc), then re-run the script.\n"
        f"name: {name}\n"
        + block_scalar("description", rewrite_body(fm["description"]))
        + f"model: {model}\n"
        + (f"disallowedTools: {', '.join(disallowed)}\n" if disallowed else "")
    )
    return f"---\n{header}---\n{rewrite_body(body)}{CLAUDE_NOTES.get(name, '')}"


def render_claude_md() -> str:
    agents_md = (REPO / "AGENTS.md").read_text()
    start, end = "# Global engineering principles", "\n# Strength-based model routing"
    if not agents_md.startswith(start) or end not in agents_md:
        raise SystemExit(f"AGENTS.md no longer starts with {start!r} and contains {end.strip()!r}")
    principles = agents_md[: agents_md.index(end)].rstrip("\n")
    routing = (REPO / "claude" / "routing.md").read_text()
    header = (
        "<!-- GENERATED by ~/opencode-harness/claude/build.py from AGENTS.md\n"
        "     (principles) + claude/routing.md. Edit those, then re-run. -->\n\n"
    )
    return f"{header}{principles}\n\n{routing}"


def render_all() -> dict[Path, str]:
    """Every generated file, keyed by its path in the repo."""
    config = json.loads(strip_jsonc((REPO / "opencode.jsonc").read_text()))
    outputs = {REPO / "claude" / "CLAUDE.md": render_claude_md()}
    for src in sorted(SRC_DIR.glob("*.md")):
        out = convert(src, config)
        yaml.safe_load(out.split("---\n")[1])  # the frontmatter must parse
        outputs[OUT_DIR / src.name] = out
    return outputs


def main() -> None:
    outputs = render_all()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.md"):
        if stale not in outputs:
            stale.unlink()
            print(f"removed {stale.name} (no longer in agents/)")
    for path, text in outputs.items():
        path.write_text(text)
    print(f"generated claude/CLAUDE.md and {len(outputs) - 1} agents in claude/agents/")


if __name__ == "__main__":
    sys.exit(main())
