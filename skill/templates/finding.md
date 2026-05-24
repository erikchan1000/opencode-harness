# Harness — Finding template

> Phase 1 artefact. Each research subagent writes one of these per
> issue it identifies. The orchestrator merges them into a single
> `findings.md` table.

## ID

<!-- F01, F02, … assigned by the orchestrator at merge time. Leave blank. -->

## Severity

<!-- Pick exactly one: -->
- [ ] critical — broken in production, data loss, security
- [ ] high     — feature is unusable for some real user flow
- [ ] medium   — degraded UX or hidden bug, easy to repro
- [ ] low      — code smell, papercut, dead code, minor refactor
- [ ] info     — observation only, no fix needed

## Area

<!-- e.g. recording / network / auth / ui-shell -->

## Title

<!-- One line, present tense. "MedASR refinement throws on first tap." -->

## Reproduction / evidence

<!--
Minimal repro or the exact code path that's broken.
File:line refs are MANDATORY — without them, the prompt-author has
nothing to anchor the implementation prompt against.
-->

- File: `mobile/lib/...`
- Lines: `123–145`
- Trigger: <!-- "user taps Refine" -->
- Symptom: <!-- "OfflineRecognizer constructor throws because model file is missing" -->

## Depends on

<!--
Other finding IDs (F0N) that MUST land before this one is
implemented. Empty for most findings — only fill in when the fix
literally requires another finding's diff to already be in the tree
(e.g. the new test you'd write would import a function that doesn't
exist yet, or the bug is hidden behind code another finding removes).

The Phase 2 DAG builder uses this to build the dependency graph and
group findings into parallel execution waves.
-->

- <!-- F02 -->

## Touches files

<!--
The absolute paths the implementation diff is expected to edit.
Best-effort — the impl agent may stray a little, but this is the
DAG builder's input for detecting file-conflict collisions between
findings that have no semantic dependency.

Two findings with overlapping `Touches files` cannot run in parallel
in the same wave even if neither depends on the other.

List the files you actually expect to be edited, not every file you
read while researching. Keep this list under ~5 — if more, the
finding is probably too coarse.
-->

- `mobile/lib/...`

## Root cause hypothesis

<!--
A *hypothesis*, not a guess. Cite the lines that support it. If
unclear, mark "needs debug agent" instead of inventing a cause.
-->

## Fix sketch

<!--
A one-paragraph plan for the implementation agent. NOT the actual
diff — that's the impl agent's job.
-->

## Test sketch

<!--
What test should exist to catch this regression. The test agent will
flesh it out.
-->

## Out-of-scope follow-ups

<!--
Anything you noticed while researching this finding that's
legitimately out of scope. Goes into the deferred backlog.
-->
