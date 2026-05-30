## PR Review

### Score: 3/5

### Findings

| # | Category | File | Problem | Suggestion | Severity |
|---|----------|------|---------|------------|----------|
| 1 | Security | src/auth/middleware.ts:42 | User token is not validated before accessing claims. JWT payload is trusted without signature verification. | Add `jwt.verify(token, secret)` before accessing `token.claims`. Use the existing `verifyToken` helper from `src/lib/auth.ts`. | Critical |
| 2 | Bug | src/routes/users.ts:87 | `findUser` can return `null` but the result is accessed without a guard, causing `TypeError: Cannot read property 'email' of null`. | Add a null check: `if (!user) return reply.code(404).send({ error: 'User not found' })`. | Major |
| 3 | Performance | src/db/queries.ts:23 | N+1 query inside a loop: each iteration calls `getVisitNotes(patientId)`. With 100 patients, this generates 101 SQL queries. | Batch the query outside the loop: `const notesMap = await getVisitNotesForPatients(patientIds)`. | Medium |
| 4 | Style | src/utils/format.ts:15 | Function `fmt` is not descriptive. Naming convention in this repo uses full words (see `formatDate`, `formatCurrency`). | Rename to `formatPhoneNumber` to match existing conventions. | Minor |
| 5 | Documentation | src/routes/visits.ts:1 | New endpoint `/visits/:id/notes` has no JSDoc comment. All other route handlers in this file have documentation. | Add JSDoc with `@param`, `@returns`, and `@throws` annotations. | Low |

### Tests Review

Missing tests for the new `/visits/:id/notes` endpoint. Existing test patterns in `src/__tests__/` show each route handler has a corresponding test file.

### Security Review

**Critical:** The JWT validation bypass in `middleware.ts:42` is a security vulnerability. Any client can forge a token with arbitrary claims. This must be fixed before merge.

### Effort to Review: 3/5
