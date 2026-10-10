---
name: skillsmp-discovery
description: This skill should be used when the user asks to find, browse, compare, or install community skills from SkillsMP (skillsmp.com), or when a needed skill may already exist in a public marketplace.
license: MIT
---

# SkillsMP Discovery

Use this skill to discover and install community skills from SkillsMP into OpenCode.

## When to use

- The user asks for a capability that might already exist as a public skill.
- The user asks to search SkillsMP by topic or use case.
- The user asks to install a community skill into OpenCode.

## Search workflow

1. Search SkillsMP with:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/skillsmp_search.py" --query "$ARGUMENTS"
```

2. If `SKILL_MAP_API_KEY` is set, the script uses SkillsMP API endpoints.
3. If no API key is set (or API lookup fails), the script falls back to parsing SkillsMP search results via `r.jina.ai`.
4. Present top matches with repo, skill name, and short description.

## Install workflow

After the user chooses a result, install it with:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/skillsmp_install.py" --repo "owner/repo" --skill-name "skill-name"
```

Useful flags:

- `--dry-run` to preview what would be installed.
- `--overwrite` to replace an existing local copy.
- `--target-dir` to install to a non-default skills directory.

## Verify installation

Run:

```bash
opencode debug skill
```

Confirm the installed skill appears in the discovered list.

## Notes

- Skills are installed globally to `~/.config/opencode/skills` by default.
  Under Claude Code, run `~/opencode-harness/install.sh --claude` afterwards:
  it links every skill installed there into `~/.claude/skills`, so both
  tools see it. (Or pass `--target-dir ~/.claude/skills` for a Claude-only
  install.)
- Review third-party skill content before relying on it.
- If multiple skills are found in a repository, provide `--skill-name` to disambiguate.
