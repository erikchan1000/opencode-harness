# opencode-harness

A multi-subagent orchestration system for [OpenCode](https://opencode.ai) that turns complex, ambiguous tasks into structured research, parallel implementation, and verified fixes.

## What it does

A **harness** is a team of six specialized AI subagents that work together through a five-phase loop:

1. **Scope** -- define the objective, boundaries, and done criteria
2. **Research** -- parallel codebase exploration producing structured findings
3. **Plan** -- deterministic DAG builder groups findings into dependency-aware waves
4. **Execute** -- parallel implementation with JIT prompt generation and two-tier failure recovery
5. **Wrap** -- aggregate results into a report

The system handles the hard parts of multi-agent orchestration: context isolation between agents, file-conflict detection, dependency ordering, warm/cold retry on failures, and persistent scratchpads for audit trails.

## Architecture

```
                    ┌──────────────┐
                    │  Orchestrator │  (parent agent running the skill)
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
    │  Research  │   │  Research  │   │  Research  │   Phase 1 (parallel)
    │  (area A)  │   │  (area B)  │   │  (area C)  │
    └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
          └────────────────┼────────────────┘
                           │
                    ┌──────▼───────┐
                    │ DAG Builder   │  Phase 2 (deterministic)
                    │ (Python)      │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │  Wave 1    │  Wave 2    │  ...
              │            │            │
         ┌────┼────┐  ┌───┼───┐        │
         │    │    │  │   │   │        │
        F01  F02  F03 F04 F05          │  Phase 3 (wave-parallel)
         │    │    │  │   │   │        │
    Each finding pipeline:             │
    prompt → impl → debug? → test      │
              │                        │
              └────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │    Report     │  Phase 4
                    └──────────────┘
```

### The seven roles

| Role | Agent | Edits code? | Purpose |
|------|-------|-------------|---------|
| **Research** | `harness-research` | No | Explore codebase, produce structured findings with file:line refs |
| **Prompt author** | `harness-prompt` | No | Write self-contained implementation prompts per finding |
| **Implementation** | `harness-impl` | Yes | Execute one prompt, produce one focused diff |
| **Review** | `harness-review` | No | Run PR-Agent to review impl diff before tests |
| **Debug** | `harness-debug` | No | Root-cause analysis when impl fails or regresses |
| **Unit test** | `harness-test` | Yes | Write + run tests as quality gate before marking done |
| **Recovery** | `harness-recovery` | No | Rewrite failed prompts with narrower scope for cold retry |

### Key design decisions

- **JIT prompt generation**: Wave 2 prompts are written *after* Wave 1 completes, so they incorporate actual changes rather than stale hypotheses.
- **Two-tier failure recovery**: warm retry (resume via `task_id`) preserves context; cold retry (recovery agent) rewrites the prompt with narrower scope.
- **Deterministic DAG builder**: a Python script (not an LLM) computes wave ordering from dependency and file-overlap metadata. No hallucinated schedules.
- **Scratchpad protocol**: every subagent writes to a UUID-keyed file as it works, creating an audit trail for recovery and wrap-up.

## Repository structure

```
opencode-harness/
├── README.md
├── LICENSE
├── install.sh              # Symlink into ~/.config/opencode/
├── pyproject.toml          # Dev deps (pytest) for running tests
│
├── skill/                  # create-harness skill (orchestration methodology)
│   ├── SKILL.md            # Master orchestration methodology (388 lines)
│   ├── templates/
│   │   ├── objective.md    # Phase 0 — scope definition
│   │   ├── finding.md      # Phase 1 — per-issue research output
│   │   ├── impl-prompt.md  # Phase 3a — per-finding implementation prompt
│   │   ├── pipelines.md    # Phase 2 — wave plan format reference
│   │   └── scratchpad.md   # Every subagent's working-memory file
│   ├── scripts/
│   │   └── build_pipelines.py  # Deterministic DAG builder (~490 lines)
│   └── examples/
│       ├── mobile-bugs.md  # Worked example: Flutter recording pipeline
│       └── api-perf.md     # Worked example: REST backend latency
│
├── pr-review/              # pr-review skill (AI code review via PR-Agent)
│   ├── SKILL.md            # Skill definition + trigger patterns
│   ├── scripts/
│   │   ├── ensure_installed.py  # Check/install pr-agent in isolated venv
│   │   ├── run_review.py        # Invoke pr-agent CLI, capture output
│   │   └── parse_output.py      # Parse markdown output → structured findings
│   └── templates/
│       └── pr_agent.toml        # Default review config template
│
├── agents/                 # Subagent definitions (installed individually)
│   ├── harness-research.md
│   ├── harness-prompt.md
│   ├── harness-impl.md
│   ├── harness-review.md   # Code review gate (between impl and test)
│   ├── harness-debug.md
│   ├── harness-test.md
│   └── harness-recovery.md
│
└── tests/                  # pytest test suite
    ├── conftest.py
    ├── test_ensure_installed.py
    ├── test_run_review.py
    ├── test_parse_output.py
    └── fixtures/
        ├── sample_review_output.md
        └── sample_diff.patch
```

## Installation

### Quick install (symlinks)

```bash
./install.sh
```

This creates symlinks from your OpenCode config to the repo, so updates are picked up automatically.

### Manual install (copy)

```bash
# Install the skills
cp -r skill/ ~/.config/opencode/skills/create-harness/
cp -r pr-review/ ~/.config/opencode/skills/pr-review/

# Install the agent definitions
cp agents/harness-*.md ~/.config/opencode/agent/
```

### Verify

After installing, both skills appear in OpenCode's available skills list, and the seven `harness-*` agent types become available to the Task tool.

## Usage

The harness activates automatically when you ask OpenCode to do something that matches the skill's trigger patterns:

- "Find bugs in the recording feature and fix them"
- "Audit the API routes for performance issues, then implement fixes"
- "Decompose this refactor into parallel tasks"

Or invoke it explicitly:

```
/skill create-harness
```

The orchestrator (parent agent) then runs the five-phase loop, spawning subagents via the Task tool as needed.

### Minimal example

```
You: "Find and fix correctness bugs in src/auth/"

OpenCode (orchestrator):
  Phase 0 → writes plan/objective.md
  Phase 1 → spawns 2 research agents scoped to src/auth/
  Phase 2 → runs build_pipelines.py → plan/pipelines.md
  Phase 3 → Wave 1: generates prompts, runs impl+test pipelines in parallel
          → Wave 2: JIT prompts with Wave 1 context, runs remaining pipelines
  Phase 4 → writes plan/report.md, surfaces summary
```

### PR Review skill

The `pr-review` skill provides AI-powered code review using
[PR-Agent](https://github.com/The-PR-Agent/pr-agent). It runs locally
with your own LLM API key (BYOK).

```
You: "/pr-review" or "review my changes"

OpenCode:
  1. Ensures PR-Agent is installed (isolated venv)
  2. Runs pr-agent review against local diff
  3. Parses output into structured findings
  4. Presents results with severity, file, line, problem, fix
```

#### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PR_AGENT_MODEL` | No | `anthropic/claude-sonnet-4-20250514` | LLM model |
| `OPENAI_KEY` | If using OpenAI | - | OpenAI API key |
| `ANTHROPIC_KEY` | If using Claude | - | Anthropic API key |

#### Harness integration

When the `harness-review` agent is available, the finding pipeline
becomes:

```
prompt → impl → review → test
```

The review agent produces a verdict: `PASS` (proceed to test),
`NEEDS_FIX` (route back to impl), or `BLOCKED` (escalate).

### The DAG builder

The `build_pipelines.py` script is the deterministic planner:

```bash
python skill/scripts/build_pipelines.py \
  --findings plan/findings.md \
  --output   plan/pipelines.md \
  --title    "Auth module bugs"
```

It reads the findings table, builds a dependency graph from `Depends on` and `Touches files` metadata, detects cycles, and topologically sorts into waves. Exit codes: 0 = success, 1 = validation error, 2 = parse error.

## Runtime artifacts

When a harness runs, it creates a `plan/` directory in the target repo:

```
plan/
├── objective.md            # Phase 0 scope
├── findings.md             # Phase 1 aggregated findings table
├── pipelines.md            # Phase 2 wave plan
├── prompts/                # Phase 3a per-finding implementation prompts
│   ├── F01-auth-bypass.md
│   ├── F02-token-leak.md
│   └── F02.recovery-1.md  # Recovery prompt (if cold retry was needed)
├── scratch/                # Subagent working memory (gitignore recommended)
│   ├── research-auth-<uuid>.md
│   ├── impl-F01-<uuid>.md
│   └── test-F01-<uuid>.md
└── report.md               # Phase 4 summary
```

Recommended `.gitignore` addition:

```
plan/scratch/
```

## Requirements

- [OpenCode](https://opencode.ai) with Task tool support
- Python 3.10+ (for `build_pipelines.py` and pr-review scripts)
- An LLM API key (for pr-review skill: `OPENAI_KEY`, `ANTHROPIC_KEY`, etc.)
- `git` CLI (for pr-review local diff mode)
- `gh` CLI (optional, for PR URL auto-detection)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## License

MIT
