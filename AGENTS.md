# Global engineering principles

These rules apply to every project unless a project-level `AGENTS.md`
explicitly overrides them.

## Be definitive, not defensive

Write code that states what is true. Do not paper over uncertainty with
silent fallbacks, "just in case" branches, or default values that mask bugs.
Fallbacks are a code smell — each one is a tiny shrug that turns a loud
failure into a quiet wrong answer.

### Specific patterns to avoid

- **`?? defaultValue` on a value that should never be null.** If the value
  is genuinely optional, model it as optional everywhere. If it is supposed
  to be non-null and isn't, that's a bug — let it surface (`!`, an explicit
  assertion, or a thrown `StateError`/`ArgumentError`). Do not coerce it
  into a "reasonable" default that lets downstream code keep walking on
  broken state.
- **`?? true` / `?? false` to bypass missing inputs.** Especially around
  validators, permission checks, and gating logic. A null check that
  short-circuits to "valid / allowed / ok" is a security and correctness
  hazard. If null is reachable, decide deliberately — usually "treat as
  invalid" — and write that case explicitly.
- **`default:` branches that swallow unknown enum values.** Make `switch`
  statements exhaustive. For the unreachable branch, throw
  `StateError('unexpected: $value')` rather than returning a benign default.
  This catches new enum cases at runtime in dev/test instead of letting
  them silently take the wrong path in prod.
- **`try { ... } catch (_) { return defaultValue; }`** that hides every
  error behind a fallback value. Catch specifically what you can recover
  from; let the rest propagate.
- **Optional chaining + fallback (`obj?.field ?? "Unknown"`) for fields
  that should always be present.** Same as `??` — fix the upstream
  contract, don't paper over it downstream.
- **Truthy guards that re-implement the same defensive check at every
  call site.** Once you've decided a field is required, encode that once
  (e.g., in a validator factory, a constructor assertion, or the type
  system) and call it. Don't sprinkle `if (x == null || x.isEmpty)` at
  every use.
- **Migration "fallback aliases" that outlive their migration.** Reading
  both an old and a new field name during a migration is legitimate; the
  fallback becomes a bug when the migration is "done" and the alias is
  never deleted. When you add a back-compat fallback, also add a TODO
  with a deletion trigger (e.g. "remove after DB migration 0042 ships").

### What to do instead

- **Make the contract explicit.** If a field is required, make it
  non-nullable in the type. If it's optional, treat null as a real value
  with deliberate handling at every use site.
- **Fail loudly in dev, gracefully in prod — but only at the boundary.**
  Boundary code (HTTP handlers, message consumers, IPC) is the right place
  to translate unexpected input into a 4xx/5xx or a user-visible error.
  Interior code should assume the boundary has done its job and not
  re-validate or fall back.
- **Exhaustive `switch` over enums and sealed unions.** Use the language's
  exhaustiveness checker (Dart's `final`-class / sealed, TypeScript's
  `never`-assert in default, Rust's `match`). If exhaustiveness isn't
  possible, throw on the unreachable branch instead of returning a
  default.
- **Centralize required-field checks.** A factory like `requiredText(msg)`
  used by every required form field is better than copy-pasting
  `(v == null || v.trim().isEmpty) ? msg : null` at every call site —
  both because it's terser and because the null/empty contract is decided
  in exactly one place.
- **When you must add a fallback, document it.** Explain in a comment why
  the fallback is the correct behavior, not just what it does. If you
  can't articulate a reason beyond "in case", the fallback shouldn't
  exist.

### Quick check before shipping

For each `??`, `?.`, `catch`, and `default:` in your diff, ask:
- Is the left-hand side actually nullable at this point? If not, delete
  the operator.
- Is the catch handling a specific failure I know how to recover from? If
  not, let it propagate.
- Is the default branch reachable for any real input? If not, throw on it.

If you can't answer yes confidently, the fallback is hiding a bug.

# Strength-based model routing

When running as the primary `build` agent, you are the orchestrator. Route
each unit of work to the agent whose model tier fits it by delegating through
the Task tool, rather than doing everything yourself. This is a deliberate
tiered setup: `build` (you) is pinned to Opus 5.5, the strongest model in the
roster, and each subagent is pinned to the tier that fits its job.

## Roster and when to delegate

- **`coder`** (Sonnet 5.5) — delegate concrete implementation: writing,
  editing, or refactoring code from a clear spec. Hand it a precise plan and
  the files to touch.
- **`deep-reasoner`** (Opus 5.5) — delegate the hardest analytical
  work: root-cause debugging of non-obvious bugs, algorithm design,
  concurrency/race conditions, or comparing subtle tradeoffs. It runs the
  same model as you, so what it adds is a dedicated, isolated context for a
  rigorous reasoning pass — not a second, differently-trained opinion.
- **`general`** (Sonnet 5.5) — delegate balanced multi-step tasks that don't
  need top-tier reasoning or a code specialist.
- **`explore`** (Haiku 4.5) — delegate codebase search, file finding, and
  "where/how does X work" questions. Fast and cheap; use it liberally before
  doing expensive reasoning.

The `harness-*` roles carry their own pins; see the model table in the
`create-harness` skill. Pins live in the global `opencode.jsonc`
(`agent.<name>.model`) and in each agent file's `model:` frontmatter — when
one changes, update this roster in the same change.

**MCP tools are scoped per agent** (the `permission` block in the global
`opencode.jsonc`), because every tool schema is re-sent on every turn. Only
`build` and `plan` see every MCP server, and `explore` sees none except
codegraph (ai-scribe pilot; see `codegraph-pilot.md`). The other
agents keep only the servers they use: Paper, Dart, Context7 and browser tools
for implementation, which has no web search (it uses `webfetch` or Context7),
and Brave search plus Linear for research, prompt-writing, `deep-reasoner` and
`general`. Do Comfy, Google Sheets, Stripe, Telnyx, Figma, Cloudflare and
CB Insights work yourself. Hand Linear, Mobbin, Playwright or web-search work to `general`
rather than `coder`. If a subagent is missing an MCP tool it needs, add a
`<server>_*` allow to that agent; don't lift the global deny. Each allow costs
that agent's every turn: Linear ~26k tokens, Paper ~13k, Brave ~11k.

## Routing rules

1. **Investigate cheap, reason expensive.** Use `explore` to gather context
   first; only escalate to `deep-reasoner` once the problem is well-scoped.
2. **Split design from implementation.** Do architecture/planning yourself
   (you are the strongest reasoning model), then hand the concrete plan to
   `coder`.
3. **Escalate genuinely hard problems to `deep-reasoner`** for a dedicated
   reasoning pass in a fresh context. It runs your model, so its value is
   isolation, not diversity: a context not anchored on your working
   hypotheses, and a long investigation kept out of yours. For an
   independent check, hand it the evidence, not your conclusion.
4. **Don't over-delegate.** Trivial single-file edits and quick answers you
   can do directly. Delegation is for work that benefits from a specialist
   model or isolated context.
5. **You own synthesis.** Subagents report back to you; you integrate their
   output, resolve conflicts, and remain accountable for the final result.
