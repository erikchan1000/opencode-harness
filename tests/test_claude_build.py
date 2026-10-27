"""The Claude Code files under claude/ are generated from the opencode ones.

These tests fail when someone edits agents/, AGENTS.md, claude/routing.md or
a model pin in opencode.jsonc without re-running claude/build.py (or
./install.sh --claude), so the two harnesses cannot silently drift apart.
"""
import importlib.util
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("claude_build", REPO / "claude" / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def test_generated_files_are_current():
    outputs = build.render_all()
    stale = [str(p.relative_to(REPO)) for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    assert not stale, f"out of date, run `python3 claude/build.py`: {stale}"


def test_no_orphaned_claude_agents():
    expected = {p.name for p in (REPO / "agents").glob("*.md")}
    actual = {p.name for p in (REPO / "claude" / "agents").glob("*.md")}
    assert actual == expected


def test_every_agent_has_required_claude_frontmatter():
    for path in (REPO / "claude" / "agents").glob("*.md"):
        fm = yaml.safe_load(path.read_text().split("---\n")[1])
        assert fm["name"] == path.stem
        assert fm["description"].strip()
        assert fm["model"] == "inherit" or fm["model"].startswith("claude-"), path.name


def test_only_the_pipeline_runner_may_spawn_subagents():
    for path in (REPO / "claude" / "agents").glob("harness-*.md"):
        fm = yaml.safe_load(path.read_text().split("---\n")[1])
        disallowed = {t.strip() for t in fm.get("disallowedTools", "").split(",")}
        assert ("Agent" in disallowed) == (path.stem != "harness-pipeline"), path.name


def test_strip_jsonc_keeps_urls_inside_strings():
    assert build.strip_jsonc('{"u": "http://x//y", // note\n "a": [1,],}') == '{"u": "http://x//y", \n "a": [1]}'


def _disallowed(name):
    fm = yaml.safe_load((REPO / "claude" / "agents" / f"{name}.md").read_text().split("---\n")[1])
    return {t.strip() for t in fm.get("disallowedTools", "").split(",")}


def test_mcp_scoping_follows_opencode_allowlists():
    # harness-impl may use dart/paper/context7/playwright/codegraph, nothing else.
    impl = _disallowed("harness-impl")
    assert not {"mcp__dart", "mcp__paper", "mcp__context7", "mcp__playwright", "mcp__codegraph"} & impl
    assert {"mcp__linear", "mcp__stripe", "mcp__google-sheets", "mcp__brave-search"} <= impl
    # harness-recovery has no opencode entry, so it gets no scoped server.
    recovery = _disallowed("harness-recovery")
    assert {"mcp__codegraph", "mcp__linear", "mcp__paper", "mcp__dart"} <= recovery


def test_harness_review_uses_single_pr_review_scripts_path():
    # F17: step 2 used to probe two locations via an undefined CLAUDE_SKILL_DIR.
    source = (REPO / "agents" / "harness-review.md").read_text()
    generated = (REPO / "claude" / "agents" / "harness-review.md").read_text()
    assert "CLAUDE_SKILL_DIR" not in source
    assert "CLAUDE_SKILL_DIR" not in generated
    assert "~/.config/opencode/skills/pr-review/scripts/" in source
    assert "~/.claude/skills/pr-review/scripts/" in generated
    assert "~/.config/opencode/skills/pr-review/scripts/" not in generated
