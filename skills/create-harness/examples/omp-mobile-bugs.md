# Example (omp) - Finding and fixing bugs in a Flutter recording pipeline

> Companion to `SKILL.omp.md`; the omp counterpart of [mobile-bugs.md](mobile-bugs.md), same scenario, shortened.
> Failure handling for this run is in [omp-failure-recovery.md](omp-failure-recovery.md).
> Schemas used: `findings.schema.json`, `pipeline-verdict.schema.json`, under `skill://create-harness/schemas/`.

The user said: *"Find similar bugs in the voice model. Document an
improvement plan in markdown. Then execute the fixes."*

## Phase 0 - Scope

In plan mode, write the self-contained plan to `local://recording-bugs-plan.md`:

```markdown
# Recording pipeline bugs

## Objective
Find and fix correctness / UX bugs in the mobile recording pipeline
(STT, diarization, MedASR, audio capture).

## Out of scope
- backend/**, UI shell / typography / colour, retraining models

## Definition of done
- `flutter analyze` clean for the recording feature
- each finding's own new or edited test files green
- manual smoke: record + stop produces transcripts with Speaker labels

## Failure budget
- 2 retries per finding

## Preconditions
- task.maxRecursionDepth 2, isolation enabled, async enabled: verified
- all harness-* agents declare their role; harness-pipeline declares its spawns line: verified
- REVIEW_MODE=pr-agent (gh auth, origin remote and LLM key present)
- test runner: flutter test
```

Submit it by writing the slug to `xd://propose`. Nothing else runs until the plan is approved.

## Phase 1 - Research

ONE batched `task` call, three `harness-research` items with non-overlapping scopes. `context` is required:

<!-- schema: none -->
```json
{
  "context": "Approved plan: local://recording-bugs-plan.md. Report findings for your slice only; every finding needs depends_on and touches_files.",
  "tasks": [
    {
      "name": "ResearchA",
      "agent": "harness-research",
      "task": "Number findings F101, F102, ... (your id block; use these ids in depends_on). Scope: mobile/lib/features/recording/data/sherpa/** and recording_provider.dart. Focus: correctness + missing tests.",
      "solutionSpace": "Find root causes with file:line evidence; do not edit anything."
    },
    {
      "name": "ResearchB",
      "agent": "harness-research",
      "task": "Number findings F201, F202, ... (your id block; use these ids in depends_on). Scope: mobile/lib/features/recording/data/transcriber/**. Focus: race conditions + lifecycle bugs.",
      "solutionSpace": "Find root causes with file:line evidence; do not edit anything."
    },
    {
      "name": "ResearchC",
      "agent": "harness-research",
      "task": "Number findings F301, F302, ... (your id block; use these ids in depends_on). Scope: mobile/lib/features/recording/presentation/**. Focus: UX gaps + state-management bugs.",
      "solutionSpace": "Find root causes with file:line evidence; do not edit anything."
    }
  ]
}
```

Each agent finishes by `yield`ing JSON. `ResearchA` yields:

<!-- schema: findings -->
```json
{
  "findings": [
    {
      "id": "F101",
      "severity": "high",
      "area": "recording",
      "title": "MedASR not auto-downloaded on Refine",
      "evidence": [
        {
          "file": "mobile/lib/features/recording/recording_provider.dart",
          "lines": "295",
          "trigger": "Tap Refine before the MedASR model is installed",
          "symptom": "Refine fails with a missing-model error"
        }
      ],
      "depends_on": [],
      "touches_files": [
        "mobile/lib/features/recording/recording_provider.dart",
        "mobile/lib/features/recording/presentation/record_screen.dart"
      ],
      "root_cause": "refine() assumes the model is installed and never calls the download service.",
      "fix_sketch": "Add an ensureInstalled() guard before refine() and surface download progress in the UI.",
      "test_sketch": "Fake the download service; assert refine() triggers one download when the model is absent."
    },
    {
      "id": "F102",
      "severity": "high",
      "area": "recording",
      "title": "Sherpa decode blocks UI on slow CPU",
      "evidence": [
        {
          "file": "mobile/lib/features/recording/data/sherpa/sherpa_streaming_transcriber.dart",
          "lines": "178-190"
        }
      ],
      "depends_on": [],
      "touches_files": [
        "mobile/lib/features/recording/data/sherpa/sherpa_streaming_transcriber.dart"
      ],
      "root_cause": "The decode loop never yields to the event loop between chunks.",
      "fix_sketch": "Yield to the event loop every N chunks.",
      "test_sketch": "Feed a long buffer and assert timers fire during decode.",
      "out_of_scope_followups": ["Move decoding to an isolate"]
    }
  ]
}
```

Never paste findings back into your own context. Extract only the fields you need with a JSON-path read:

```
read agent://ResearchA/findings/0/depends_on
```

A slice that found nothing yields `{"findings": []}`, which is valid.

## Phase 2 - Plan (deterministic)

Run the DAG builder instead of spawning a planner. Each research result is persisted as `<id>.json` next to its `.md`:

```bash
d=$(dirname "$(realpath agent://ResearchA)")
python3 skill://create-harness/scripts/build_pipelines.py \
  --findings-json "$d/ResearchA.json" "$d/ResearchB.json" "$d/ResearchC.json" \
  --format json --output local://pipelines.json
```

The script emits `{title, waves, todo_init}`. Call `todo` with the emitted `todo_init`, copying the strings exactly (lookups are exact matches):

<!-- schema: none -->
```json
{
  "op": "init",
  "list": [
    {
      "phase": "Wave 1",
      "items": [
        "F101 - MedASR not auto-downloaded on Refine",
        "F102 - Sherpa decode blocks UI on slow CPU",
        "F201 - startSession race with first feedAudio"
      ]
    },
    {
      "phase": "Wave 2",
      "items": [
        "F202 - Diarization ignores >60s recordings",
        "F301 - Captured WAV not cleaned up if assign fails"
      ]
    }
  ]
}
```

F202 and F301 land in wave 2 because they share files with F101.

## Phase 3 - Execute, wave 1

**(a) JIT prompts.** ONE batched call of `harness-prompt` items. Each writes `local://prompts/F0N-<slug>.md` and returns the path:

<!-- schema: none -->
```json
{
  "context": "Approved plan: local://recording-bugs-plan.md. Template: skill://create-harness/templates/impl-prompt.md. Every prompt must state verbatim: subagents never run test suites; they run only the test files they created or edited.",
  "tasks": [
    {
      "name": "PromptF101",
      "agent": "harness-prompt",
      "task": "Finding F101 - MedASR not auto-downloaded on Refine. Read it with: read agent://ResearchA/findings/0. Write local://prompts/F101-medasr-on-demand-download.md",
      "solutionSpace": "One finding, one prompt; anchor on the evidence file:line."
    },
    {
      "name": "PromptF102",
      "agent": "harness-prompt",
      "task": "Finding F102 - Sherpa decode blocks UI on slow CPU. Read it with: read agent://ResearchA/findings/1. Write local://prompts/F102-sherpa-decode-yield.md",
      "solutionSpace": "One finding, one prompt; anchor on the evidence file:line."
    },
    {
      "name": "PromptF201",
      "agent": "harness-prompt",
      "task": "Finding F201 - startSession race with first feedAudio. Read it with: read agent://ResearchB/findings/0. Write local://prompts/F201-await-start-session.md",
      "solutionSpace": "One finding, one prompt; anchor on the evidence file:line."
    }
  ]
}
```

**(b) Review channel.** Push the branch and open a draft PR (`gh pr create --draft`).

**(c) Pipelines.** Announce first ("3 runners, about 35-40 min"), then ONE batched call of `harness-pipeline` items, each `isolated: true` so same-wave findings do not race the working tree:

<!-- schema: none -->
```json
{
  "context": "Approved plan: local://recording-bugs-plan.md. Spawn only impl, test and debug children; never write code yourself. Subagents never run test suites; they run only the test files they created or edited.",
  "tasks": [
    {
      "name": "PipelineF101",
      "agent": "harness-pipeline",
      "task": "Run the pipeline for F101 using local://prompts/F101-medasr-on-demand-download.md",
      "solutionSpace": "impl, then debug if needed, then test; yield a pipeline verdict.",
      "isolated": true
    },
    {
      "name": "PipelineF102",
      "agent": "harness-pipeline",
      "task": "Run the pipeline for F102 using local://prompts/F102-sherpa-decode-yield.md",
      "solutionSpace": "impl, then debug if needed, then test; yield a pipeline verdict.",
      "isolated": true
    },
    {
      "name": "PipelineF201",
      "agent": "harness-pipeline",
      "task": "Run the pipeline for F201 using local://prompts/F201-await-start-session.md",
      "solutionSpace": "impl, then debug if needed, then test; yield a pipeline verdict.",
      "isolated": true
    }
  ]
}
```

Then `wait`. When `PipelineF101` finishes it yields:

<!-- schema: pipeline-verdict -->
```json
{
  "finding_id": "F101",
  "status": "DONE",
  "title": "MedASR not auto-downloaded on Refine",
  "files_changed": [
    "mobile/lib/features/recording/recording_provider.dart",
    "mobile/lib/features/recording/presentation/record_screen.dart",
    "mobile/test/recording/recording_provider_test.dart"
  ],
  "tests": { "added": 3, "passed": 3, "total": 3, "result": "pass" },
  "child_agent_ids": {
    "impl": "PipelineF101.ImplF101",
    "test": "PipelineF101.TestF101"
  },
  "warm_retries": 0,
  "spillover": null,
  "blocker": null
}
```

Read verdicts with `read agent://PipelineF101/status` (and `/blocker` when BLOCKED). The `DONE` verdict requires `tests.result` to be `"pass"`; anything else is a contract violation and is treated as BLOCKED.

You own the work list. For a DONE verdict:

<!-- schema: none -->
```json
{ "op": "done", "task": "F101 - MedASR not auto-downloaded on Refine" }
```

For a BLOCKED verdict:

<!-- schema: none -->
```json
{ "op": "block", "task": "F102 - Sherpa decode blocks UI on slow CPU", "reason": "impl cannot fake the decoder; see history://PipelineF102" }
```

**(d) Review gate.** After all runners return, the orchestrator itself spawns `harness-review` once for the wave (never a runner). On PASS, mark the phase done:

<!-- schema: none -->
```json
{ "op": "done", "phase": "Wave 1" }
```

Wave 2 repeats (a) to (d); its prompt authors see wave 1's actual results. A NEEDS_FIX or BLOCKED runner is handled in [omp-failure-recovery.md](omp-failure-recovery.md).

## Phase 4 - Wrap

Render the report from the verdict JSON into `local://report.md`, pass it as the PR body with `gh pr edit --body-file`, mark remaining phases done, `drop` any deferred finding with a one-line reason, and append a `Wrap` phase.
