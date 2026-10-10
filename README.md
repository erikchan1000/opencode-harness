# opencode-harness

The source of truth for my [OpenCode](https://opencode.ai) setup: a collection of
**skills**, **agents**, and **config** that are symlinked into `~/.config/opencode/`
by [`install.sh`](install.sh). Edit here, and the changes are live everywhere.

The flagship is the **create-harness** skill — a multi-subagent orchestration
system that turns complex, ambiguous tasks into structured research, parallel
implementation, and verified fixes — but the repo now tracks the whole toolbox.

## What's inside

### Skills (`skills/`)

| Skill | Purpose |
|-------|---------|
| [`create-harness`](skills/create-harness) | Multi-subagent orchestration: research → plan → parallel implement → verify (flagship, see below) |
| [`pr-review`](skills/pr-review) | AI-powered code review via [PR-Agent](https://github.com/qodo-ai/pr-agent), runs locally (BYOK) |
| [`caveman`](skills/caveman) | Ultra-compressed communication mode; cuts token usage ~75% while keeping technical accuracy |
| [`fhir-ehr-mapping-playbook`](skills/fhir-ehr-mapping-playbook) | Canonical-to-FHIR and vendor EHR mapping/sync design & validation |
| [`flutter-taste-skill`](skills/flutter-taste-skill) | Give AI-generated Flutter UI good taste (bento grids, glassmorphism, anti-slop rules) |
| [`hipaa-security-checklist`](skills/hipaa-security-checklist) | Review PHI handling, access controls, and HIPAA-aligned safeguards |
| [`home-health-oasis-playbook`](skills/home-health-oasis-playbook) | OASIS, M1800, and GG charting logic for home-health AI scribe workflows |
| [`mobile-ui-refactor`](skills/mobile-ui-refactor) | Refactor/overhaul mobile UI (Material 3, dark-mode-first, motion, polish) |
| [`quant-strategy-research`](skills/quant-strategy-research) | Quant trading-strategy research methodology (entry/exit signals, anti-overfitting validation) |
| [`skill-creator`](skills/skill-creator) | Guide for authoring and updating effective skills |
| [`skillsmp-discovery`](skills/skillsmp-discovery) | Find, browse, and install community skills from [SkillsMP](https://skillsmp.com) |

### Agents (`agents/`)

The seven `harness-*` agents power the create-harness flagship (detailed in the
table further down). The rest are general-purpose specialists:

| Agent | Purpose |
|-------|---------|
| [`coder`](agents/coder.md) | Implementation specialist — writes/edits/refactors from a clear spec |
| [`deep-reasoner`](agents/deep-reasoner.md) | Hard-reasoning & debugging — root cause, algorithms, concurrency, tradeoffs |
| [`ehr-fhir-sync-architect`](agents/ehr-fhir-sync-architect.md) | Design/implement/review EHR/FHIR integration for home-health charting |
| [`hipaa-privacy-reviewer`](agents/hipaa-privacy-reviewer.md) | Focused HIPAA/privacy/security review of PHI-handling code |
| [`home-health-scribe-architect`](agents/home-health-scribe-architect.md) | Architecture for AI scribe systems in home-health workflows |
| [`scribe-test-engineer`](agents/scribe-test-engineer.md) | Unit/integration tests for AI scribe features with edge-case coverage |

### Config

- [`AGENTS.md`](AGENTS.md) — global engineering principles + strength-based model routing.
- [`opencode.jsonc`](opencode.jsonc) — model routing, MCP servers, and plugins.

## Flagship: the create-harness skill

A **harness** is a team of seven specialized AI subagents that work together through a five-phase loop:

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
├── AGENTS.md               # Engineering principles + model routing (→ config)
├── opencode.jsonc          # Model routing, MCP servers, plugins (→ config)
├── install.sh              # Symlink skills/agents/config into ~/.config/opencode/
├── pyproject.toml          # Dev deps (pytest) for running tests
│
├── skills/                 # All skills — each dir symlinked into ~/.config/opencode/skills/
│   ├── create-harness/     # Flagship orchestration methodology
│   │   ├── SKILL.md
│   │   ├── templates/      # objective / finding / impl-prompt / pipelines / scratchpad
│   │   ├── scripts/build_pipelines.py   # Deterministic DAG builder
│   │   └── examples/       # mobile-bugs.md, api-perf.md
│   ├── pr-review/          # AI code review via PR-Agent
│   │   ├── SKILL.md
│   │   ├── scripts/        # ensure_installed.py, run_review.py, parse_output.py
│   │   └── templates/pr_agent.toml
│   ├── caveman/
│   ├── fhir-ehr-mapping-playbook/
│   ├── flutter-taste-skill/
│   ├── hipaa-security-checklist/
│   ├── home-health-oasis-playbook/
│   ├── mobile-ui-refactor/
│   ├── quant-strategy-research/
│   ├── skill-creator/
│   └── skillsmp-discovery/
│
├── agents/                 # All subagents — each file symlinked into ~/.config/opencode/agents/
│   ├── harness-research.md   harness-prompt.md   harness-impl.md
│   ├── harness-review.md     harness-debug.md    harness-test.md
│   ├── harness-recovery.md
│   ├── coder.md              deep-reasoner.md
│   ├── ehr-fhir-sync-architect.md
│   ├── hipaa-privacy-reviewer.md
│   ├── home-health-scribe-architect.md
│   └── scribe-test-engineer.md
│
└── tests/                  # pytest suite for the pr-review scripts
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

This symlinks **everything** into `~/.config/opencode/`, so the repo stays the
single source of truth and edits go live immediately:

- every dir in `skills/` → `~/.config/opencode/skills/<name>`
- every file in `agents/` → `~/.config/opencode/agents/<name>.md`
- `AGENTS.md` and `opencode.jsonc` → `~/.config/opencode/`

The script is idempotent (re-run after pulling updates). If a target already
exists as a real file/dir, it is backed up to `<target>.bak-<timestamp>` before
the symlink is created; existing symlinks are replaced in place.

### Verify

After installing, all skills appear in OpenCode's available skills list, and the
`harness-*` and specialist agent types become available to the Task tool.

### Claude Code

```bash
./install.sh --claude
```

The same repo also drives [Claude Code](https://claude.com/claude-code).
opencode's files stay the source of truth, and `claude/` holds only what
Claude Code needs on top of them:

| Path | What it is |
|------|------------|
| `claude/build.py` | Generates the two files below from the opencode sources. `tests/test_claude_build.py` fails when they are out of date. |
| `claude/agents/*.md` | **Generated** from `agents/*.md`: frontmatter mapped (`permission` → `disallowedTools`, pins from frontmatter or `opencode.jsonc`), `Task`/`task_id` → `Agent`/`SendMessage`. |
| `claude/CLAUDE.md` | **Generated**: the principles section of `AGENTS.md` + `claude/routing.md` (the roster in Claude Code names). |
| `claude/routing.md` | Hand-written model routing for Claude Code. |
| `claude/settings.json` | Merged into `~/.claude/settings.json`: denies `codegraph init/index/uninit`, sets subagent depth 2. |
| `claude/mcp.sh` | Registers every MCP server from `opencode.jsonc` (user scope) and ai-scribe's personal `opencode.json` (local scope). Skips servers that exist. No secrets in config. |
| `claude/install.sh` | Runs all of the above; links `skills/*`, any opencode-only skill, the agents and `CLAUDE.md` into `~/.claude/`. |

After editing an agent, a pin, `AGENTS.md` or `claude/routing.md`, re-run
`./install.sh --claude` (or just `python3 claude/build.py`). Then run `/mcp`
in Claude Code to sign in to the OAuth servers.

Claude Code differences from the opencode setup:

- **Per-agent MCP scoping is generated** from the `opencode.jsonc` allowlists into each agent's `disallowedTools`. Claude Code defers MCP tool schemas until a
  tool is used, so the scoping now limits which (often write-capable) servers
  an agent may call rather than saving tokens.
- **`harness-pipeline`'s spawn allowlist is prompt-enforced.** Claude Code
  ignores `Agent(type)` restrictions inside subagents. Leaf roles still cannot
  spawn (`disallowedTools: Agent`), so depth stays at 2. The `create-harness`
  skill's "Running under Claude Code" section has the full mapping.
- **Not ported:** the `mask-home` plugin (Claude Code has no hook that
  rewrites the system prompt or built-in tool output) and
  `opencode-claude-auth` (not needed).
- **Supermemory (ai-scribe only)** lives outside this repo, like the opencode
  side: the `claude()` function in `~/.zshrc` loads a pinned copy of
  `supermemoryai/claude-supermemory` from `~/.claude/vendor/claude-supermemory`
  with `--plugin-dir`, only in ai-scribe checkouts and worktrees, using the
  Keychain key and the shared `ai-scribe` container that opencode-supermemory
  also writes to.

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
| `PR_AGENT_MODEL` | No | `anthropic/claude-opus-5-5` | LLM model |
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
python skills/create-harness/scripts/build_pipelines.py \
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
