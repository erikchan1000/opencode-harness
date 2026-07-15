---
name: fhir-ehr-mapping-playbook
description: This skill should be used when designing or validating canonical-to-FHIR and vendor EHR mapping/sync logic.
---

# FHIR EHR Mapping Playbook

Use this skill when building EHR sync and FHIR mapping features.

## Objectives
- Keep canonical internal models separate from vendor-specific payloads.
- Ensure idempotent, observable sync operations.
- Reduce connector drift through explicit mapping contracts.

## Workflow
1. Define canonical payload schema for the feature.
2. Map canonical fields to FHIR resources first.
3. Map FHIR/canonical payload to vendor API shape via adapter layer.
4. Add retry/backoff, conflict detection, and reconciliation behavior.

## Required Outputs
- Mapping table: canonical -> FHIR -> vendor field.
- Error taxonomy for sync failures.
- Idempotency key strategy and correlation IDs.
- Test cases for partial failure and retry behavior.

## Guardrails
- Never write directly to vendor payloads from UI-specific structures.
- Always preserve sync status and failure visibility for clinician operations.
