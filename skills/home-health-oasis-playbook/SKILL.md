---
name: home-health-oasis-playbook
description: This skill should be used when implementing or reviewing OASIS, M1800, and GG charting logic for home health AI scribe workflows.
---

# Home Health OASIS Playbook

Use this skill when implementing or reviewing home health charting flows tied to OASIS items, M1800, and GG support.

## Objectives
- Keep charting outputs structured, evidence-backed, and clinician-reviewable.
- Ensure low-confidence item handling is explicit and safe.
- Preserve traceability from generated chart sections to transcript evidence.

## Workflow
1. Confirm required OASIS sections for the current feature scope.
2. Define deterministic validation checks before final sign-off.
3. Ensure every suggested M1800/GG value has a source evidence reference.
4. Require manual clinician confirmation for low-confidence values.

## Implementation Checklist
- Include confidence scores for extracted/suggested items.
- Include required-field checks in both API and UI layers.
- Keep unsupported/unknown values explicit (never silently infer final values).
- Maintain edit history for clinician overrides.

## Guardrails
- Never auto-submit OASIS output without clinician sign-off.
- Never hide uncertainty in generated documentation.
