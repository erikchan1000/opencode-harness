# Harness — Implementation prompt template

> Phase 3a artefact. The prompt-author writes one of these per finding,
> tailored so the implementation subagent can act on it without seeing
> the rest of the harness. Generated just-in-time per wave so prompts
> can incorporate results from prior waves.

## Filename convention

`harness/prompts/F0N-<kebab-slug>.md` — e.g.
`harness/prompts/F01-medasr-on-demand-download.md`.

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

## Verification

<!--
How the impl agent confirms it's done. The unit-test agent runs after
this, but the impl agent should at least sanity-check.
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
3. The orchestrator will attempt a warm retry (resume via task_id)
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
