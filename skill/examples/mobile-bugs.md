# Example — Finding and fixing bugs in a Flutter recording pipeline

> The canonical example this skill was written for. The user said:
> *"Find similar bugs in the voice model. Document an improvement plan
> in markdown. Then execute the fixes."*

## Phase 0 — Scope

```markdown
# harness/objective.md

## One-line objective
Find and fix correctness / UX bugs in the mobile recording pipeline
(STT, diarization, MedASR, audio capture).

## In-scope
- mobile/lib/features/recording/**
- mobile/lib/core/platform/**
- mobile/test/recording/**

## Out of scope
- backend/**
- mobile UI shell / typography / colour
- model files themselves (we don't retrain)

## Definition of done
- [ ] All `severity: high` findings fixed or deferred with rationale.
- [ ] `flutter analyze` clean for the recording feature.
- [ ] `flutter test test/recording/` green.
- [ ] Manual smoke on iPad Air M4 sim: record + stop produces
      transcripts with Speaker labels; MedASR refine works first try.
- [ ] CHANGELOG entries + ADRs per AGENTS.md.

## Failure budget
- Warm retries per finding: 1
- Cold retries per finding: 1
- Parallel research agents: 3
- Wall-clock budget: 2 hours
```

## Phase 1 — Research

Spawn three research subagents in parallel using the Task tool, each
scoped to a slice:

```
Task(subagent_type: "harness-research",
     prompt: "Scope: mobile/lib/features/recording/data/sherpa/**
              Focus: correctness + missing tests
              ...")

Task(subagent_type: "harness-research",
     prompt: "Scope: mobile/lib/features/recording/data/transcriber/**
              Focus: race conditions + lifecycle bugs
              ...")

Task(subagent_type: "harness-research",
     prompt: "Scope: mobile/lib/features/recording/presentation/**
              Focus: UX gaps + state-management bugs
              ...")
```

After all three return, merge into `harness/findings.md`:

```markdown
| ID  | Severity | Area      | Title                                  | File:Line                              | Depends on | Touches files                                                  |
|-----|----------|-----------|----------------------------------------|----------------------------------------|------------|----------------------------------------------------------------|
| F01 | high     | recording | MedASR not auto-downloaded on Refine   | recording_provider.dart:295            | —          | recording_provider.dart, record_screen.dart                    |
| F02 | high     | recording | Sherpa decode blocks UI on slow CPU    | sherpa_streaming_transcriber.dart:178  | —          | sherpa_streaming_transcriber.dart                              |
| F03 | medium   | recording | startSession race with first feedAudio | apple_speech_transcriber.dart:110      | —          | apple_speech_transcriber.dart                                  |
| F04 | medium   | recording | Diarization ignores >60s recordings    | diarization_service.dart:48            | —          | diarization_service.dart, recording_provider.dart              |
| F05 | low      | recording | Captured WAV not GC'd if assign fails  | record_screen.dart:213                 | —          | record_screen.dart                                             |
```

## Phase 2 — Plan (deterministic)

Run `build_pipelines.py` instead of spawning a planner agent:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/build_pipelines.py" \
  --findings harness/findings.md \
  --output   harness/pipelines.md \
  --title    "Mobile recording pipeline bugs"
```

Output:

```
Parsed 5 findings
Wrote harness/pipelines.md
  Waves: 2, Max parallelism: 3
  Wave 1: F01, F02, F03
  Wave 2: F04, F05
```

The script detects that:

- F01, F04 both touch `recording_provider.dart` → file conflict
- F01, F05 both touch `record_screen.dart` → file conflict
- F02 only touches `sherpa_streaming_transcriber.dart` → independent
- F03 only touches `apple_speech_transcriber.dart` → independent

Resulting wave plan (generated, not hand-written):

```markdown
## Wave 1 (parallel — 3 findings)
- F01 — MedASR on-demand download    [recording_provider.dart, record_screen.dart]
- F02 — Sherpa decode yield          [sherpa_streaming_transcriber.dart]
- F03 — Await startSession           [apple_speech_transcriber.dart]

## Wave 2 (parallel — 2 findings)
- F04 — Diarization fullbuffer       [diarization_service.dart, recording_provider.dart]
        ⚠ shares recording_provider.dart with F01; deferred to avoid file-conflict race
- F05 — WAV cleanup on assign fail   [record_screen.dart]
        ⚠ shares record_screen.dart with F01; deferred to avoid file-conflict race
```

## Phase 3 — Execute (wave-by-wave, JIT prompts + parallel pipelines)

**Wave 1 — Step 3a (prompts, parallel):**

Spawn three prompt-authors in parallel, one per finding:

```
Task(subagent_type: "harness-prompt",
     prompt: "Finding: F01 — MedASR not auto-downloaded on Refine
              <full finding details>
              Template: ${CLAUDE_SKILL_DIR}/templates/impl-prompt.md
              Output: harness/prompts/F01-medasr-on-demand-download.md")

Task(subagent_type: "harness-prompt", prompt: "Finding: F02 ...")
Task(subagent_type: "harness-prompt", prompt: "Finding: F03 ...")
```

**Wave 1 — Step 3b (finding pipelines, parallel):**

```
parallel:
  pipeline F01: impl(F01) → debug-if-needed(F01) → test(F01)
  pipeline F02: impl(F02) → debug-if-needed(F02) → test(F02)
  pipeline F03: impl(F03) → debug-if-needed(F03) → test(F03)
barrier: wait for all three to reach DONE/BLOCKED
```

**Wave 2 — Step 3a (prompts with prior wave context):**

Now that Wave 1 is done, prompts for Wave 2 incorporate what changed:

```
Task(subagent_type: "harness-prompt",
     prompt: "Finding: F04 — Diarization ignores >60s recordings
              <full finding details>
              Prior wave context: F01 added an ensureInstalled() guard at
              recording_provider.dart:295 and a download progress UI at
              record_screen.dart:120.
              Template: ${CLAUDE_SKILL_DIR}/templates/impl-prompt.md
              Output: harness/prompts/F04-diarization-fullbuffer.md")
```

This is the JIT advantage — F04's prompt knows exactly what F01 changed
in `recording_provider.dart`, so the impl agent won't conflict.

**Wave 2 — Step 3b:**

```
parallel:
  pipeline F04: impl(F04) → test(F04)
  pipeline F05: impl(F05) → test(F05)
barrier
```

### Failure recovery example

If F01 had failed:

1. `harness-impl(F01)` returns `BLOCKED: ModelDownloadService isn't
   injectable`.
2. **Warm retry**: resume the same agent via task_id with guidance:
   "Your scratchpad shows you identified the issue at line 295 but
   couldn't mock the service. Try adding a constructor parameter for
   the service so it can be faked, THEN do the wiring."
3. If warm retry also fails — **cold retry**: invoke
   `harness-recovery` which reads both scratchpads, diagnoses failure
   mode 1 (scope too big), and writes
   `prompts/F01.recovery-1.md` that says "first add a constructor
   parameter for the service, THEN do the wiring" with narrower scope.
4. Spawn a fresh `harness-impl` with the recovery prompt.
5. If F01 exhausts its recovery budget, the orchestrator marks F01
   BLOCKED, automatically defers Wave 2's F04 (shares a file), and
   proceeds with Wave 2's F05.

## Phase 4 — Wrap

Aggregate completion logs, update CHANGELOG and ADRs per repo
conventions, surface a one-page report to the user.

## Takeaway

Without the wave plan, the orchestrator would have run all 5 findings
serially (~5x impl-agent runs sequentially). With it, Wave 1 ships 3
findings concurrently, then Wave 2 ships 2 more concurrently — roughly
2x wall-clock speedup. JIT prompt generation means Wave 2 prompts
account for Wave 1's actual diffs, not just hypotheses.
