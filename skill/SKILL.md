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
`~/.config/opencode/agent/harness-*.md`) plus an orchestration loop the
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

A complete harness has six roles. Cut the ones not needed; never add a
seventh without a strong reason — diluting roles is how harnesses go bad.

| Role | `subagent_type` | Tool restrictions | Output |
|------|-----------------|-------------------|--------|
| **Research** | `harness-research` | `edit: false` | Structured findings file with file:line refs |
| **Prompt author** | `harness-prompt` | — | One tailored implementation-prompt `.md` per finding |
| **Implementation** | `harness-impl` | — | A diff that compiles + one-line completion log |
| **Debug** | `harness-debug` | `edit: false` | Root-cause note + recommended patch (no edits) |
| **Unit test** | `harness-test` | — | New / amended tests + green test-run log |
| **Recovery** | `harness-recovery` | `edit: false` | A revised prompt for whichever role failed |

All harness agents have `task: false` (no recursive sub-spawning) and
`todowrite: false` (parent owns the task list).

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
        (b) Run finding-pipelines IN PARALLEL: impl → debug → test.
        (c) On failure: warm retry (resume task_id) → cold retry
            (recovery agent + fresh impl).
        Wait for the whole wave to complete before the next wave.
- [ ] Phase 4 — Wrap. Aggregate completion logs into report.md.
        Update CHANGELOG / ADRs per repo conventions.
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

```
For each wave:
  Step 3a — Prompt (parallel):
    For each F0N in this wave (PARALLEL):
      - Invoke Task(subagent_type: "harness-prompt",
                    prompt: "<finding details from findings.md>
                             Template: ${CLAUDE_SKILL_DIR}/templates/impl-prompt.md
                             Output: plan/prompts/F0N-<slug>.md
                             Prior wave results: <summary of completed findings if any>")
      - Save task_id (not needed for prompt, but consistent)

  Step 3b — Finding pipelines (parallel):
    For each F0N in this wave (PARALLEL):
      - [ ] Implementation: invoke Task(subagent_type: "harness-impl",
                                        prompt: "Prompt: plan/prompts/F0N-<slug>.md")
            Save task_id as impl_task_id_F0N.
      - [ ] On impl failure — WARM RETRY:
              Resume via Task(subagent_type: "harness-impl",
                              task_id: impl_task_id_F0N,
                              prompt: "You timed out / returned empty.
                                       Your scratchpad shows: <summary>.
                                       Focus only on: <remaining items>.")
      - [ ] On warm retry failure — COLD RETRY:
              Invoke Task(subagent_type: "harness-recovery",
                          prompt: "<original prompt path + failed transcript>")
              Then invoke a FRESH Task(subagent_type: "harness-impl",
                                       prompt: "plan/prompts/F0N.recovery-1.md")
      - [ ] Debug: invoke Task(subagent_type: "harness-debug")
              only if the impl output shows a regression or unexpected behaviour.
              Route the debug note back to impl if a re-fix is needed.
      - [ ] Unit test: invoke Task(subagent_type: "harness-test")
              Write tests, run them, attach the green log.
      - [ ] Mark F0N done in findings.md; append to report.md.

  Barrier: wait for ALL F0N in this wave to reach DONE or BLOCKED.
  Move to the next wave.
```

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

### Phase 4 — Wrap

- Aggregate completion logs from each finding into `plan/report.md`.
- Update repo conventions (CHANGELOG, ADRs, etc.) per the repo's
  `AGENTS.md` or equivalent.
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
    `impl-F01`, `debug-F03`, `test-F02`, `recovery-F01-1`.
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
(`impl-F01`, `debug-F01`, `test-F01`) but have unique UUIDs. The
parent can search `plan/scratch/*-F0N-*` to find every scratchpad
related to one finding when writing the wrap-up report.

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

The skill relies on six global subagent definitions installed at
`~/.config/opencode/agent/harness-*.md`. Invoke them via the Task tool
with the corresponding `subagent_type`:

- `harness-research` — read-only codebase exploration
- `harness-prompt` — per-finding prompt authoring (one finding at a time)
- `harness-impl` — focused implementation from a single prompt
- `harness-debug` — root-cause analysis without edits
- `harness-test` — test writing + execution gate
- `harness-recovery` — prompt rewriting for cold retries

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
   unit-test phase is the gate, not optional polish.

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
      invocation that ran
- [ ] `plan/report.md` summarises completions and any deferred items
- [ ] CHANGELOG / ADRs updated per repo conventions
- [ ] All tests pass; lints clean
- [ ] Deferred findings are listed in the backlog with a one-line
      rationale
