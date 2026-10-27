# Harness — Implementation prompt template

> Phase 3a artefact. The prompt-author writes one of these per finding,
> tailored so the implementation subagent can act on it without seeing
> the rest of the harness. Generated just-in-time per wave so prompts
> can incorporate results from prior waves.

## Filename convention

`plan/prompts/F0N-<kebab-slug>.md` — e.g.
`plan/prompts/F01-medasr-on-demand-download.md`.

## Required sections

```markdown
# F0N — <title>

## Context

<!--
Self-contained summary. The impl agent will NOT see findings.md or
the other findings. Include:
  - Repo: which one (path, branch)
  - Area: which feature / file
  - User-visible symptom: what the user reports
  - Why this matters: business / safety justification (HIPAA, etc.)
-->

## Prior wave context

<!--
ONLY present for findings in Wave 2+. Summarise what earlier
findings changed that this finding should account for. Include
the actual file:line changes, not just the finding titles.
Omit this section entirely for Wave 1 findings.
-->

## Files in play

<!--
Full paths, not relative. Each file gets a one-line "what to look at"
note. Keep this list under 5 — if more, the finding was too coarse
and should be split.
-->

- `<absolute/path/to/file.dart>` — <one line about what to look for>

## Required change

<!--
Imperative. The impl agent should be able to copy/paste these as a
todo list. No prose — bullets.
-->

- [ ] <exact change 1>
- [ ] <exact change 2>

## Constraints

<!--
Non-negotiables. List the rules the agent must NOT break.
-->

- Do not change public APIs without a deprecation note.
- Do not introduce new dependencies; use what's in pubspec.yaml.
- Comments must follow `<repo conventions document>`.

<!--
Domain checklists — INCLUDE the matching block whenever the finding touches
that domain. These are the bug classes the review gate keeps catching after
impl+test have both passed (5× in one run, 2026-09-09); putting them here is
~45 min cheaper than finding them in review.
-->

<!-- If the change acquires a resource (MediaStream/MediaRecorder, file
handle, socket, subscription, timer, lock): -->
- Every exit path releases the resource: success, user cancel, error
  callback, component unmount, AND unmount/cancel while the acquisition
  is still pending (the late-resolving promise must release what it just
  got and return without touching state).
- The acquire entry point is guarded by state: a second call while
  acquiring/active must throw or no-op, never acquire a second instance.
- Tests assert the release (spy on `track.stop()` / `close()` /
  `unsubscribe()`), not just the state label.

<!-- If the change has an async transition driven by a user control
(stop/submit/save/confirm): -->
- The control that triggers the transition is disabled (and re-labelled)
  from the moment it fires until the transition settles; a second click
  during the in-flight window cannot re-enter and cannot discard the
  result of the first.
- A rejection arriving after a result was already stored does not clear
  the stored result.

<!-- If the change adds or edits an accessible control (Flutter
`Semantics`, ARIA role="button"): -->
- The node exposes its action (`onTap:` / real click handler), reports
  `enabled` consistently with the visual disabled state, and — if
  `excludeSemantics`/`aria-hidden` is used on children — carries the full
  label itself. Tests assert `hasTapAction` / the role's action.

## Verification

<!--
How the impl agent confirms it's done. Keep it NARROW: the single new
test file and static analysis. The test agent runs the area directory once;
the orchestrator runs the full suite once per wave. Do not list the full
project suite here.
-->

- [ ] `flutter analyze` clean for `<scope>`
- [ ] Manually run `<command>` and confirm `<output>`
- [ ] `flutter test test/<file>_test.dart` passes

## Out-of-scope (do NOT touch)

<!--
List the temptations. The impl agent will see related code and want
to "while I'm here" fix it. This section blocks scope creep.
-->

- Don't refactor `<file>` even though it's nearby.
- Don't fix `<adjacent finding ID>` — that's a separate prompt.

## On failure / timeout

If the impl agent can't complete this in one pass, it should:

1. Save its progress to a `HARNESS-WIP` comment in the file it was editing.
2. Return a one-paragraph summary of what it did, what's left, and
   what blocked it.
3. The orchestrator will attempt a warm retry (resume the same agent; opencode: `task_id`, Claude Code: `SendMessage` to the agent id, omp: `write agent://<id>`)
   first, then route to the recovery agent if warm retry fails.
```

## Authoring tips for the prompt-author subagent

- **One finding, one prompt.** Don't bundle.
- **Less is more in "Required change".** If you find yourself writing
  5+ bullets, the finding was too coarse — flag it back to the
  orchestrator to split.
- **Cite file:line in `Files in play` always.** The impl agent's
  context window is limited; line numbers save it from re-reading.
- **Keep "Constraints" to ~3 bullets.** More than that and the agent
  starts ignoring them.
- **Include "Prior wave context" for Wave 2+ findings.** The impl
  agent needs to know what changed before it starts.
