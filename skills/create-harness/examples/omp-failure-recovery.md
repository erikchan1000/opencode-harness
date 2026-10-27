# Example (omp) - Failure recovery: warm retry, cold retry, review NEEDS_FIX

> Companion to `SKILL.omp.md` (Phase 3 (d) and (e)); continues [omp-mobile-bugs.md](omp-mobile-bugs.md) at wave 1.
> Schemas used: `pipeline-verdict.schema.json`, `recovery.schema.json`, under `skill://create-harness/schemas/`.

One rule decides everything: pipeline runners are spawned `isolated: true`,
so a failed runner is retried **cold** (a revived isolated runner's second patch
capture after the first merged is unverified, so a fresh runner is safe).
Only non-isolated agents (`harness-prompt`, `harness-research`) are retried
**warm** with `write agent://<id>`.

## 1. Warm retry of a non-isolated agent

`PromptF102` dies instantly with an "API safeguard error" before writing its
file. It is not isolated, so revive it with its full context, then `wait`:

```
write agent://PromptF102
```

with the text: `Your run was interrupted before you wrote anything. Continue and write local://prompts/F102-sherpa-decode-yield.md`.

## 2. Cold retry of an isolated runner

`PipelineF101` yields a BLOCKED verdict:

<!-- schema: pipeline-verdict -->
```json
{
  "finding_id": "F101",
  "status": "BLOCKED",
  "title": "MedASR not auto-downloaded on Refine",
  "files_changed": [],
  "tests": { "added": 0, "passed": 0, "total": 0, "result": "not_run" },
  "child_agent_ids": { "impl": "PipelineF101.ImplF101" },
  "warm_retries": 0,
  "spillover": null,
  "blocker": {
    "gate": "impl",
    "reason": "ModelDownloadService is not injectable, so the download path cannot be faked",
    "next_step": "cold_retry"
  }
}
```

Mark it blocked on the work list and inspect what happened:

<!-- schema: none -->
```json
{ "op": "block", "task": "F101 - MedASR not auto-downloaded on Refine", "reason": "impl blocked: ModelDownloadService not injectable" }
```

```
read agent://PipelineF101/blocker
read history://PipelineF101
read history://PipelineF101.ImplF101
```

Do not `write agent://PipelineF101`: the runner was spawned isolated and is
retried cold. Spawn `harness-recovery` with a task text that names the
failed id and the transcript to read:

<!-- schema: none -->
```json
{
  "context": "Approved plan: local://recording-bugs-plan.md. Retry budget per finding: 2.",
  "tasks": [
    {
      "name": "RecoveryF101",
      "agent": "harness-recovery",
      "task": "Finding F101 failed. Failed agent id: PipelineF101. Read history://PipelineF101 and history://PipelineF101.ImplF101, diagnose the failure mode, and write a narrower prompt to local://prompts/F101.recovery-1.md.",
      "solutionSpace": "Smaller scope and explicit ordering; do not edit code."
    }
  ]
}
```

`RecoveryF101` yields:

<!-- schema: recovery -->
```json
{
  "finding_id": "F101",
  "attempt": 1,
  "diagnosis": {
    "failure_mode": "timeout_token_limit",
    "summary": "Scope too big: the impl tried to wire the download and refactor the service in one pass, and stopped at line 295 unable to mock the service."
  },
  "revised_prompt_path": "local://prompts/F101.recovery-1.md",
  "changes": [
    "First add a constructor parameter for the download service so it can be faked",
    "Only then wire ensureInstalled() into refine()"
  ],
  "budget_remaining": 1
}
```

Respawn a fresh isolated runner with a new name on the revised prompt:

<!-- schema: none -->
```json
{
  "context": "Approved plan: local://recording-bugs-plan.md. Spawn only impl, test and debug children; never write code yourself. Subagents never run test suites; they run only the test files they created or edited.",
  "tasks": [
    {
      "name": "PipelineF101-r1",
      "agent": "harness-pipeline",
      "task": "Run the pipeline for F101 using local://prompts/F101.recovery-1.md",
      "solutionSpace": "impl, then debug if needed, then test; yield a pipeline verdict.",
      "isolated": true
    }
  ]
}
```

### Genuinely blocked

If the diagnosis is `genuinely_blocked`, `revised_prompt_path` is `null`.
Do not respawn: escalate to the human, `drop` the finding, and defer its
dependents (wave 2's F202 and F301 share files with F101).

<!-- schema: recovery -->
```json
{
  "finding_id": "F101",
  "attempt": 1,
  "diagnosis": {
    "failure_mode": "genuinely_blocked",
    "summary": "The download endpoint is not provisioned in this environment; no prompt change can fix that."
  },
  "revised_prompt_path": null,
  "changes": [],
  "budget_remaining": 1
}
```

<!-- schema: none -->
```json
{ "op": "drop", "task": "F101 - MedASR not auto-downloaded on Refine", "reason": "genuinely blocked: download endpoint not provisioned; needs human" }
```

## 3. Wave review returns NEEDS_FIX

After every runner returned, the orchestrator spawned `harness-review` for
the wave. It yields a verdict with a blocking item against F101:

<!-- schema: review-verdict -->
```json
{
  "verdict": "NEEDS_FIX",
  "items": [
    {
      "finding_id": "F101",
      "severity": "high",
      "category": "correctness",
      "file": "mobile/lib/features/recording/recording_provider.dart",
      "line": 301,
      "problem": "ensureInstalled() is awaited without handling a failed download; refine() proceeds with no model",
      "fix": "Return early and surface the error when ensureInstalled() throws",
      "blocking": true
    },
    {
      "finding_id": "F102",
      "severity": "low",
      "category": "style",
      "file": "mobile/lib/features/recording/data/sherpa/sherpa_streaming_transcriber.dart",
      "line": null,
      "problem": "Magic number for the yield interval",
      "fix": "Name the constant",
      "blocking": false
    }
  ],
  "blocker": null
}
```

Only blocking items are retried; the advisory F102 item goes in the report.
`PipelineF101` was an isolated runner, so it is **not** revived with
`write agent://PipelineF101`. There is no failure to diagnose, so skip
`harness-recovery` and spawn a fresh isolated runner whose task text carries
the review item:

<!-- schema: none -->
```json
{
  "context": "Approved plan: local://recording-bugs-plan.md. Spawn only impl, test and debug children; never write code yourself. Subagents never run test suites; they run only the test files they created or edited.",
  "tasks": [
    {
      "name": "PipelineF101-r2",
      "agent": "harness-pipeline",
      "task": "Re-run the pipeline for F101 using local://prompts/F101-medasr-on-demand-download.md. Fix this blocking review item: recording_provider.dart:301 - ensureInstalled() is awaited without handling a failed download; return early and surface the error when it throws. Add a test for the failure path.",
      "solutionSpace": "Minimal change that resolves the review item; yield a pipeline verdict.",
      "isolated": true
    }
  ]
}
```

Re-run the review gate once the new verdict is DONE. If a finding is still
blocked once its budget is spent, defer it and its dependents with `drop`
and a one-line reason.
