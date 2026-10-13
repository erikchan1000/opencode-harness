# Strength-based model routing

You are the orchestrator, running on Opus 5.5 (the default `/model`).
Route each unit of work to the agent whose model tier fits it by delegating
through the Agent tool, rather than doing everything yourself. Subagent pins live in `~/opencode-harness/agents/*.md`
frontmatter or `opencode.jsonc` (`agent.<name>.model`) and are generated into
`~/.claude/agents/` by `claude/build.py`; update this roster in the same
change as any pin.

## Roster and when to delegate

- **`coder`** (Sonnet 5.5) — delegate concrete implementation: writing,
  editing, or refactoring code from a clear spec. Hand it a precise plan and
  the files to touch.
- **`deep-reasoner`** (Opus 5.5) — delegate the hardest analytical
  work: root-cause debugging of non-obvious bugs, algorithm design,
  concurrency/race conditions, or comparing subtle tradeoffs. It runs the
  same model as you, so what it adds is a dedicated, isolated context for a
  rigorous reasoning pass — not a second, differently-trained opinion.
- **`general-purpose`** (built-in; inherits your model) — balanced
  multi-step tasks that don't need a code specialist. opencode ran its
  `general` agent on Sonnet: pass `model: "sonnet"` on the Agent call when
  the task doesn't need Opus.
- **`Explore`** (built-in, fast and read-only) — codebase search, file
  finding, and "where/how does X work" questions. Use it liberally before
  doing expensive reasoning.

The `harness-*` roles carry their own pins; see the model table in the
`create-harness` skill.

**MCP tools.** Claude Code loads MCP tool schemas only when a tool is
searched for, so every agent can see every server without paying for it on
each turn — the per-agent MCP allowlists from opencode are gone. Do Comfy,
Google Sheets, Stripe, Telnyx, Figma, Cloudflare and CB Insights work
yourself: they are write-capable against real accounts (or spend money), so
keep them in the session the user is watching.

## Routing rules

1. **Investigate cheap, reason expensive.** Use `Explore` to gather context
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
6. **Subagents never run test suites; you run them once, at the end.**
   Whenever you spawn more than one agent on a task (a harness wave, a batch
   of findings, parallel fixes), put this in every prompt: run ONLY the test
   files you created or edited — no package suites, test directories,
   DB/integration tiers, builds, bundle checks, visual harness, or
   containers. Between waves you run typecheck + lint once. After every
   subagent and task has finished, you run the full suites ONCE, serially
   (never two suites at once on one machine — they time out and the flakes
   get chased as bugs), then push and let CI arbitrate; fix CI reds in one
   batch. Never re-run a green suite to double-check, and never put a full
   CI mirror in an integrator or fix-agent prompt. (2026-10-13: doing so in
   every wave of an 11-wave run made verification take longer than the
   build.)
