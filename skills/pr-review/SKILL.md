---
name: pr-review
description: >-
  AI-powered code review using PR-Agent CLI. Runs locally with your own
  LLM API key (BYOK). Use when user says "review this PR", "review my
  changes", "code review", "/pr-review", or when a harness needs a
  review gate after implementation. Supports review of local branch
  diffs and remote PR URLs. Configurable LLM provider via PR_AGENT_MODEL
  env var.
---

# PR Review

Run AI-powered code review using [PR-Agent](https://github.com/The-PR-Agent/pr-agent)
locally. PR-Agent analyzes diffs with LLM-powered review, catching
security issues, bugs, performance problems, and style violations.

## When to use

- User asks to review a PR, diff, or set of changes
- Harness orchestrator needs a review gate after `harness-impl`
- Pre-push code quality check on a feature branch
- Security/compliance audit of a changeset

## Prerequisites

- Python 3.10+
- An LLM API key in your environment (see Configuration below)
- `git` CLI available
- `gh` CLI (optional, for PR URL auto-detection)

## Workflow

### Step 1: Ensure PR-Agent is installed

```bash
python "${CLAUDE_SKILL_DIR}/scripts/ensure_installed.py"
```

If PR-Agent is not installed, this creates an isolated venv at
`~/.local/share/opencode-harness/pr-agent-venv/` and installs
`pr-agent==0.35.0`. The venv is reused across sessions.

If install fails, check that Python 3.10+ is available and that pip
can reach PyPI.

### Step 2: Run the review

**Review local branch diff (most common):**
```bash
python "${CLAUDE_SKILL_DIR}/scripts/run_review.py" \
  --local \
  --command review
```

**Review a specific PR by URL:**
```bash
python "${CLAUDE_SKILL_DIR}/scripts/run_review.py" \
  --pr-url https://github.com/owner/repo/pull/123 \
  --command review
```

**With domain-specific focus:**
```bash
python "${CLAUDE_SKILL_DIR}/scripts/run_review.py" \
  --local \
  --command review \
  --extra-instructions "Focus on HIPAA compliance, PHI exposure, and audit logging"
```

**Available commands:** `review`, `improve`, `describe`, `ask`

### Step 3: Parse and present results

Pipe the output through the parser for structured formatting:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/run_review.py" --local --command review \
  | python "${CLAUDE_SKILL_DIR}/scripts/parse_output.py" --format caveman
```

**Output formats:**
- `--format markdown` (default): Clean table with severity, file, line, problem, fix
- `--format caveman`: One line per finding: `file:L42: bug: problem. fix.`
- `--format json`: Machine-readable `{"score": N, "findings": [...]}`

### Step 4: Present findings to the user

Summarize the review results. For each finding, include:
- File and line number
- Severity (critical / high / medium / low)
- Problem description
- Suggested fix

If invoked as a harness review gate, output the structured verdict
format that `harness-review.md` expects (PASS / NEEDS_FIX / BLOCKED).

## Configuration

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PR_AGENT_MODEL` | No | `anthropic/claude-opus-5-5` | LLM model for reviews. Must be in pr-agent's MAX_TOKENS registry *or* paired with `PR_AGENT_MODEL_MAX_TOKENS`; the runner validates up front and lists registered options on mismatch |
| `PR_AGENT_MODEL_MAX_TOKENS` | Only for unregistered models | `1000000` (default model only) | Input-window size passed as `config.custom_model_max_tokens`. pr-agent 0.35.0 predates opus 5.5, so its registry has no entry — the runner supplies one |
| `PR_AGENT_TEMPERATURE` | No | `1` | Sampling temperature. Newer Anthropic models REJECT pr-agent's built-in 0.2 with "temperature is deprecated for this model" |
| `OPENAI_KEY` | If using OpenAI | - | OpenAI API key |
| `ANTHROPIC_KEY` | If using Claude | - | Anthropic API key |
| `GROQ_API_KEY` | If using Groq | - | Groq API key |
| `DEEPSEEK_KEY` | If using DeepSeek | - | DeepSeek API key |
| `PR_AGENT_VERSION` | No | `0.35.0` | PR-Agent version to install |

### Per-repo configuration

Place a `.pr_agent.toml` in the repo root to customize review behavior:

```toml
[pr_reviewer]
extra_instructions = "This is a healthcare app. Flag any PHI logging."
num_max_findings = 5
require_security_review = true
```

See `templates/pr_agent.toml` in this skill directory for all available
options.

### Supported LLM providers

PR-Agent uses LiteLLM, supporting: OpenAI, Anthropic Claude, Google
Gemini, Ollama (local), Groq, DeepSeek, Mistral, Amazon Bedrock,
Azure OpenAI, and more. Set `PR_AGENT_MODEL` to the LiteLLM model
string (e.g., `ollama/qwen2.5-coder:32b` for local inference).

## Operational notes (learned 2026-08-29, PR #422)

- **Large PRs:** GitHub's API refuses diffs beyond ~300 files / ~20k lines
  (HTTP 406; pr-agent logs "PR has no files" and exits 0). The runner
  detects this on `--pr-url` runs and auto-falls back to `--local` against
  the PR's base branch when the checkout is on the PR's head branch. For
  harness runs, prefer reviewing per wave instead of one mega-PR.
- **`--local` mechanics:** pr-agent's LocalGitProvider needs a `.git`
  DIRECTORY (git worktrees have a `.git` file), a clean tree, and a LOCAL
  base branch. The runner satisfies all three by reviewing a throwaway
  `git clone --local` of the repo (hardlinked, cheap, auto-deleted).
  Consequence: uncommitted changes are NOT reviewed (the runner warns).
- **Provider selection:** `git_provider` must be set via the
  `CONFIG__GIT_PROVIDER` env var, never `--config.git_provider` — pr-agent
  picks the provider before CLI config args apply.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Review completed successfully |
| 1 | PR-Agent error (check stderr) |
| 2 | Configuration error (missing API key, bad arguments) |
| 3 | No diff found (nothing to review) |

## Boundaries

- **Does not auto-fix code.** Reports findings only. Use `harness-impl`
  or manual editing to address findings.
- **Does not post to GitHub/GitLab.** All output goes to stdout. The
  `publish_output = false` setting is always enforced.
- **Does not approve or reject PRs.** Produces findings for human or
  agent review, not merge decisions.
- **Does not run tests or linters.** Use `harness-test` or your CI
  pipeline for that.

## Harness integration

When used as part of the multi-agent harness, this skill powers the
`harness-review` subagent. The pipeline becomes:

```
prompt -> impl -> review -> test
```

The review agent runs after impl and produces a verdict:
- `PASS`: proceed to test
- `NEEDS_FIX`: route findings back to impl
- `BLOCKED`: escalate to the orchestrator

See `agents/harness-review.md` for the subagent definition.
