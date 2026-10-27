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

# Create Harness (omp)

A **harness** is a structured team of subagents that take a complex,
ambiguous task from "we want to improve X" to a list of concrete findings
to a pile of executed fixes that compile, run, and have tests behind them.

In omp the harness keeps **no state in repo files**. The approved plan is a
`local://` file, findings and verdicts are structured agent outputs read
through `agent://`, the work list is the `todo` tool, transcripts are
`history://`, and the report is the pull request body. The orchestrator
(you) owns the plan, the `todo` list, and every decision.

## When to use this skill

Use a harness when **all** of these are true:

- The task is too big for one chat to hold in context end-to-end.
- The task naturally decomposes into research, fix, and verify.
- Failures during execution are recoverable (retryable with better
  instructions, not just escalate to the human).

Do not bother with a harness for single-file edits, tasks where the fix is
already known, or one-shot questions that just need exploration (use the
bundled `scout` agent for cheap search).

## Harness mechanics (omp)

| Need | omp primitive | Source |
|------|---------------|--------|
| Spawn agents | `task` tool, batch shape `{context, tasks:[{name?, agent, task, solutionSpace, isolated?}]}`. `context` is required and is rendered into every spawned agent's system prompt. | task.md:35-45 |
| Handle on an agent | Its agent id = the `name` you gave. Ids are session-unique: a repeated name becomes `Name-2`, `Name-3`. Record the ids the call actually returns. | task.md:44,205 |
| Read a result | `read agent://<id>` (full output) or `read agent://<id>/<key>/<index>/...` (JSON extraction from the structured result). | task.md:95-96, read.md:93 |
| Warm retry | `write agent://<id>` with the retry text; revives a parked agent with its full prior context. | task.md:128,197 |
| What an agent did | `history://<id>` (concise transcript); bare `history://` lists registered agents. | task.md:97,197 |
| Nesting depth | `task.maxRecursionDepth`, default 2: orchestrator 0, runner 1, leaf 2. | task-agent-discovery.md:328 |
| Who a runner may spawn | `spawns:` in the agent's frontmatter (CSV or array). Enforced; a denied spawn fails with `Cannot spawn '...'. Allowed: ...`. | task-agent-discovery.md:39,312-320 |
| Concurrency | `task.maxConcurrency`, default 32; extra spawns queue. | task.md:169 |
| Bundled fallbacks | `task` (general), `reviewer` (review), `scout` (cheap search). | task-agent-discovery.md:135 |
| Work list | `todo` tool (orchestrator only; subagents never get it). | todo.md:22-26,171 |
| Waiting | `wait` blocks for the next result; results also auto-deliver. | wait.md:11,20 |
| Skill directory | `skill://create-harness/...`; in `bash` it resolves to the directory. | skills.md:178-191 |
| Shared scratch files | `local://` root, shared with all subagents. | task.md:38,196 |

`harness-pipeline`'s allowlist is exactly:

```yaml
spawns: harness-impl, harness-test, harness-debug
```

`harness-review` is absent **by design**: review is a wave-level gate that
the orchestrator spawns itself, never a runner.

### Roster and roles

Agents name a **role**, never a model. The role pins live in the harness
config repo's `roles.yaml`; to change what a role runs, edit it there and
re-run the installer, or switch the live roles with `/modelpreset`.

| Agent | Role | Spawned by | Output | Why this role |
|-------|------|-----------|--------|---------------|
| `harness-research` | `research` | orchestrator | findings JSON (`findings.schema.json`) | Findings quality gates every later phase. It assigns severity and declares `depends_on` / `touches_files`, which is what the DAG builder schedules from. A missed bug is never fixed; a wrong `touches_files` schedules two conflicting diffs into one wave. Do not downgrade it to the search tier: it is the most expensive slot and still the one to resist cutting. |
| `harness-prompt` | `structured` | orchestrator | one prompt file per finding | Templating a finding into a prompt needs no frontier reasoning and is high-volume. |
| `harness-pipeline` | `structured` | orchestrator | `pipeline-verdict.schema.json` | Sequences gates from explicit PASS/NEEDS_FIX verdicts; high-volume. Must never write code. |
| `harness-impl` | `impl` | pipeline | a diff + completion log | Focused implementation from a single prompt. |
| `harness-test` | `test` | pipeline | tests + green run log | The code-writing role that proves the impl changed behaviour; gets the strongest implementation tier. |
| `harness-debug` | `reason` | pipeline | root-cause note, no edits | Root-cause analysis is one of the hardest reasoning jobs in the loop. |
| `harness-review` | `review` | orchestrator | `review-verdict.schema.json` | Security and correctness judgment, once per wave. |
| `harness-recovery` | `reason` | orchestrator | `recovery.schema.json` | Diagnosing why an agent failed is a judgment job; it is what turns a timeout into a smaller-scope retry. |

Never add a ninth role without a strong reason; diluting roles is how
harnesses go bad.

### Why the runner exists

The orchestrator's context window, not concurrency, is the scaling limit.
`harness-pipeline` collapses four gate transcripts per finding into one
verdict and keeps each finding's warm-retry loop local, where the failure
context is already in-window. "Coordinate, never implement" is enforced in
the runner's prompt and by its `spawns` allowlist.

## Methodology: five-phase loop

Phases 1-4 run only after the plan is approved (Phase 0).

```
- Phase 0 - Scope. Plan mode: write the plan, submit it for approval.
- Phase 1 - Research. One batched task call of harness-research agents.
- Phase 2 - Plan. build_pipelines.py -> waves -> todo list.
- Phase 3 - Execute, per wave: prompts -> review channel -> pipelines
            -> review gate -> retries.
- Phase 4 - Wrap. Report into the PR body; close the todo list.
```

### Phase 0 - Scope (plan mode)

1. Enter plan mode. Write `local://<slug>-plan.md` containing: the
   objective (one sentence), out of scope (temptations to resist), the
   definition of done (tests passing, lints clean, manual smoke), the
   failure budget per finding (default 2 retries), and
   the preconditions result below.
2. Submit it by writing the slug to `xd://propose`
   (resolve-tool-runtime.md:7,39). Plan approval rides only on that write.
3. Plan mode is read-only and rejects `isolated` (task.md:35,114), and
   approval may clear or compact the conversation. The plan file must
   therefore be self-contained. The approved-plan reference is handed to
   every subagent automatically (task.md:116,201); per-wave extras go in
   the batch `context` field.
4. Headless runs use `--plan-yolo --plan-yolo-into default`
   (cli-reference.md:133-134). `--plan-yolo` alone executes on the `smol`
   role, which would run every wave of the orchestrator on the cheapest
   model; `--plan-yolo-into default` keeps the orchestrator on the default
   role.

#### Preconditions - record the result in the plan

Verify before submitting; each one fails awkwardly mid-wave if found late:

- `omp config get task.maxRecursionDepth` prints at least 2
  (task-agent-discovery.md:328; settings.md:48,69).
- `omp config get task.isolation.enabled` prints true and the repo is a git
  repo (task.md:35, 138-139).
- `omp config get async.enabled` prints true (settings.md:623).
- Every `harness-*` agent, as generated by the omp build, declares
  `model: "@<role>"`, and `harness-pipeline` declares the `spawns` line
  above. Exactly four agents also declare `structured: true` and an
  `output` schema: `harness-research`, `harness-pipeline`, `harness-review`
  and `harness-recovery`. The other four (`harness-impl`, `harness-test`,
  `harness-debug`, `harness-prompt`) correctly have neither. `structured:
  true` plus `output` is what gives those four agents `yield` and schema
  validation while `task.structured` is off; it does not unhide the
  caller-side `outputSchema`, which stays hidden while `task.structured` is
  off (task-agent-discovery.md:46,290). If any expected declaration is
  missing, stop and tell the user to re-run the installer.
- Review gate reachable: `gh auth status`, `git remote get-url origin`, and
  an LLM key for PR-Agent. If any fails, record `REVIEW_MODE=fallback` (the
  bundled `reviewer` agent with security-focused instructions) now; do not
  discover it at wave 1.
- A test runner exists (check `package.json`, `pyproject.toml`,
  `pubspec.yaml`).

### Phase 1 - Research (parallel)

ONE batched `task` call: one item per slice, `agent: "harness-research"`,
non-overlapping scopes (three is usually right, never more than five), the
shared `context` pointing at the approved plan. Each yields JSON conforming
to `schemas/findings.schema.json`.

Give each slice its own id block in its `task` text: ResearchA numbers
F101, F102, ..., ResearchB F201, F202, ..., ResearchC F301, ... (the schema
pattern `^[A-Z]+\d+$` allows this). Tell each slice to number its findings
from its block and to use those ids in `depends_on`. Ids must be unique
across slices, because `build_pipelines.py` rejects a duplicate id (exit 2,
`Duplicate finding ID F01`) and every slice numbering from F01 would collide.
A cross-slice `depends_on` is not possible (a slice cannot know another
slice's ids); the script derives cross-slice ordering from `touches_files`
overlaps.

Every finding declares `depends_on` and `touches_files`. Do not drop
legitimate findings to hit a line target.

Read fields with JSON-path reads, for example
`read agent://ResearchA/findings/0/depends_on` (task.md:96). Never paste
findings back into your own context.

### Phase 2 - Plan (deterministic)

The structured result of each research agent is persisted as a sidecar
`<id>.json` next to `<id>.md` in the session artifacts directory
(task.md:94-95). `realpath agent://<id>` in `bash` prints the physical path
of the `.md` (bash.md:196), so export the findings and build the plan.
A slice that found nothing yields `{"findings": []}`, which is valid. If
every slice is empty, research has answered the objective with "nothing to
fix": do not run the script (it exits 2 on a zero total), skip Phase 3, and
go straight to Phase 4 reporting that result. Otherwise:

```bash
d=$(dirname "$(realpath agent://ResearchA)")
python3 skill://create-harness/scripts/build_pipelines.py \
  --findings-json "$d/ResearchA.json" "$d/ResearchB.json" "$d/ResearchC.json" \
  --format json --output local://pipelines.json
```

The script emits `{title, waves:[{findings:[...]}], todo_init}`. Edges come
from explicit `depends_on` AND file-conflict overlaps in `touches_files`;
waves are topologically sorted (higher severity first, more dependents
first, smaller scope first). It exits non-zero on validation failures:

- **Cycle detected**: a `depends_on` is wrong, or two findings should merge.
  Re-examine the findings; this is a research output bug.
- **Shared files in one wave**: a script bug, since it should have pushed
  one finding later.

Then initialize the work list from the emitted `todo_init`: call `todo` with
`{op:"init", list:[...]}` exactly as emitted. Waves are phases (`Wave N`);
each task content is an exact, unique string of the form
`F01 - <title>` with an ASCII hyphen-minus separator (todo.md:22,162).
`todo` lookups are exact string matches, so copy the strings from
`todo_init` rather than retyping them.

### Phase 3 - Execute (per wave, in order)

The orchestrator spawns exactly two kinds of agent per wave before the
review gate: prompt authors, then pipeline runners. It never spawns
`harness-impl`, `harness-test`, or `harness-debug` directly.

**(a) JIT prompts.** One batched `task` call, `agent: "harness-prompt"`,
`name: "PromptF0N"` per finding. Each writes its prompt to
`local://prompts/F0N-<slug>.md` (the `local://` root is shared with
subagents, task.md:38,196) and returns the path. This is the only file
artifact and it lives in the session sandbox, not the repo. Each prompt
includes the verbatim rule: **subagents never run test suites**; they run
only the test files they created or edited. Prompts are written after the
previous wave's results are in, so they reflect what was actually learned.

**(b) Review channel.** Push the wave's branch and create or update a draft
PR (`gh pr create --draft` first wave, `git push` later), or honour
`REVIEW_MODE=fallback`.

**(c) Pipelines.** One batched `task` call, `agent: "harness-pipeline"`,
`name: "PipelineF0N"`, one item per finding. Set `isolated: true` on each
item so same-wave findings implement in parallel without racing the working
tree (task.md:35,138-139). Merge-back is governed by `task.isolation.merge`
and `task.isolation.apply`; a conflict or failed merge surfaces in the task
result and recovery artifacts are preserved (task.md:117,203). Each runner
yields `schemas/pipeline-verdict.schema.json`. Always use the ids the call
actually returned (they may be uniquified; children are prefixed by their
parent id, for example `PipelineF01.ImplF01`). Read verdicts with
`read agent://PipelineF0N/status` and `/blocker`. The verdict schema
rejects `DONE` unless `tests.result` is `"pass"`; a runner whose result
fails that validation violated its contract, so treat it as BLOCKED and
retry it under the rule in (e).

Update the work list as verdicts arrive: `todo` `done` on the finding's task
for DONE; `block` with a `reason` for BLOCKED (todo.md:24-26). Subagents
never get `todo` (todo.md:171); you own it.

**(d) Review gate, once per wave.** After every runner has returned, spawn
`harness-review` from the orchestrator (never from a runner) with the PR
URL, the wave's findings, and the union of changed files. It yields
`schemas/review-verdict.schema.json`. Review runs once per wave over the
whole PR diff, never per finding: N reviews of the same diff each flag the
others' changes as noise. PR-Agent needs a REAL GitHub PR; local dummy URLs
are rejected. Always pass `CONFIG__MAX_MODEL_TOKENS=400000` through to the
review run, because the default 32 000 silently prunes a large diff, and
ask the review agent to confirm the focus files were in the reviewed diff.

- PASS: `todo` `done` on `phase: "Wave N"`.
- NEEDS_FIX: for each finding with blocking items, retry that finding's
  runner under the rule in (e) with the items, then re-run the gate. Advisory items go in the
  report and do not block.
- BLOCKED: fall back to the bundled `reviewer` agent with explicit
  security-focused instructions.

**(e) Retries.**

One rule. Pipeline runners are spawned `isolated: true` and are retried
**cold**: a failed or NEEDS_FIX runner gets a fresh runner. omp can revive
isolated agents with their workspace (task.md:54,126), but whether a second
patch capture re-applies cleanly after the first one merged is unverified,
so a fresh runner is the safe retry. A non-isolated agent (for example `harness-prompt` or
`harness-research`) is retried **warm**.

- **Warm** (non-isolated agents only) = `write agent://<returned id>` with
  the failure text, then `wait`. It revives the parked agent with full prior
  context (task.md:128,197). A run that dies instantly with an "API
  safeguard error" before any edit has always recovered on warm retry.
- **Cold** (every isolated runner) = spawn `harness-recovery` with `task` text naming the failed
  agent id and telling it to read `history://<failed-id>` (task.md:97,197).
  It yields `schemas/recovery.schema.json`. `revised_prompt_path` is a
  `local://prompts/F0N.recovery-N.md` string, or `null` only when
  `failure_mode` is `genuinely_blocked`; in that case escalate to the human
  and do not respawn. Otherwise spawn a fresh runner (new `name`, for
  example `PipelineF0N-r1`, isolated) on the revised prompt. For a NEEDS_FIX with
  no failure to diagnose, skip `harness-recovery`: the fresh runner's
  `task` text carries the review items. The budget per finding
  comes from the plan file.
- If the wave has a finding BLOCKED past its budget, default to deferring
  it (and its dependents) and moving on: `todo` `drop` with a one-line
  reason.

**(f) Wall-clock discipline** (learned on a 15-finding, 4-wave run that
took 3h48m and looked hung half the time). Five rules:

1. **Announce before you wait.** Before dispatching runners, a review gate,
   or a warm retry, emit one line: what is running, how many agents, and the
   expected duration (9 parallel runners about 35-40 min; a PR-Agent gate
   about 6 min; a warm retry about 15 min). Then call `wait`, which blocks
   for the next result (results also auto-deliver, wait.md:11,20; 30-minute
   safety cap, wait.md:16). Inspect progress with `read proc://`
   (wait.md:23,26) or the Agent Hub on `Alt+A` (task-agent-discovery.md:109).
   If a non-isolated agent is interrupted, resume it with
   `write agent://<returned id>`; isolated runners are retried cold.
2. **Subagents never run test suites; the orchestrator runs them once, at
   the end.** Every subagent in a parallel run (impl, test, runner,
   integrator, fix agent) runs ONLY the test files it created or edited.
   Forbidden inside a subagent: a package's whole suite or a test
   directory, DB / integration tiers, starting containers, builds, bundle
   checks, the visual harness, package-wide typechecks. Put this rule
   verbatim in every subagent prompt; agents otherwise "helpfully" run
   everything. The orchestrator's ladder:
   - **Between waves:** typecheck + lint once, plus the wave's new test
     files. No full suites.
   - **Once all subagents are finished:** the full suites, ONCE, serially
     (never two at once on one machine), then push and let CI arbitrate.
     A CI red is fixed in one batch, not one push per test.
   - **Never** re-run a green suite to double-check, and never run a full
     CI mirror per wave.
3. **No revert-and-rerun mutation probes** against suites slower than about
   30 s. Reason from the diff.
4. **Do not idle at the barrier.** When one straggler is more than 10 min
   behind its wave, start prompt authoring for next-wave findings whose
   `depends_on` are all DONE.
5. **Move recurring review findings into the impl prompt.** When a wave's
   review flags a class of bug, later prompt authors get that class as an
   explicit checklist item.

Repos may publish a suite-cost table in their `AGENTS.md`; pass it verbatim
into every runner prompt.

#### Test gate

Mandatory for every finding and it lives inside the runner. "Green" means
the finding's OWN new or edited test files, not the area suite. Neither the
orchestrator nor a runner may: mark a finding done without a green run of
its own tests; skip the step to save time; move to the next wave while a
finding has impl done but tests not run; treat build or typecheck success
alone as verification. Tests must fail on pre-fix code (argue it from the
diff), pass on post-fix code, and cover the edge cases in the finding. If
tests cannot be written (pure infrastructure), the test agent documents why
and does a manual checklist; note the exception in the report.

### Phase 4 - Wrap

- Render the report from verdict JSON read via `agent://` paths (finding id,
  title, `files_changed`, `tests`, `warm_retries`, `spillover`, review
  items) into markdown at `local://report.md`. Pass it as the PR body:
  `gh pr edit --body-file` (or `gh pr create --body-file`). Resolve the
  `local://` path with `realpath` first if the tool needs a physical path.
- Close the work list: `todo` `done` on remaining phases, `drop` on deferred
  findings with a one-line reason, and `append` a `Wrap` phase (todo.md:29).
- Record decisions the way the repo's `AGENTS.md` says. Default to the
  lightest record that survives the run: what changed goes in the PR body,
  and each non-obvious decision from the completion logs becomes one memory
  in the shared memory if the repo uses one. Write an ADR or CHANGELOG entry
  only when the repo's rules require one for that kind of change; not one
  per finding.
- Surface the report to the user with a short summary.

## Transcripts

omp keeps every subagent's transcript. Use `history://<id>` to see what an
agent did and `history://` to list registered agents. This is how a
recovery agent learns what was tried, and how you audit a runner's
children: runner children are dot-qualified (`PipelineF01` spawns
`ImplF01`, whose full id is `PipelineF01.ImplF01`; task.md:96 and the
nesting note there). Always use the id the task call returned.

## Subagent definitions

Spawned by the **orchestrator**: `harness-research`, `harness-prompt`,
`harness-pipeline`, `harness-review`, `harness-recovery`.

Spawned by **`harness-pipeline`** only: `harness-impl`, `harness-test`,
`harness-debug`. That split is enforced by the `spawns` allowlist, not just
convention, and needs `task.maxRecursionDepth` of 2.

Schemas live at `skill://create-harness/schemas/`: `findings.schema.json`,
`pipeline-verdict.schema.json`, `review-verdict.schema.json`,
`recovery.schema.json`. The DAG builder is
`skill://create-harness/scripts/build_pipelines.py`.

## Anti-patterns to avoid

1. **Letting the parent agent do the work itself.** If the parent ends up
   writing code instead of orchestrating, that is a chat, not a harness.
2. **One mega-subagent that does research + implementation + tests.** It
   loses context isolation, which is the whole point.
3. **Skipping JIT prompt generation and hand-writing prompts.** Spawn the
   prompt author per finding in the wave.
4. **Running findings strictly serially without checking the DAG.** If the
   plan is one finding per wave, dependencies were probably over-declared.
5. **Running findings in parallel without a wave barrier.** Two findings
   touching the same file race their diffs and one loses.
6. **No recovery role.** Every harness eventually has a subagent that
   times out, runs out of tokens, or returns empty.
7. **Cold-retrying a non-isolated agent, or warm-retrying an isolated
   one.** Non-isolated agents resume with `write agent://<returned id>`,
   which is faster and keeps context; isolated runners are retried cold (see (e)).
8. **Findings without severity, file:line, `depends_on`, `touches_files`.**
   The DAG builder cannot schedule them and the prompt author has nothing
   to anchor on.
9. **Shipping without running the tests.** "It compiles" is not "it works."
10. **The orchestrator spawning `harness-impl` / `harness-test` /
    `harness-debug` directly.** It pulls every gate transcript back into
    your context and drops the per-finding retry loop.
11. **Raising `task.maxRecursionDepth` past 2 "for parallelism."** Depth is
    not a concurrency knob (that is `task.maxConcurrency`); extra depth
    buys unbounded multiplicative fan-out.
12. **Reviewing per finding instead of per wave.**
13. **Re-pasting agent output into your own context** instead of reading
    `agent://<id>/<path>` for just the field you need.

## Closing checklist

- [ ] The plan was approved and still matches what was actually done
- [ ] Every `todo` task is closed (`done`, or `drop` with a reason)
- [ ] Every finding has a verdict, with a green run of its own test files
      (or a documented exception for untestable findings)
- [ ] Every wave got exactly one review pass that ended PASS (or a recorded
      fallback review)
- [ ] The full suites ran ONCE, serially, after the last subagent finished,
      and pass; lints clean. No subagent ran a suite
- [ ] The PR body contains the report, including deferred findings with a
      one-line rationale
- [ ] Decisions recorded per the repo's `AGENTS.md`

## Where omp differs

1. **No export-agent-output-to-file tool.** The closest real mechanism is
   the `<id>.json` sidecar located via `realpath agent://<id>`
   (bash.md:196, read.md:92).
2. **`isolated` is unavailable in plan mode** (task.md:35), so Phase 0 cannot
   dry-run an isolated spawn.
3. **`todo` is orchestrator-only** (todo.md:171); runners cannot tick their
   own tasks.
4. **Isolated runners are retried cold.** omp can revive them with their
   workspace (task.md:54,126), but a second patch capture after the first
   one merged is unverified, so a fresh runner is the safe retry.
5. **`harness-review` needs a real PR.** There is no local-diff review mode;
   without a pushable remote the gate degrades to the bundled `reviewer`.
