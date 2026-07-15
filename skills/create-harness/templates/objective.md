# Harness — Objective

> Phase 0 artefact. Fill in before spawning any subagent.

## One-line objective

<!-- "Find and fix correctness / UX bugs in the mobile recording pipeline." -->

## In-scope

- <!-- e.g. mobile/lib/features/recording/** -->
- <!-- e.g. mobile/test/recording/** -->

## Out of scope (mention but don't fix this round)

- <!-- backend, anything network-only -->
- <!-- design-system / typography -->

## Definition of done

- [ ] All `severity: high` findings either fixed or explicitly
      deferred with rationale.
- [ ] Lints / static analysis clean for areas touched.
- [ ] Tests green for areas touched.
- [ ] Manual smoke pass on the relevant runtime (sim, device, browser…).
- [ ] CHANGELOG / ADR entries written per repo conventions.

## Failure budget

- Warm retries per finding (task_id resumption): **1** (default).
- Cold retries per finding (recovery agent): **1** (default).
- Total retry budget per finding: **2** (warm + cold).
- Max parallel research agents: **3** (default).
- Total wall-clock budget for the harness: **<fill in>**.

## Roster

| Role | Subagent type | Notes |
|------|---------------|-------|
| Research | `harness-research` | scoped per-area |
| Prompt author | `harness-prompt` | one invocation per finding, parallel within wave |
| Implementation | `harness-impl` | one invocation per finding |
| Debug | `harness-debug` | only on regressions |
| Unit test | `harness-test` | gate before mark-done |
| Recovery | `harness-recovery` | cold retry only (after warm retry fails) |
