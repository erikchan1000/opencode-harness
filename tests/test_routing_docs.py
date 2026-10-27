"""Routing prose and skill text must name roles, not pinned model ids.

roles.yaml is the single source for role -> model. Prose that hard-codes a
model id (`claude-opus-5-5`) or a marketing name (`Opus 5.5`) drifts the
moment a pin changes, and the docs then tell the orchestrator the wrong thing.
These checks keep that drift out of the routing doc and the skills that
describe model routing or installation.

Each checker is also run against a pre-fix excerpt (FX2) so the test proves it
would have caught the original text.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

MODEL_ID = re.compile(r"claude-(opus|sonnet|haiku)")
MODEL_NAME = re.compile(r"\b(Opus|Sonnet|Haiku) \d")


def read(rel: str) -> str:
    return (REPO / rel).read_text()


def flat(text: str) -> str:
    """Collapse whitespace so phrases split across wrapped lines still match."""
    return " ".join(text.split())


def model_id_hits(text: str) -> list[str]:
    return [m.group(0) for m in MODEL_ID.finditer(text)]


def skill_creator_problems(text: str) -> list[str]:
    problems = []
    if "--omp" not in text:
        problems.append("does not mention `./install.sh --omp`")
    if "newly-generated" in text:
        problems.append('still says "newly-generated"')
    return problems


def routing_problems(text: str) -> list[str]:
    problems = []
    if "same model as you" in flat(text):
        problems.append('claims deep-reasoner runs "the same model as you"')
    if "roles.yaml" not in text:
        problems.append("does not reference roles.yaml")
    hits = [m.group(0) for m in MODEL_NAME.finditer(text)]
    if hits:
        problems.append(f"hard-codes model names {hits}")
    return problems


# Verbatim excerpts of the pre-fix (HEAD before FX2) text.
PRE_FIX_CREATE_HARNESS = (
    "| Test (`harness-test`) | `anthropic/claude-opus-5-5` | Code-writing role |\n"
    "| Prompt (`harness-prompt`), Pipeline (`harness-pipeline`) | "
    "`anthropic/claude-sonnet-5-5` | Structured-output roles |\n"
)
PRE_FIX_SKILL_CREATOR = (
    "When editing the (newly-generated or existing) skill, remember that the "
    "skill is being created for another instance of Claude to use.\n"
    "Then run `./install.sh` and `./install.sh --claude` from `~/opencode-harness`.\n"
)
PRE_FIX_ROUTING = (
    "You are the orchestrator, running on Opus 5.5 (the default `/model`).\n"
    "- **`deep-reasoner`** (Opus 5.5) — delegate the hardest analytical\n"
    "  work. It runs the\n"
    "  same model as you, so what it adds is a dedicated, isolated context for a\n"
    "  rigorous reasoning pass.\n"
    "Subagent pins live in `~/opencode-harness/agents/*.md` frontmatter.\n"
)


@pytest.mark.parametrize(
    "rel", ["skills/create-harness/SKILL.md", "claude/routing.md"]
)
def test_no_pinned_model_ids(rel):
    assert model_id_hits(read(rel)) == [], (
        f"{rel} hard-codes model ids; name the role and point at roles.yaml"
    )


def test_model_id_check_catches_pre_fix_create_harness():
    assert model_id_hits(PRE_FIX_CREATE_HARNESS) == [
        "claude-opus",
        "claude-sonnet",
    ]


def test_model_id_check_passes_empty_text():
    assert model_id_hits("") == []


def test_skill_creator_mentions_omp_install():
    assert skill_creator_problems(read("skills/skill-creator/SKILL.md")) == []


def test_skill_creator_check_catches_pre_fix_text():
    assert skill_creator_problems(PRE_FIX_SKILL_CREATOR) == [
        "does not mention `./install.sh --omp`",
        'still says "newly-generated"',
    ]


def test_skill_creator_check_flags_empty_text():
    assert skill_creator_problems("") == ["does not mention `./install.sh --omp`"]


def test_routing_names_roles_not_models():
    assert routing_problems(read("claude/routing.md")) == []


def test_routing_check_catches_pre_fix_text():
    problems = routing_problems(PRE_FIX_ROUTING)
    assert problems[0] == 'claims deep-reasoner runs "the same model as you"'
    assert problems[1] == "does not reference roles.yaml"
    assert problems[2].startswith("hard-codes model names")
    assert len(problems) == 3


def test_routing_check_matches_phrase_across_line_wrap():
    assert routing_problems("runs the same\nmodel as\n  you. roles.yaml") == [
        'claims deep-reasoner runs "the same model as you"'
    ]


OLD_MCP_PHRASES = ("no per-agent MCP", "per-agent MCP allowlists from opencode are gone")


@pytest.mark.parametrize("rel", ["omp/routing.md", "omp/AGENTS.md", "claude/routing.md", "claude/CLAUDE.md"])
def test_no_false_mcp_allowlist_claim(rel):
    text = flat(read(rel))
    for phrase in OLD_MCP_PHRASES:
        assert phrase not in text, f"{rel} still says {phrase!r}"


def test_omp_routing_says_mcp_is_scoped_per_agent():
    assert "MCP tools are scoped per agent" in flat(read("omp/AGENTS.md"))


def test_claude_routing_describes_disallowed_tools():
    assert "disallowedTools" in read("claude/CLAUDE.md")


ALIAS_BY_FAMILY = {"sonnet": "sonnet", "opus": "opus", "haiku": "haiku"}


def expected_task_alias(roles_yaml_text: str) -> str:
    import yaml

    model = yaml.safe_load(roles_yaml_text)["roles"]["task"]
    match = re.fullmatch(r"anthropic/claude-(sonnet|opus|haiku)-.+", model)
    assert match, f"roles.task {model!r} is not an anthropic claude model"
    return ALIAS_BY_FAMILY[match.group(1)]


def routing_task_alias(text: str) -> str:
    match = re.search(r'pass\s+`model:\s*"(\w+)"`', text)
    assert match, "claude/routing.md names no `model: \"<alias>\"` for general-purpose"
    return match.group(1)


def test_claude_routing_task_alias_matches_roles_yaml():
    assert routing_task_alias(read("claude/routing.md")) == expected_task_alias(read("roles.yaml"))


def test_alias_drift_check_fails_on_disagreement():
    assert expected_task_alias("roles:\n  task: anthropic/claude-opus-5-5\n") != routing_task_alias('pass `model: "sonnet"`')
    assert expected_task_alias("roles:\n  task: anthropic/claude-haiku-4-5\n") == "haiku"
