# Example — Finding and fixing perf regressions in a REST backend

> Second worked example. Demonstrates that the same harness structure
> handles a different domain (server-side perf) by tweaking only the
> role focuses, not the methodology.

## Phase 0 — Scope

```markdown
# plan/objective.md

## One-line objective
Identify P99 latency regressions in the Fastify backend's hot
endpoints and fix the highest-impact ones.

## In-scope
- backend/src/routes/**
- backend/src/db/**
- backend/src/lib/**

## Out of scope
- mobile/** (clients aren't the bottleneck this round)
- infra/** (no Cloud Run / GCP changes)

## Definition of done
- [ ] At least 3 high-severity findings resolved.
- [ ] `npm run test` green.
- [ ] Bench script (`scripts/bench.sh`) shows P99 improvement on
      changed endpoints.
- [ ] CHANGELOG + ADR entries for any architectural changes.

## Failure budget
- Warm retries per finding: 1
- Cold retries per finding: 1
- Parallel research agents: 3
- Wall-clock budget: 4 hours
```

## Phase 1 — Research focuses

The three research subagents run with **perf-shaped** focuses via the
Task tool:

```
Task(subagent_type: "harness-research",
     prompt: "Scope: backend/src/routes/**
              Focus: N+1 queries, missing pagination, fan-out
              ...")

Task(subagent_type: "harness-research",
     prompt: "Scope: backend/src/db/**
              Focus: missing indexes, hot Drizzle relations
              ...")

Task(subagent_type: "harness-research",
     prompt: "Scope: backend/src/lib/**
              Focus: JSON serialisation, large payload paths
              ...")
```

Severity rubric is rewritten for perf:
- `critical`: endpoint timing out under normal load
- `high`: > 500 ms P99 for a hot endpoint
- `medium`: > 100 ms P99 for any endpoint
- `low`: code smell with no measurable impact

## Phase 2 — Plan (deterministic)

Same `build_pipelines.py` script, no changes:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/build_pipelines.py" \
  --findings plan/findings.md \
  --output   plan/pipelines.md \
  --title    "Backend P99 latency regressions"
```

## Phase 3 — Execute (JIT prompts)

Same loop. Two differences from the mobile example:

1. **JIT prompts include bench commands**: each prompt's `Verification`
   section now includes a bench command:

   ```markdown
   ## Verification
   - [ ] `npm run test` clean
   - [ ] `scripts/bench.sh GET /v1/encounters` P99 < 200 ms
   - [ ] Drizzle query logs show one query per request, not N+1
   ```

2. **`harness-test` writes bench tests**: the test agent produces
   **bench tests** as well as unit tests, so the perf gate is
   machine-checkable.

## Phase 4 — Wrap

Aggregate, write a perf summary to `plan/report.md`, link to each
ADR.

## Takeaway

Same six roles, same five phases, same templates, same
`build_pipelines.py` — just different focuses and verification
commands. That is the whole point of the methodology being
task-shaped, not domain-shaped.
