---
name: create-harness
description: >-
  This skill should be used when building a multi-subagent harness for
  complex, multi-step tasks. It defines a six-role roster (research,
  prompt-author, implementation, debug, unit-test, recovery) and a
  five-phase orchestration loop with dependency-aware parallel execution,
  just-in-time prompt generation, and two-tier failure recovery. Use when
  the task decomposes into research, fix, and verify steps, when failures
  are recoverable, or when the user mentions building a harness,
  orchestrating subagents, decomposing a large feature into parallel
  research + implementation + verification, or asks to "find bugs /
  improvement areas and fix them" across a codebase.
---

# Create Harness

A **harness** is a structured team of subagents that work together to
take a complex, ambiguous task from "we want to improve X" to a list of
concrete findings to a pile of executed fixes that compile, run, and
have tests behind them.

This skill provides a methodology and file templates to build one. The
harness comprises OpenCode subagent definitions (in
`~/.config/opencode/agents/harness-*.md`) plus an orchestration loop the
parent agent runs using the Task tool.

## When to use this skill

Use a harness when **all** of these are true:

- The task is too big for one chat to hold in context end-to-end.
- The task naturally decomposes into research, fix, and verify.
- Failures during execution are recoverable (i.e. retryable with better
  instructions, not just escalate to the human).

Do not bother with a harness for:

- Single-file edits.
- Tasks where the fix is already known.
- One-shot questions that just need exploration.

## The standard roster

A complete harness has eight roles. Cut the ones not needed; never add a
ninth without a strong reason — diluting roles is how harnesses go bad.

| Role | `subagent_type` | Tool restrictions | Output |
|------|-----------------|-------------------|--------|
| **Research** | `harness-research` | `edit: false` | Structured findings file with file:line refs |
| **Prompt author** | `harness-prompt` | — | One tailored implementation-prompt `.md` per finding |
| **Pipeline runner** | `harness-pipeline` | scoped `task` (see below) | One compact per-finding verdict |
| **Implementation** | `harness-impl` | — | A diff that compiles + one-line completion log |
| **Debug** | `harness-debug` | `edit: false` | Root-cause note + recommended patch (no edits) |
| **Review** | `harness-review` | `edit: false` | PR-Agent findings + PASS/NEEDS_FIX/BLOCKED verdict |
| **Unit test** | `harness-test` | — | New / amended tests + green test-run log |
| **Recovery** | `harness-recovery` | `edit: false` | A revised prompt for whichever role failed |

Every harness agent has `todowrite: false` (parent owns the task list).
All of them also have `task: false` **except `harness-pipeline`**, which is
the single role permitted to fan out — and only to the four leaf roles it
coordinates:

```yaml
permission:
  task:
    "*": deny            # wildcard first — last matching rule wins
    harness-impl: allow
    harness-review: allow
    harness-test: allow
    harness-debug: allow
```

This requires `"subagent_depth": 2` in `opencode.json(c)`; the default of
`1` blocks all nesting. Depth accounting is orchestrator=0, runner=1,
leaf=2. Because the leaf roles keep `task: false`, depth 2 is
self-limiting — nothing can reach a third level even by mistake.

Two mechanisms must both be satisfied for nesting to work, and they are
independent: `subagent_depth` gates nesting *depth*, while an injected
blanket `task: "*": deny` gates each subagent's *ability* to spawn at all.
Declaring any `task` rule on an agent suppresses that injected deny.
Raising `subagent_depth` alone is a no-op.

### Why the runner exists

The orchestrator's context window — not concurrency — is the scaling limit
of a harness. OpenCode imposes no cap on parallel subagents, so a wave can
be as wide as the DAG allows. What it cannot do is stop the parent from
absorbing four gate transcripts per finding per wave.

The pipeline runner collapses that to one verdict per finding, and keeps
each finding's warm-retry loop local, where the failure context is already
in-window instead of reconstructed across orchestrator turns.

`harness-pipeline` deliberately does **not** set `edit: deny`, even though
it must never write code. Session-level deny rules are inherited by child
sessions (`deriveSubagentSessionPermission`), so an agent-level edit deny
on the runner risks propagating into its `harness-impl` children and
silently breaking every implementation. The "coordinate, never implement"
rule is therefore enforced in the runner's prompt instead.

### Model assignments

The roles run on a deliberate two-tier model split, set via `model:`
(and `variant:`) in each agent's frontmatter:

| Role(s) | Model | Rationale |
|---------|-------|-----------|
| Test (`harness-test`) | `anthropic/claude-opus-5-5` | Code-writing role: strongest implementation model |
| Implementation (`harness-impl`) | `anthropic/claude-sonnet-5-5` | 2026-09-23: temporarily back from opus-5-5 — every impl invocation on that pin was rejected by the provider content filter pre-output (8/8 findings, docs-only included) while test/research on the same pin ran clean. Revert when a probe succeeds; see the comment in `agents/harness-impl.md`. |
| Review (`harness-review`), Debug (`harness-debug`), Recovery (`harness-recovery`) | `anthropic/claude-opus-5-5` | Judgment roles: security/correctness review, root-cause analysis, and diagnosing *why an agent failed* — the three hardest reasoning jobs in the loop |
| Research (`harness-research`) | `anthropic/claude-opus-5-5` | Findings quality gates every downstream phase (2026-08-22: upgraded from sonnet-4-6 per user preference) |
| Prompt (`harness-prompt`), Pipeline (`harness-pipeline`) | `anthropic/claude-sonnet-5-5` | Structured-output roles: templating a finding into a prompt, and sequencing gates from explicit PASS/NEEDS_FIX verdicts. Neither needs frontier reasoning; both are high-volume, so this is where the cost lives |
| Orchestration (parent agent) | Run the parent session on `anthropic/claude-opus-5-5` | The orchestrator makes the retry/defer/escalate decisions; use the strongest model |

Research is the one to resist downgrading. It is tempting to put it on Haiku
alongside the built-in `explore` agent, but research does more than search —
it assigns severity and declares `depends_on` / `touches_files`, which is the
input the DAG builder schedules from. Bad findings poison every downstream
phase: a missed bug is never fixed, and a wrong `touches_files` silently
schedules two conflicting diffs into the same wave. Sonnet is the floor and
Opus is the current setting.

Note that research is also high-volume — three-to-five parallel subagents per
harness run, each reading a lot of code. It is the most expensive Opus slot in
the roster. If cost becomes the binding constraint, this is the first place to
look, but downgrade it deliberately rather than by drift.

When updating model assignments, edit the frontmatter of the
corresponding `~/.config/opencode/agents/harness-*.md` files and keep
this table in sync. Two pins live outside the harness agents and move with
the Opus rows: the orchestration row mirrors the `build` pin in the global
`opencode.jsonc`, and PR-Agent (which `harness-review` drives) reviews
with the pr-review skill's `DEFAULT_MODEL` in `scripts/run_review.py`.
2026-09-22: every Opus pin moved from `claude-opus-5` to `claude-opus-5-5`.
2026-10-08: every Sonnet pin moved from `claude-sonnet-5` to `claude-sonnet-5-5`.

The **recovery** role is the one most teams skip. It is what turns "the
implementation agent timed out" from a dead end into "feed the truncated
stderr back in with a smaller scope and try again."

## Invoking subagents

Use the Task tool to spawn each harness agent:

```
Task(subagent_type: "harness-research",
     prompt: "<scope + focus + paths to templates + output path>")
```

The Task tool returns a `task_id` that can be used to **resume** the
same agent session later — this enables warm retries (see Phase 3).

### Running under Claude Code

This skill and its agents are written in opencode terms. Under Claude Code
(agents installed at `~/.claude/agents/harness-*.md` by
`~/opencode-harness/install.sh --claude`), translate as follows; everything
else — phases, roles, templates, the DAG builder, the review and test gates
— is unchanged.

| opencode | Claude Code |
|----------|-------------|
| `Task(subagent_type: "X", prompt: …)` | Agent tool, `subagent_type: "X"`, same prompt. Several calls in one message run in parallel (up to 20 at once). |
| Warm retry: `Task(…, task_id: <id>, prompt: …)` | `SendMessage` with `to: <agent ID>` (the ID the Agent call returned) and the retry instructions as `message`. Record the agent ID wherever this skill says to save a `task_id`. |
| `"subagent_depth": 2` in `opencode.jsonc` | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2` in `~/.claude/settings.json` `env`. |
| `harness-pipeline`'s `task` allowlist (impl/test/debug only) | **Not enforced**: Claude Code ignores an `Agent(type)` allowlist inside a subagent. The runner's prompt carries the rule, and every leaf role has `Agent` in `disallowedTools`, so nothing nests past depth 2. |
| `task: deny`, `edit: deny`, `todowrite: deny` | `disallowedTools: Agent` / `Edit, Write, NotebookEdit` / `TodoWrite` |
| `question: deny` | Nothing to set: Claude Code never gives subagents `AskUserQuestion`. |
| "no concurrency cap" | Claude Code caps concurrent subagents at 20 (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`); a wider wave queues. |
| `general` subagent (review fallback) | `general-purpose` |
| Task calls block until the child returns | Agent spawns may run **in the background**. Interactively, a runner still waits for its background children before it finishes. **Headless (`claude -p`, Agent SDK) it does not**: the runner returns its interim text as its verdict, and its children report to the main conversation instead (observed 2026-10-08). For a headless harness run, launch with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, which makes every spawn foreground (verified: orchestrator → `harness-pipeline` → leaf returned inline). It also disables background Bash, so set it for that process only, not in settings. |
| Per-agent MCP allowlists in `opencode.jsonc` | Generated into each agent's `disallowedTools` as `mcp__<server>` (verified 2026-10-08: `harness-pipeline` saw only paper; `harness-debug` only codegraph, brave-search, chrome-devtools, dart, playwright). |

Precondition 1 under Claude Code is instead:

```bash
grep -o '"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": *"[0-9]*"' ~/.claude/settings.json
```

Expect `2`. Unset means Claude Code's default depth (3), which works but
removes the backstop described above. `1` blocks the runners from spawning.

Model pins: `~/.claude/agents/*.md` are generated from
`~/opencode-harness/agents/*.md` by `claude/build.py`, so change a pin in
the opencode agent file (and the table below), then re-run
`./install.sh --claude`.

## Methodology — five-phase loop

Copy this checklist into the task list at the start. Tick items as
work progresses. Each phase ends with a concrete artifact on disk.

```
Harness phases:
- [ ] Phase 0 — Scope. Write objective.md.
- [ ] Phase 1 — Research. Spawn N research subagents in parallel.
        Aggregate into findings.md (with depends_on + touches_files).
- [ ] Phase 2 — Plan. Run build_pipelines.py to produce pipelines.md
        from the findings metadata.
- [ ] Phase 3 — Execute. For each wave (in order):
        (a) Generate prompts for this wave's findings (parallel).
        (b) Open the wave's review channel (push branch + draft PR),
            or record REVIEW_MODE=fallback if unavailable.
        (c) Spawn ONE harness-pipeline runner per finding, IN PARALLEL.
            Each runner owns impl → review → test + warm retries and
            returns a single verdict.
        (d) Cold retry (recovery agent + fresh runner) for any finding
            a runner reports BLOCKED.
        Wait for the whole wave to complete before the next wave.
- [ ] Phase 4 — Wrap. Aggregate completion logs into report.md.
        Record decisions per the repo's AGENTS.md (shared memory first;
        ADR/CHANGELOG only where the repo requires them).
```

### Phase 0 — Scope

Decide and write down:

1. **Objective**: one sentence.
2. **Out of scope**: bullet list of temptations to resist.
3. **Definition of done**: the user-visible checklist (tests passing,
   lints clean, manual smoke).
4. **Failure budget**: how many recovery loops per finding before
   escalating to the human (default: 2 — one warm retry, one cold).

Write this to `plan/objective.md` using the template at
`${CLAUDE_SKILL_DIR}/templates/objective.md`. The `plan/` directory
lives at the repo root, gitignored unless the team wants it tracked.

#### Preconditions — check these before Phase 1

Verify the harness can actually run end-to-end. Each of these fails at an
awkward moment (mid-wave, after work is in flight) if discovered late:

```bash
# 1. Nesting is enabled — required for harness-pipeline to fan out.
#    Expect: 2 (or higher). If 1/absent, pipeline runners cannot spawn.
grep -o '"subagent_depth"[[:space:]]*:[[:space:]]*[0-9]*' \
  ~/.config/opencode/opencode.jsonc

# 2. Review gate reachable — PR-Agent needs a REAL GitHub PR.
gh auth status                  # authenticated?
git remote get-url origin       # pushable remote exists?
echo "${PR_AGENT_MODEL:?unset}" # LLM key/model configured?

# 3. Test runner exists (adapt to the repo).
ls package.json pyproject.toml pubspec.yaml 2>/dev/null
```

Record the outcome in `objective.md`. If check 2 fails, set
`REVIEW_MODE=fallback` in the objective now and tell the user the review
gate will be a `general`-subagent manual review rather than PR-Agent —
do not discover this at wave 1.

### Phase 1 — Research (parallel)

Spawn research subagents in parallel covering **non-overlapping** slices
of the codebase. Three is usually right; more than five wastes tokens on
overlap.

Each subagent is invoked via:

```
Task(subagent_type: "harness-research",
     prompt: "Scope: <directory>
              Focus: <what to look for>
              Finding template: ${CLAUDE_SKILL_DIR}/templates/finding.md
              Output path: plan/findings/research-<scope>.md
              Scratchpad dir: plan/scratch/")
```

Findings must be sorted by severity, structured per the template, and
genuinely concise per finding — but **do not drop legitimate findings to
hit a line target**. If the area really has 12 issues, raise all 12.

Each finding **must** declare:

- `Depends on`: other finding IDs that must land first. Empty for most.
- `Touches files`: paths the implementation diff is expected to edit.
  Used by the planner to detect file-conflict collisions.

Aggregate outputs into a single `plan/findings.md` table:

```markdown
| ID  | Severity | Area      | Title                      | File:Line                   | Depends on | Touches files                               |
|-----|----------|-----------|----------------------------|-----------------------------|------------|---------------------------------------------|
| F01 | high     | recording | MedASR not downloaded      | recording_provider.dart:295 | —          | recording_provider.dart, record_screen.dart |
| F02 | medium   | network   | Bearer token logged at INFO| api_client.dart:88          | —          | api_client.dart                             |
```

### Phase 2 — Plan (deterministic)

Run the DAG builder script to produce `plan/pipelines.md`:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/build_pipelines.py" \
  --findings plan/findings.md \
  --output   plan/pipelines.md
```

The script:

- Parses the findings table for `Depends on` and `Touches files`.
- Adds dependency edges for both explicit dependencies AND file-conflict
  overlaps.
- Detects cycles (surfaces as errors — research output bug).
- Topologically sorts into waves with tie-breaks: higher severity first,
  more dependents first, smaller scope first.
- Writes `pipelines.md` in the expected format (see template).
- Exits non-zero on validation failures (shared files within a wave,
  missing findings, cycles).

If the script surfaces errors, resolve them before proceeding:

- **Cycle detected**: re-examine the findings — one of the `Depends on`
  declarations is wrong, or two findings should be merged.
- **Shared files in same wave**: the script should have pushed one to a
  later wave — if it didn't, it's a bug in the script.

### Phase 3 — Execute (per wave, JIT prompts + parallel pipelines)

Process waves IN ORDER. For each wave:

The orchestrator spawns exactly two kinds of thing per wave: prompt
authors, then pipeline runners. It never invokes `harness-impl`,
`harness-test`, or `harness-debug` directly — those are the runner's
children.

```
For each wave:
  Step 3a — Prompt (parallel, orchestrator-spawned):
    For each F0N in this wave (PARALLEL):
      - Invoke Task(subagent_type: "harness-prompt",
                    prompt: "<finding details from findings.md>
                             Template: ${CLAUDE_SKILL_DIR}/templates/impl-prompt.md
                             Output: plan/prompts/F0N-<slug>.md
                             Prior wave results: <summary of completed findings if any>")

  Step 3b — Pipelines (parallel, orchestrator-spawned):
    Emit ALL of this wave's runners in ONE assistant message so they run
    concurrently and the message boundary gives you the wave barrier free.

    For each F0N in this wave (PARALLEL):
      - [ ] Invoke Task(subagent_type: "harness-pipeline",
                        prompt: "Finding: F0N — <title>
                                 Prompt file: plan/prompts/F0N-<slug>.md
                                 Failure budget: 2
                                 Gates: impl -> test")
            Save task_id as pipeline_task_id_F0N.

    Each runner internally does: impl -> (debug if needed) -> test,
    with its own warm retries. It returns ONE verdict line per finding.

  Barrier: wait for ALL runners in this wave to return DONE or BLOCKED.

  Step 3c — REVIEW GATE (mandatory, ONCE per wave, orchestrator-run):
    CRITICAL: Do NOT skip. Do NOT run this per-finding — PR-Agent reviews
    a PR, and the PR is a wave-level artifact. N per-finding invocations
    would be N redundant reviews of the same full diff, each one flagging
    other findings' changes as noise.

      - [ ] Push the wave's branch; create/update a draft PR:
              gh pr create --draft   (first wave)  |  git push  (later waves)
      - [ ] Invoke Task(subagent_type: "harness-review",
                        prompt: "Wave: <n>
                                 Findings in wave: F0N..F0M (titles)
                                 PR URL: <real URL>
                                 Changed files: <union from all runners>
                                 Extra instructions: <domain focus if any>")
      - [ ] PASS      -> mark all wave findings done; append to report.md.
      - [ ] NEEDS_FIX -> for each finding with blocking findings against it,
                         WARM-RETRY its runner:
                           Task(subagent_type: "harness-pipeline",
                                task_id: pipeline_task_id_F0N,
                                prompt: "Review returned blocking findings
                                         against your diff: <findings>.
                                         Fix via harness-impl, re-run tests,
                                         report back.")
                         Then re-run this gate.
      - [ ] BLOCKED   -> fall back to a `general` subagent review with
                         explicit security-focused instructions (see below).

  Step 3d — COLD RETRY (only for BLOCKED findings):
      - [ ] Invoke Task(subagent_type: "harness-recovery",
                        prompt: "<original prompt path + runner's BLOCKED
                                  report + scratchpad paths>")
      - [ ] Then a FRESH Task(subagent_type: "harness-pipeline",
                              prompt: "Prompt file: plan/prompts/F0N.recovery-1.md
                                       Failure budget: 1")

  Move to the next wave.
```

**Why review moved after the test gate.** The previous version of this
skill said both "review each finding in parallel" and "review once per wave
over the full diff" — mutually exclusive instructions. The wave-level
reading is the correct one, which forces review to sit outside the
per-finding runner. Two consequences, both net positive: the review sees
the tests as well as the impl (reviewing test quality is legitimate review
work, and matches how a human PR review actually happens), and the wave
pays one PR-Agent call instead of N. The cost is that a blocking review
finding can require redoing a finding's tests — rare enough to be the
cheaper trade.

**Why JIT prompt generation**: prompts for Wave 2 findings are written
AFTER Wave 1 results are in. If Wave 1 reveals the root cause was
different from what research hypothesized, Wave 2 prompts incorporate
that knowledge instead of working from stale assumptions. This is
especially valuable for findings with `Depends on` relationships.

**Why warm retry before cold retry**: OpenCode's Task tool returns a
`task_id` that resumes the same subagent session with its full prior
context. A warm retry avoids re-reading files and re-understanding the
problem. The recovery agent (cold retry) is the fallback when the agent
is fundamentally stuck, not just timed out.

**Wave failure handling**: if any finding is BLOCKED past its recovery
budget, the orchestrator decides whether to (a) defer just that finding
and proceed to the next wave with its dependents also deferred, or
(b) abort for human input. Default is (a).

### Wall-clock discipline (learned 2026-09-09, 15-finding / 4-wave run, 3h48m)

The harness did not hang once, but it *looked* hung and half its time was
duplicated test runs. Five rules, all cheap:

1. **Announce before you wait.** Every time you dispatch runners, a review
   gate, or a warm retry, emit one line of text first: what is running, how
   many agents, and the expected duration (9 parallel runners ≈ 35–40 min;
   a PR-Agent gate ≈ 6 min; a warm retry ≈ 15 min). A bare spinner for six
   minutes got interrupted by the user while two healthy runners were
   mid-flight. If interrupted: `git status` (partial diffs are on disk,
   scratchpads are current), then resume the same `task_id` — never re-spawn.
2. **Verify once per layer.** Test agent: new test file while iterating,
   the touched area's directory ONCE at the end. Runner: trust that log, or
   re-run the single new file. Orchestrator: full suites exactly once per
   wave, right before the wave commit. Observed anti-pattern: one 2-minute
   Flutter directory suite ran 4–5× per wave across the three layers.
3. **No revert-and-rerun mutation probes** against suites slower than ~30 s.
   "Prove the test fails pre-fix" by reasoning from the diff. A probe that
   edits the fix out, runs a 2-minute suite, restores, and runs again cost
   13 minutes for three widget tests — and dirties the tree if interrupted.
4. **Don't idle at the barrier.** When one straggler is >10 min behind the
   rest of its wave, start prompt authoring for next-wave findings whose
   `Depends on` are all DONE. Prompts write only to `plan/`; no collision.
5. **Move recurring review findings into the impl prompt.** The review gate
   caught the same class five times (resource release on every exit path;
   controls left enabled during an async transition; an a11y node with no
   action) → three review passes on one wave ≈ 45 min. When a wave's review
   flags a class of bug, the prompt author for later waves gets that class
   as an explicit checklist item.

Repos may publish a suite-cost table in their `AGENTS.md` (ai-scribe does);
pass it verbatim into every runner prompt.

### Review gate enforcement

The review gate (Step 3c) uses `harness-review` which runs **PR-Agent**
for AI-powered code review. Key operational requirements:

1. **PR-Agent requires a real GitHub PR URL.** Local dummy URLs
   (`https://github.com/local/repo/pull/0`) do not work — the GitHub
   API rejects them. The orchestrator must:
   - Push the feature branch to origin
   - Create a draft PR via `gh pr create --draft`
   - Pass the real PR URL to the review script
   - This can be done once per wave (after all impl agents finish),
     not per-finding

2. **Review runs once per wave, after every pipeline runner has
   returned** — never per-finding. PR-Agent reviews the full PR diff,
   which is both cheaper and more useful than N reviews of the same
   diff from N different vantage points.

   **Always pass `CONFIG__MAX_MODEL_TOKENS=400000`** (an env var the
   review runner forwards to pr-agent). pr-agent's default
   `max_model_tokens` is 32 000; a larger diff is silently pruned and the
   run returns a confident score about whatever files survived. Observed
   2026-09-09: a 57k-token diff scored 89/100 having dropped every focus
   file. `PR_AGENT_MODEL_MAX_TOKENS` does NOT raise this cap. Ask the
   review agent to confirm in its output that the focus files were in the
   reviewed diff.

3. **If PR-Agent is BLOCKED** (missing API key, network error, etc.),
   the orchestrator should fall back to a manual review using the
   `general` subagent type with explicit security-focused instructions.
   Check for this in Phase 0, not at wave 1.

4. **Blocking findings** are routed back by warm-retrying the owning
   finding's `harness-pipeline` runner (via its saved `task_id`), which
   re-invokes `harness-impl` and re-runs its test gate. Advisory findings
   are logged in `report.md` but do not block.

5. **`harness-review` is spawned by the orchestrator, not by a runner.**
   It is deliberately absent from `harness-pipeline`'s `task` allowlist,
   so a runner physically cannot invoke it.

### Test gate enforcement

The test gate is **mandatory** for every finding pipeline, and it lives
inside the pipeline runner (`harness-pipeline` step 3). Neither the
orchestrator nor a runner may:

- Mark a finding as "done" without a green test run
- Skip the test step to "save time" — this creates false confidence
- Move to the next wave while any finding in the current wave has
  impl done but tests not run
- Treat build/typecheck success alone as sufficient verification

A runner that returns `DONE` without a `Tests:` line in its verdict has
violated its contract; treat that verdict as BLOCKED and warm-retry it.

The test agent should write tests that:

1. **Would fail on pre-fix code** (proves the impl actually changed
   behaviour)
2. **Pass on post-fix code** (proves the impl is correct)
3. **Cover edge cases** mentioned in the finding's reproduction steps

If the project has no test framework set up, the test agent should
set one up as part of its work (e.g., vitest, pytest, flutter test).

If tests cannot be written for a finding (e.g., pure infrastructure
like Terraform), the test agent should document why and perform a
manual verification checklist instead. This exception must be noted
in the finding's report entry.

### Phase 4 — Wrap

- Aggregate completion logs from each finding into `plan/report.md`.
- Record decisions the way the repo's `AGENTS.md` says. Default to the
  lightest record that survives the run: put what changed in the PR body,
  and save each non-obvious decision from the completion logs as one memory
  in the shared memory (e.g. supermemory) if the repo uses one. Write an ADR
  or CHANGELOG entry only when the repo's rules require one for that kind of
  change. A harness run does not need one ADR per finding, or a changelog
  entry per finding.
- Surface the report to the user with a short summary and links to
  each fixed finding.

## Scratchpad protocol

Every subagent invocation maintains a **scratchpad** — a markdown file
keyed by a UUID the subagent generates at start. The scratchpad is the
subagent's working memory: it persists progress, hypotheses, and
decisions to disk as the task advances, so:

- The subagent can re-anchor if its own context drifts mid-task.
- The recovery agent can read what was tried when an attempt fails.
- Warm retries have a persistent record even if the context was lost.
- The wrap-up phase has a complete audit trail.
- Multiple parallel subagents in the same wave never collide on
  filenames (UUIDs are unique).

### Convention

- **Path**: `plan/scratch/<role>-<scope>-<uuid>.md`
  - `<role>` is human-readable: `research-data-sherpa`, `prompt`,
    `pipeline-F01`, `impl-F01`, `debug-F03`, `test-F02`,
    `recovery-F01-1`.
  - `<uuid>` is generated once at start: `uuidgen | tr 'A-Z' 'a-z'`.
- **Format**: copy `${CLAUDE_SKILL_DIR}/templates/scratchpad.md`.
- **Lifecycle**: created on the first action; appended to (not
  overwritten) for each meaningful step; closed with a `Status:
  DONE | BLOCKED | <reason>` line in the final message.
- **Returned**: every subagent's final message MUST cite the
  scratchpad path so the parent can locate it later.

### What to write

Append to the scratchpad as work progresses. Good entries:

- "Read `recording_provider.dart`; `_runFinalDiarizationAsync` uses
  `unawaited` (line 198), confirms F03 hypothesis."
- "Tried adding `await` at line 198 — broke 3 unit tests; reverting
  and switching to a `Future` return."
- "Decision: keep periodic-tick interval at 8 s rather than expose
  as setting (out of scope per `objective.md`)."

Bad entries (skip these — they are noise):

- "Reading file..."
- "Thinking about the problem."
- "User asked me to implement F01."

### Convention for parallel waves

When the parent dispatches a wave's pipelines in parallel, every
finding-pipeline's subagents share the same finding ID prefix
(`pipeline-F01`, `impl-F01`, `debug-F01`, `test-F01`) but have unique
UUIDs. The parent can search `plan/scratch/*-F0N-*` to find every
scratchpad related to one finding when writing the wrap-up report.

This is why the scratchpad convention matters more once runners are in
play than it did when the orchestrator spawned every leaf directly: the
orchestrator no longer sees leaf transcripts at all, so `plan/scratch/`
is its only window into what `harness-impl` and `harness-test` actually
did. A runner that fails to cite its children's scratchpad paths has
made its finding un-auditable.

Recommend gitignoring `plan/scratch/` (working memory is noise);
keep `plan/findings.md`, `plan/pipelines.md`,
`plan/prompts/`, and `plan/report.md` in version control.

## File templates

The skill ships five templates — copy and fill in:

- `${CLAUDE_SKILL_DIR}/templates/objective.md` — Phase 0 scope
- `${CLAUDE_SKILL_DIR}/templates/finding.md` — Phase 1 research output
- `${CLAUDE_SKILL_DIR}/templates/impl-prompt.md` — Phase 3a per-finding prompt
- `${CLAUDE_SKILL_DIR}/templates/pipelines.md` — Phase 2 plan (output format reference)
- `${CLAUDE_SKILL_DIR}/templates/scratchpad.md` — every subagent's working-memory file

## Scripts

- `${CLAUDE_SKILL_DIR}/scripts/build_pipelines.py` — deterministic DAG
  builder. Reads `findings.md`, produces `pipelines.md`. Run during
  Phase 2 via the Bash tool.

## Subagent definitions

The skill relies on eight global subagent definitions installed at
`~/.config/opencode/agents/harness-*.md`. Invoke them via the Task tool
with the corresponding `subagent_type`.

Spawned by the **orchestrator**:

- `harness-research` — read-only codebase exploration
- `harness-prompt` — per-finding prompt authoring (one finding at a time)
- `harness-pipeline` — per-finding pipeline runner (impl → test)
- `harness-review` — PR-Agent code review gate (PASS/NEEDS_FIX/BLOCKED),
  once per wave
- `harness-recovery` — prompt rewriting for cold retries

Spawned by **`harness-pipeline`** (never by the orchestrator directly):

- `harness-impl` — focused implementation from a single prompt
- `harness-test` — test writing + execution gate
- `harness-debug` — root-cause analysis without edits

That split is enforced by `harness-pipeline`'s `task` allowlist, not just
convention. Requires `"subagent_depth": 2`.

## Example invocations

See `${CLAUDE_SKILL_DIR}/examples/` for worked examples:

- `examples/mobile-bugs.md` — finding and fixing bugs in a Flutter
  recording pipeline
- `examples/api-perf.md` — finding and fixing performance regressions
  in a REST backend

## Anti-patterns to avoid

1. **Letting the parent agent do the work itself.** If the parent ends
   up writing code instead of orchestrating, that is a chat, not a
   harness. Push the work into a subagent even when it feels faster
   to do it inline.
2. **One mega-subagent that does research + implementation + tests.**
   Loses context isolation. The whole point of the harness is that
   each role has a clean context window.
3. **Skipping JIT prompt generation and hand-writing prompts.** The
   prompt-author agent exists to keep prompt authoring from being a
   manual job. Spawn it per-finding in the wave, not ad-hoc.
4. **Running findings strictly serially without checking the DAG.**
   The whole win of a harness vs. a single chat is parallel execution.
   If `pipelines.md` is one finding per wave, recheck — dependencies
   were probably over-declared.
5. **Running findings in parallel without a wave barrier.** Two
   findings touching the same file will race their diffs and one will
   lose. Always honour wave boundaries.
6. **No recovery role.** Every harness eventually has a subagent that
   times out, runs out of tokens, or returns empty. Without recovery
   the loop escalates to the human; with it, the loop self-heals.
7. **Skipping warm retry and going straight to cold retry.** Warm
   retry (resuming via task_id) is faster and preserves context. Use
   it first; cold retry (recovery agent) is the fallback.
8. **Findings table without severity / file:line / depends_on /
   touches_files.** A research output without those fields is
   unactionable; the DAG builder cannot schedule it AND the prompt-
   author has nothing to anchor the impl prompt against.
9. **Shipping the harness output without running the tests.** The
   test gate inside each pipeline runner is MANDATORY, not optional
   polish. Every finding must have a green test run before it is marked
   done. "It compiles" is not "it works." If you find yourself skipping
   tests to move faster, you are building a house of cards.
10. **The orchestrator spawning `harness-impl` / `harness-test` /
   `harness-debug` directly.** Those are the runner's children. Bypassing
   the runner pulls every gate transcript back into the orchestrator's
   context, which is the exact cost the runner exists to eliminate — and
   it silently drops the per-finding retry loop.
11. **Raising `subagent_depth` past 2 to "allow more parallelism."**
   Depth is not a concurrency knob; opencode has no concurrency cap at
   all, so a wave is already as wide as the DAG permits. What extra depth
   buys is multiplicative fan-out — findings × gates × sub-delegations —
   with no ceiling. Depth 2 is deliberately the minimum that makes the
   runner work.
12. **Reviewing per-finding instead of per-wave.** N runs of PR-Agent
   over the same PR diff, each flagging the other findings' changes as
   unexplained noise. Review the wave once.

## Closing checklist

Before declaring the harness done:

- [ ] `plan/objective.md` exists and matches what was actually done
- [ ] `plan/findings.md` has a row for every finding, with status
      AND `Depends on` / `Touches files` columns filled in
- [ ] `plan/pipelines.md` shows the wave plan that was actually
      executed (annotate any waves that ran serially-by-recovery)
- [ ] `plan/prompts/` has one file per executed finding, plus any
      `.recovery-N.md` files
- [ ] `plan/scratch/` has at least one scratchpad per subagent
      invocation that ran, including one `pipeline-F0N-*` per finding
      and the `impl-` / `test-` scratchpads its runner cited
- [ ] `plan/report.md` summarises completions and any deferred items
- [ ] Decisions recorded per the repo's AGENTS.md (memory and PR body
      by default; ADR/CHANGELOG only if the repo requires them)
- [ ] **Every finding has a test run logged** (green test output or
      documented exception for untestable findings like Terraform)
- [ ] All tests pass; lints clean
- [ ] Deferred findings are listed in the backlog with a one-line
      rationale
