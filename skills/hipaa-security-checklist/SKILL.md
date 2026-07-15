---
name: hipaa-security-checklist
description: This skill should be used when reviewing PHI handling, access controls, and HIPAA-aligned safeguards during feature development.
---

# HIPAA Security Checklist

Use this skill when designing, implementing, or reviewing PHI-sensitive features.

## Objectives
- Keep PHI access scoped, auditable, and minimal.
- Enforce encryption and access controls by default.
- Catch compliance gaps early in development.

## Required Controls
1. Encryption in transit (TLS) and at rest.
2. Role-based access control with least privilege.
3. Audit logging for read/write/export actions touching PHI.
4. PHI minimization in logs and telemetry.
5. Explicit retention and deletion handling.

## Engineering Review Steps
- Verify no secrets or PHI are hard-coded.
- Verify route-level authz checks on all PHI endpoints.
- Verify background jobs and retries preserve access boundaries.
- Verify test fixtures do not contain real PHI.

## Guardrails
- If a required control is missing, block completion and file remediation tasks.
- Prefer deterministic policy checks over ad-hoc manual review.
