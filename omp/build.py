#!/usr/bin/env python3
"""Generate the omp (oh-my-pi) config that derives from the opencode files.

  omp/agents/*.md        = agents/*.md, converted as described below
  omp/RULES.md           = the "Global engineering principles" section of
                           AGENTS.md (omp task subagents drop AGENTS.md but
                           keep RULES.md, so the principles travel here)
  omp/AGENTS.md          = omp/routing.md (omp's roster; the AGENTS.md routing
                           section names opencode/Claude agents)
  omp/config.fragment.yml = modelRoles / modelPresets / task / bash settings
                           for the user's omp config.yml, from roles.yaml
  omp/mcp.json           = the "mcp" block of opencode.jsonc (see omp/mcp.py;
                           secrets stay references, never resolved)
  omp/extension/policy.json = per-agent MCP scoping + restricted-spawn data for
                           the omp/extension policy extension (see omp/policy.py)

agents/*.md stays the single source of truth for every prompt; roles.yaml is
the single source for role -> model and agent -> role. Run this after editing
anything under agents/, roles.yaml, AGENTS.md, omp/routing.md, the
create-harness schemas, or a pin in opencode.jsonc. The output is committed so
diffs are reviewable. `--check` writes nothing and exits 1 when anything is
stale, missing or orphaned.

Mapping (opencode frontmatter -> omp frontmatter):
  model pin                     -> model: "@<role>" from roles.yaml `agents:`;
                                   omitted for agents with no entry (they
                                   inherit the caller's model)
  permission.task allow-list    -> spawns: <allowed agents>
  permission.task absent/deny   -> no spawns. opencode injects a blanket task
                                   deny into subagents, so coder and
                                   deep-reasoner cannot spawn there either;
                                   omp matches that (decision, not a gap)
  no restricting permission     -> `tools:` omitted, omp's default toolset
                                   applies; an explicit list is emitted only
                                   when the source denies something
  permission.edit: deny         -> tools without edit, write, ast_edit
  permission.webfetch: deny     -> tools without web_search
  permission.todowrite: deny    -> tools without todo
  permission.question: deny     -> tools without ask
  mode, temperature             -> dropped (no omp equivalent)
harness-pipeline additionally loses edit and ast_edit in omp (OMP_TOOL_DENY):
its "coordinate, never implement" rule becomes enforced; it keeps `write`,
which outbound agent:// messages need.
`task` and `wait` are auto-added by omp when `spawns` is declared
(docs/task-agent-discovery.md), so they are not listed in `tools`.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("claude_build", REPO / "claude" / "build.py")
_claude_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_claude_build)
strip_jsonc = _claude_build.strip_jsonc
_mcp_spec = importlib.util.spec_from_file_location("omp_mcp", REPO / "omp" / "mcp.py")
_omp_mcp = importlib.util.module_from_spec(_mcp_spec)
_mcp_spec.loader.exec_module(_omp_mcp)
_policy_spec = importlib.util.spec_from_file_location("omp_policy", REPO / "omp" / "policy.py")
_omp_policy = importlib.util.module_from_spec(_policy_spec)
_policy_spec.loader.exec_module(_omp_policy)

# Agents whose final message must match a JSON Schema in
# skills/create-harness/schemas/<name>.schema.json. omp ignores the agent
# `output` unless `structured: true` is set on the agent (or `task.structured`
# is on), so both are emitted. omp's output validator accepts these schemas
# verbatim (`$schema`, `$id`, local `$ref` into `$defs`), so they are embedded
# unmodified.
OUTPUT_SCHEMAS = {
    "harness-research": "findings",
    "harness-pipeline": "pipeline-verdict",
    "harness-review": "review-verdict",
    "harness-recovery": "recovery",
}
AUTOLOAD_SKILLS = {"harness-review": ["pr-review"]}
# Leaf harness agents that must run inline: the pipeline needs their result
# before it can take the next step.
BLOCKING = {"harness-impl", "harness-test", "harness-debug"}
# Agents only a permitted parent (harness-pipeline) may spawn; the policy
# extension refuses every other spawn. Separate from BLOCKING: that decides
# inline execution, this decides who may spawn. harness-debug stays restricted
# (decision: the debug description's orchestrator example is rewritten for omp
# below rather than widening the guard; the pipeline owns debug routing).
RESTRICTED_SPAWN = {"harness-impl", "harness-test", "harness-debug"}

# omp built-in tool names (packages/coding-agent/src/tools/builtin-names.ts).
BASE_TOOLS = ["read", "find", "grep", "glob", "bash", "edit", "write", "ast_grep", "ast_edit", "lsp", "web_search", "todo", "ask"]
# opencode permission key -> omp tools removed when that key is `deny`.
PERMISSION_TOOLS = {
    "edit": ["edit", "write", "ast_edit"],
    "webfetch": ["web_search"],
    "todowrite": ["todo"],
    "question": ["ask"],
}
PERMISSION_KEYS = {"task", *PERMISSION_TOOLS}
# omp-only tool removals. The pipeline runner only coordinates (opencode keeps
# its edit tools only because denying them there would propagate to its
# children; omp children carry their own tool lists).
OMP_TOOL_DENY = {"harness-pipeline": ["edit", "ast_edit"]}

# omp built-in roles that roles.yaml does not declare: extra -> source role.
EXTRA_ROLES = {"slow": "reason", "plan": "reason", "advisor": "review", "commit": "smol"}

# Ordered: specific rewrites before the generic ones.
_IMPL_BLOCK = (
    '   Task(subagent_type: "harness-impl",\n'
    '        prompt: "Prompt: plan/prompts/F0N-<slug>.md")\n'
    "   Save the returned task_id as impl_task_id.\n"
)
_IMPL_RETRY = (
    '     Task(subagent_type: "harness-impl", task_id: impl_task_id,\n'
    '          prompt: "You returned <BLOCKED|empty|partial>. Your scratchpad\n'
    '                   shows: <summary>. Complete only: <remaining items>.")\n'
)
_DEBUG_BLOCK = (
    '   Task(subagent_type: "harness-debug",\n'
    '        prompt: "<symptom + changed files + impl scratchpad path>")\n'
)
_TEST_BLOCK = (
    '   Task(subagent_type: "harness-test",\n'
    '        prompt: "Finding: F0N — <title>\n'
    "                 Changed files: <list from impl output>\n"
    "                 Write tests that fail on pre-fix code and pass now.\n"
    '                 Attach the green test log.")\n'
)
# Child ids: omp qualifies a child's id with its parent's id (the runner
# `PipelineF0N` gets `PipelineF0N.ImplF0N`), and agent:// messages need the
# exact id the task call returns, so the runner records it instead of
# assuming the `name` it passed.
BODY_SUBS = [
    (
        _IMPL_BLOCK,
        '   task({context: "Finding F0N pipeline: follow the prompt file exactly.",\n'
        '         tasks: [{agent: "harness-impl", name: "ImplF0N",\n'
        '                  task: "Prompt: local://prompts/F0N-<slug>.md",\n'
        '                  solutionSpace: "<fix given | causes open>"}]})\n'
        "   Name every child in CamelCase (`ImplF0N`, `TestF0N`, `DebugF0N`).\n"
        "   Record the agent id the task call RETURNS as impl_agent_id: omp\n"
        "   qualifies it under your own id (e.g. `PipelineF0N.ImplF0N`), so the\n"
        "   `name` you passed is not the id.\n",
    ),
    # Warm retry: write to the id the task call returned, then wait for the reply.
    (
        _IMPL_RETRY,
        '     write(path: "agent://<impl_agent_id>",\n'
        '           content: "Your previous attempt returned <BLOCKED|empty|partial>.\n'
        "                     What failed: <summary>.\n"
        '                     Complete only: <remaining items>.")\n'
        "     Then `wait` for its reply.\n",
    ),
    (
        _DEBUG_BLOCK,
        '   task({context: "Finding F0N debug: diagnose only, do not edit.",\n'
        '         tasks: [{agent: "harness-debug", name: "DebugF0N",\n'
        '                  task: "<symptom + changed files + impl_agent_id>",\n'
        '                  solutionSpace: "<cause open>"}]})\n',
    ),
    (
        _TEST_BLOCK,
        '   task({context: "Finding F0N test gate: run only your own test files.",\n'
        '         tasks: [{agent: "harness-test", name: "TestF0N",\n'
        '                  task: "Finding: F0N — <title>\n'
        "                         Changed files: <list from impl output>\n"
        "                         Write tests that fail on pre-fix code and pass now.\n"
        '                         Attach the green test log.",\n'
        '                  solutionSpace: "<tests for a given fix>"}]})\n',
    ),
    ("Record every `task_id` you receive.", "Record every agent id the task call returns."),
    ("via `task_id`", "via a follow-up message to your agent id"),
    ("via task_id resumption", "via a follow-up message to the saved agent id"),
    ("(task_id resumption)", "(follow-up message to the saved agent id)"),
    ("using the saved task_id", "via a follow-up message to its saved agent id"),
    ("Use task_id resumption", "Use a follow-up message to the saved agent id"),
    ("the Task tool", "the task tool"),
    ("`~/.config/opencode/skills/pr-review/scripts/`", "`skill://pr-review/scripts`"),
    ("~/.config/opencode/skills", "skill://"),
]

# Scratchpads, `plan/` and findings files do not exist in omp: working memory
# is the transcript (`history://<agent id>`), prompt files live under
# `local://prompts/`, and results are `yield`ed JSON. Each agent that has a
# "## Scratchpad protocol" section gets this paragraph in its place.
_TRANSCRIPT = (
    "Your transcript is your working memory; the orchestrator audits it via "
    "`history://<your agent id>`. State what you read, what you tried and why in "
    "your messages as you go, so a recovery agent can pick up from there."
)
_YIELD = (
    "Finish by `yield`ing JSON that matches your output schema, with no prose "
    "outside the JSON. The report templates below describe the content to put "
    "in the matching schema fields; do not emit them as prose."
)
WORKING_MEMORY = {
    "harness-impl": _TRANSCRIPT,
    "harness-test": _TRANSCRIPT,
    "harness-debug": _TRANSCRIPT,
    "harness-prompt": _TRANSCRIPT,
    "harness-research": f"{_TRANSCRIPT}\n\n{_YIELD}",
    "harness-review": f"{_TRANSCRIPT}\n\n{_YIELD}",
    "harness-pipeline": (
        f"{_TRANSCRIPT} The audit trail (gate transitions, retry decisions, child "
        "agent ids) goes into your yielded verdict, not a file.\n\n"
        f"{_YIELD}"
    ),
    "harness-recovery": (
        "The parent passes the failed subagent's agent id. **Read its transcript first** "
        "via `history://<failed-agent-id>`; its reasoning, decisions and last actions are "
        "your primary diagnostic input. Your own transcript is your working memory.\n\n"
        f"{_YIELD}"
    ),
}
_SCRATCH_SECTION = re.compile(r"## Scratchpad protocol\n.*?(?=\n## )", re.S)
# Report-template lines that cite a scratchpad (the preceding blank line goes too).
_SCRATCH_LINE = re.compile(r"\n*[ \t]*(?:Failed agent scratchpad|Scratchpad): plan/scratch/[^\n]*\n")

# Per-agent exact rewrites. Each `old` MUST occur in that agent's text (body or
# description); a missing anchor fails the build naming the source.
AGENT_SUBS = {
    "harness-impl": [
        ("The path to a single `plan/prompts/F0N-<slug>.md`.", "The path to a single `local://prompts/F0N-<slug>.md`."),
    ],
    "harness-prompt": [
        ("The output path (`plan/prompts/F0N-<slug>.md`).", "The output path (`local://prompts/F0N-<slug>.md`)."),
        ("Generate the prompt at `plan/prompts/F0N-<slug>.md`", "Generate the prompt at `local://prompts/F0N-<slug>.md`"),
        ("Created prompt: plan/prompts/F01-medasr-on-demand-download.md", "Created prompt: local://prompts/F01-medasr-on-demand-download.md"),
        ("Return a brief summary (do not re-paste the full prompt):", "Return the `local://prompts/F0N-<slug>.md` path you wrote and a brief summary (do not re-paste the full prompt):"),
    ],
    "harness-pipeline": [
        (
            "This is enforced by convention, not by permissions: you technically retain edit tools because denying them at the agent level would risk propagating the deny into your `harness-impl` children. Do not exploit that.",
            "Your tool list has no edit tools, only `write` (for `agent://` messages); `bash` must stay read-only.",
        ),
        (
            "and write **only** inside `plan/` (your scratchpad and report fragments).",
            "and write **only** to `local://`; `write` is for messages to your children via `agent://`.",
        ),
        ("The path to `plan/prompts/F0N-<slug>.md`.", "The path to `local://prompts/F0N-<slug>.md`."),
        (
            "…or a **resume** (you are being warm-retried via `task_id`), which means one\nof:",
            "…or a **re-spawn** after a failed or NEEDS_FIX run: your task text then carries the prior failure or the review items, which means one\nof:",
        ),
        ("continue from\n  your scratchpad.", "continue from\n  the failure described in your task text."),
        (
            "with the\n   impl scratchpad path. Do NOT invoke",
            "with the\n   impl agent id (the orchestrator audits it via `history://<id>`). Do NOT invoke",
        ),
        ("Record it in your scratchpad under `Spillover` and report it upward", "Record it under `spillover` in your yielded verdict and report it upward"),
        ("Your final message must be compact", "Your yielded verdict must be compact"),
        (
            "    - plan/scratch/pipeline-F0N-<uuid>.md\n    - plan/scratch/impl-F0N-<uuid>.md\n",
            "    - impl agent id: <PipelineF0N.ImplF0N>\n",
        ),
        ("  Scratchpads:\n", "  Child agent ids:\n"),
    ],
    "harness-research": [
        (
            "## Allowed writes\n\n- `plan/scratch/<role>-<scope>-<uuid>.md` — your scratchpad\n- `plan/findings/research-<area>.md` — your structured output\n\nNEVER edit code outside `plan/`.",
            "## Allowed writes\n\nNone. You do not write files: your structured output is the JSON you `yield`.",
        ),
        ("- The path to write your findings file to (e.g. `plan/findings/research-<scope>.md`).\n", ""),
        ("write one filled-in copy of the template into your findings file.", "add one entry shaped like the template to your findings."),
        (
            "When done, close your scratchpad with `Status: DONE` and return the findings file path.",
            "When done, `yield` the findings JSON. Do not return a file path.",
        ),
    ],
    "harness-recovery": [
        ("- The failed role and its return text (or the timeout signal).", "- The failed role, its agent id, and its return text (or the timeout signal)."),
        (
            "Save the revised prompt to `plan/prompts/F0N.recovery-N.md` (incrementing N if multiple recovery attempts). Then return a brief report:",
            "Save the revised prompt to `local://prompts/F0N.recovery-N.md` (incrementing N if multiple recovery attempts). Then report these fields in your yielded JSON:",
        ),
        ("plan/prompts/F0N.recovery-N.md\n\n## Failure-budget", "local://prompts/F0N.recovery-N.md\n\n## Failure-budget"),
    ],
}
# Descriptions have their own anchors: they are rewritten as a separate text.
DESCRIPTION_SUBS = {
    "harness-impl": [
        ("(plan/prompts/F0N-*.md)", "(local://prompts/F0N-*.md)"),
        ("Supports warm retry via task_id resumption when", "Supports warm retry via a follow-up message to its agent id when"),
        ("plan/prompts/F01-medasr-on-demand-download.md.", "local://prompts/F01-medasr-on-demand-download.md."),
        ("Your scratchpad shows you completed the refactor", "Your last report says you completed the refactor"),
        ("using the saved task_id to continue", "by messaging its saved agent id to continue"),
        ("Use task_id resumption for a warm retry", "Use a follow-up message to the saved agent id for a warm retry"),
    ],
    "harness-prompt": [("plan/prompts/F0N-<slug>.md. The prompt must", "local://prompts/F0N-<slug>.md. The prompt must")],
    "harness-pipeline": [("from plan/prompts/F01-medasr", "from local://prompts/F01-medasr")],
    # omp only lets harness-pipeline spawn harness-debug (RESTRICTED_SPAWN), so
    # the orchestrator-level example and clause are dropped.
    "harness-debug": [
        (
            "Use when the implementation subagent reports a blocker that needs investigation, or when verification reveals an unexpected behaviour after an impl diff.",
            "Use when the implementation subagent reports a blocker that needs investigation. Only harness-pipeline spawns this agent.",
        ),
        (
            """\n- <example>
  Context: Manual smoke test reveals unexpected behaviour in a feature the harness just fixed.
  user: "After F02's fix, the API returns 500 on large payloads — was fine before."
  assistant: "I'm going to use the harness-debug agent to trace the regression to a root cause."
  <commentary>
  An unexpected regression appeared after a harness fix. Use harness-debug to produce a diagnostic the orchestrator can route to a fresh impl agent or recovery.
  </commentary>
  </example>""",
            "",
        ),
    ],
}
LEFTOVER = re.compile(r".*(?:Task\(|task_id|subagent_type|SendMessage|opencode|todowrite|Agent tool|(?i:scratch)|plan/).*")


def apply_anchored(text: str, subs: list[tuple[str, str]], source: str) -> str:
    for old, new in subs:
        if old not in text:
            raise SystemExit(f"{source}: rewrite anchor missing, update omp/build.py: {old!r}")
        text = text.replace(old, new)
    return text


def rewrite_body(text: str, source: str, agent: str | None = None, subs: dict[str, list[tuple[str, str]]] | None = None) -> str:
    """`agent` names the agents/<agent>.md the text came from (None for generic text)."""
    if agent in WORKING_MEMORY:
        text, count = _SCRATCH_SECTION.subn(lambda _: f"## Working memory\n\n{WORKING_MEMORY[agent]}\n", text)
        if count > 1:
            raise SystemExit(f"{source}: more than one Scratchpad protocol section")
    if agent is not None and subs is not None and agent in subs:
        text = apply_anchored(text, subs[agent], source)
    text = _SCRATCH_LINE.sub("\n", text)
    for old, new in BODY_SUBS:
        text = text.replace(old, new)
    leftovers = LEFTOVER.findall(text)
    if leftovers:
        raise SystemExit(f"{source}: opencode-specific text left after rewrite: {leftovers}")
    return text


def block_scalar(key: str, value: str) -> str:
    lines = value.rstrip("\n").split("\n")
    return f"{key}: |-\n" + "\n".join(f"  {line}" if line else "" for line in lines) + "\n"


def load_roles(repo: Path) -> dict:
    roles = yaml.safe_load((repo / "roles.yaml").read_text())
    declared = set(roles["roles"])
    for agent, role in sorted(roles["agents"].items()):
        if role not in declared:
            raise SystemExit(f"roles.yaml: agent {agent!r} maps to undefined role {role!r}")
    # `presets:` holds only extra presets; an empty YAML value means none.
    roles["presets"] = roles["presets"] or {}
    if "default" in roles["presets"]:
        raise SystemExit("roles.yaml: presets.default is derived from `roles:`; remove it")
    for preset, mapping in sorted(roles["presets"].items()):
        for role in sorted(mapping):
            if role not in declared:
                raise SystemExit(f"roles.yaml: preset {preset!r} uses undeclared role {role!r}")
    clash = sorted(set(EXTRA_ROLES) & declared)
    if clash:
        raise SystemExit(f"roles.yaml: roles {clash} collide with the omp built-in roles the build derives")
    return roles


def check_pins(repo: Path, roles: dict, frontmatters: dict[str, dict]) -> None:
    """Every opencode model pin must have a roles.yaml `agents:` entry."""
    mapped = set(roles["agents"])
    config = json.loads(strip_jsonc((repo / "opencode.jsonc").read_text()))
    for name, fm in sorted(frontmatters.items()):
        if "model" in fm and name not in mapped:
            raise SystemExit(f"agents/{name}.md pins model {fm['model']!r} but roles.yaml `agents:` has no entry for {name!r}")
    for name, cfg in sorted(config["agent"].items()):
        if "model" in cfg and name not in mapped:
            raise SystemExit(f"opencode.jsonc agent.{name}.model is pinned but roles.yaml `agents:` has no entry for {name!r}")


def spawn_list(name: str, task) -> list[str]:
    """Agents `permission.task` lets this agent spawn; [] for a plain deny or no rule."""
    # An absent rule maps to no spawns on purpose. In opencode an absent rule
    # means "allowed", but subagents get an injected blanket task deny there
    # (see agents/harness-pipeline.md), so coder and deep-reasoner cannot spawn
    # in opencode either; omp matches that. Only an explicit allow-list spawns.
    if task is None:
        return []
    if task == "deny":
        return []
    if not isinstance(task, dict) or "*" not in task or task["*"] != "deny":
        raise SystemExit(f"agents/{name}.md: permission.task must be 'deny' or a dict with '*: deny' plus allow entries, got {task!r}")
    allowed = [agent for agent, verdict in task.items() if agent != "*"]
    for agent in allowed:
        if task[agent] != "allow":
            raise SystemExit(f"agents/{name}.md: permission.task.{agent} must be 'allow', got {task[agent]!r}")
    return allowed


def tool_list(name: str, perm: dict) -> list[str] | None:
    """Explicit omp tool list, or None when nothing restricts the agent.

    An explicit `tools:` replaces omp's default toolset, so it is emitted only
    when the source denies something (or OMP_TOOL_DENY does); an unrestricted
    agent omits it and keeps the full default set.
    """
    removed: set[str] = set(OMP_TOOL_DENY.get(name, []))
    for key, verdict in perm.items():
        if key not in PERMISSION_KEYS:
            raise SystemExit(f"agents/{name}.md: unsupported permission key {key!r} (omp build handles {sorted(PERMISSION_KEYS)})")
        if key == "task":
            continue
        if verdict != "deny":
            raise SystemExit(f"agents/{name}.md: permission.{key} must be 'deny', got {verdict!r}")
        removed.update(PERMISSION_TOOLS[key])
    if not removed:
        return None
    return [tool for tool in BASE_TOOLS if tool not in removed]


def load_schema(repo: Path, agent: str, schema: str) -> dict:
    path = repo / "skills" / "create-harness" / "schemas" / f"{schema}.schema.json"
    if not path.is_file():
        raise SystemExit(f"{agent}: output schema file missing: {path.relative_to(repo)}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise SystemExit(f"{agent}: output schema {path.relative_to(repo)} is not valid JSON: {err}")


def parse_agent(src: Path) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", src.read_text(), re.S)
    if not m:
        raise SystemExit(f"{src}: no frontmatter")
    return yaml.safe_load(m.group(1)), m.group(2)


def convert(src: Path, fm: dict, body: str, roles: dict, repo: Path) -> str:
    name = src.stem
    if "permission" not in fm:
        raise SystemExit(f"{src}: frontmatter has no `permission` block")
    perm = fm["permission"]
    tools = tool_list(name, perm)
    spawns = spawn_list(name, perm.get("task"))

    for skill in AUTOLOAD_SKILLS.get(name, []):
        if not (repo / "skills" / skill / "SKILL.md").is_file():
            raise SystemExit(f"{name}: autoloadSkills {skill!r} has no skills/{skill}/SKILL.md")

    header = (
        f"# GENERATED by omp/build.py from agents/{name}.md.\n"
        f"# Edit that file (or roles.yaml), then re-run the script.\n"
        f"name: {name}\n" + block_scalar("description", rewrite_body(fm["description"], f"agents/{name}.md description", name, DESCRIPTION_SUBS))
    )
    if name in roles["agents"]:
        header += f'model: "@{roles["agents"][name]}"\n'
    if spawns:
        header += f"spawns: {', '.join(spawns)}\n"
    if name in BLOCKING:
        header += "blocking: true\n"
    if name in OUTPUT_SCHEMAS:
        schema = load_schema(repo, name, OUTPUT_SCHEMAS[name])
        header += "structured: true\n" + f"output: {json.dumps(schema, sort_keys=False)}\n"
    if name in AUTOLOAD_SKILLS:
        header += f"autoloadSkills: {', '.join(AUTOLOAD_SKILLS[name])}\n"
    if tools is not None:
        header += f"tools: {', '.join(tools)}\n"
    return f"---\n{header}---\n{rewrite_body(body, f'agents/{name}.md body', name, AGENT_SUBS)}"


def render_rules_md(repo: Path) -> str:
    agents_md = (repo / "AGENTS.md").read_text()
    start, end = "# Global engineering principles", "\n# Strength-based model routing"
    if not agents_md.startswith(start) or end not in agents_md:
        raise SystemExit(f"AGENTS.md no longer starts with {start!r} and contains {end.strip()!r}")
    principles = agents_md[: agents_md.index(end)].rstrip("\n")
    header = (
        "<!-- GENERATED by omp/build.py from AGENTS.md (principles).\n"
        "     Edit that file, then re-run. -->\n\n"
    )
    return f"{header}{principles}\n"


def render_agents_md(repo: Path) -> str:
    routing = (repo / "omp" / "routing.md").read_text()
    header = (
        "<!-- GENERATED by omp/build.py from omp/routing.md.\n"
        "     Edit that file, then re-run. -->\n\n"
    )
    return f"{header}{routing}"


def with_extra_roles(mapping: dict) -> dict:
    return {**mapping, **{extra: mapping[source] for extra, source in EXTRA_ROLES.items()}}


def bash_deny_patterns(repo: Path) -> list[dict]:
    """omp `bash.patterns` deny entries from claude/settings.json `permissions.deny`.

    `Bash(cmd *)` becomes the match `cmd*`; `Bash(cmd)` stays exact. Any other
    entry fails the build rather than being dropped, so a new deny rule cannot
    silently go missing in omp.
    """
    settings = json.loads((repo / "claude" / "settings.json").read_text())
    patterns = []
    for entry in settings["permissions"]["deny"]:
        m = re.fullmatch(r"Bash\(([^*()]+?)( \*)?\)", entry)
        if not m:
            raise SystemExit(f"claude/settings.json: deny entry {entry!r} cannot be translated to an omp bash pattern (supported: Bash(cmd) and Bash(cmd *))")
        patterns.append({"match": m.group(1) + ("*" if m.group(2) else ""), "approval": "deny"})
    return patterns


def render_fragment(roles: dict, repo: Path) -> str:
    # `default` is derived from `roles:`; roles.yaml `presets:` holds only extras.
    presets = {"default": roles["roles"], **roles["presets"]}
    fragment = {
        "modelRoles": with_extra_roles(roles["roles"]),
        "modelPresets": {name: {"modelRoles": with_extra_roles(mapping)} for name, mapping in presets.items()},
        # Isolation is a precondition of the pipeline runners (spawned isolated).
        "task": {"maxRecursionDepth": 2, "isolation": {"enabled": True}},
        "bash": {"patterns": bash_deny_patterns(repo)},
    }
    header = (
        "# GENERATED by omp/build.py from roles.yaml.\n"
        "# Merge into ~/.omp/agent/config.yml; edit roles.yaml, then re-run the script.\n"
    )
    return header + yaml.safe_dump(fragment, sort_keys=False)


def render_mcp(repo: Path) -> str:
    config = json.loads(strip_jsonc((repo / "opencode.jsonc").read_text()))
    return json.dumps(_omp_mcp.convert(config["mcp"]), indent=2) + "\n"


def render_policy(repo: Path, parsed: dict) -> str:
    config = json.loads(strip_jsonc((repo / "opencode.jsonc").read_text()))
    spawns = {src.stem: spawn_list(src.stem, fm["permission"].get("task")) for src, (fm, _) in parsed.items()}
    return _omp_policy.render_policy(config, {src.stem: fm for src, (fm, _) in parsed.items()}, spawns, RESTRICTED_SPAWN)


def render_all(repo: Path = REPO) -> dict[Path, str]:
    """Every generated file, keyed by its path. Reads only; deterministic."""
    roles = load_roles(repo)
    parsed = {src: parse_agent(src) for src in sorted((repo / "agents").glob("*.md"))}
    check_pins(repo, roles, {src.stem: fm for src, (fm, _) in parsed.items()})
    omp = repo / "omp"
    outputs = {
        omp / "RULES.md": render_rules_md(repo),
        omp / "AGENTS.md": render_agents_md(repo),
        omp / "config.fragment.yml": render_fragment(roles, repo),
        omp / "mcp.json": render_mcp(repo),
    }
    for src, (fm, body) in parsed.items():
        out = convert(src, fm, body, roles, repo)
        yaml.safe_load(out.split("---\n")[1])  # the frontmatter must parse
        outputs[omp / "agents" / src.name] = out
    # After the agent loop so a malformed agent fails there, naming its source.
    outputs[omp / "extension" / "policy.json"] = render_policy(repo, parsed)
    return outputs


def problems(outputs: dict[Path, str], repo: Path) -> list[str]:
    found = []
    for path, text in outputs.items():
        rel = path.relative_to(repo)
        if not path.exists():
            found.append(f"missing {rel}")
        elif path.read_text() != text:
            found.append(f"stale {rel}")
    agents_dir = repo / "omp" / "agents"
    if agents_dir.is_dir():
        found += [f"orphan {p.relative_to(repo)}" for p in sorted(agents_dir.glob("*.md")) if p not in outputs]
    return found


def main(argv: list[str] | None = None, repo: Path = REPO) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ["--check"]):
        raise SystemExit(f"usage: omp/build.py [--check], got {args}")
    outputs = render_all(repo)
    if args == ["--check"]:
        found = problems(outputs, repo)
        if found:
            print("omp output out of date, run `python3 omp/build.py`:\n  " + "\n  ".join(found))
            return 1
        return 0
    agents_dir = repo / "omp" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for stale in sorted(agents_dir.glob("*.md")):
        if stale not in outputs:
            stale.unlink()
            print(f"removed {stale.name} (no longer in agents/)")
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    agent_count = sum(1 for path in outputs if path.parent == agents_dir)
    print(f"generated omp/RULES.md, omp/AGENTS.md, omp/config.fragment.yml, omp/mcp.json, omp/extension/policy.json and {agent_count} agents in omp/agents/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
