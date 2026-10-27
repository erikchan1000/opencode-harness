---
name: skillsmp-discovery
description: This skill should be used when the user asks to find, browse, compare, or install community skills from SkillsMP (skillsmp.com), or when a needed skill may already exist in a public marketplace.
license: MIT
---

# SkillsMP Discovery

Use this skill to discover and install community skills from SkillsMP into the agent harness in use (opencode, Claude Code or omp).

## When to use

- The user asks for a capability that might already exist as a public skill.
- The user asks to search SkillsMP by topic or use case.
- The user asks to install a community skill into the harness in use.

## Search workflow

`<skill-dir>` below is the absolute path of the directory containing this
`SKILL.md` (it holds `scripts/`). Take it from the skill header given when
the skill loaded: Claude Code, "Base directory for this skill"; omp, the
`[Skill directory: ...]` line (or `skill://skillsmp-discovery`, which is the
skill directory in bash); opencode, the parent directory of the loaded
`SKILL.md`. Substitute that absolute path wherever `<skill-dir>` appears in
a command.

1. Search SkillsMP with:

```bash
python "<skill-dir>/scripts/skillsmp_search.py" --query "$ARGUMENTS"
```

2. If `SKILL_MAP_API_KEY` is set, the script uses SkillsMP API endpoints.
3. If no API key is set (or API lookup fails), the script falls back to parsing SkillsMP search results via `r.jina.ai`.
4. Present top matches with repo, skill name, and short description.

## Install workflow

After the user chooses a result, install it with:

```bash
python "<skill-dir>/scripts/skillsmp_install.py" --repo "owner/repo" --skill-name "skill-name"
```

Useful flags:

- `--dry-run` to preview what would be installed.
- `--overwrite` to replace an existing local copy.
- `--target-dir` to install to a non-default skills directory.

## Verify installation

- opencode: run `opencode debug skill` and confirm the skill appears in the discovered list.
- Claude Code: confirm `~/.claude/skills/<name>/SKILL.md` exists after `install.sh --claude`.
- omp: run `ls "${PI_CODING_AGENT_DIR:-$HOME/.omp/agent}/skills/<name>/SKILL.md"`.

## Notes

- Install location depends on the harness:
  - opencode: the default `--target-dir` (`~/.config/opencode/skills`).
  - Claude Code: the same default dir, then run `~/opencode-harness/install.sh --claude`; it links the skill into `~/.claude/skills`.
  - omp: pass `--target-dir "${PI_CODING_AGENT_DIR:-$HOME/.omp/agent}/skills"` to install natively. `install.sh --omp` does not pick up skills from the opencode dir.
- Review third-party skill content before relying on it.
- If multiple skills are found in a repository, provide `--skill-name` to disambiguate.
