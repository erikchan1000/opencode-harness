"""Guards for the omp-native create-harness skill, the SKILL.md allowlist and
the conditional recovery schema."""

import json
import re
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "create-harness"
SKILL_OMP = SKILL_DIR / "SKILL.omp.md"
SKILL_MD = SKILL_DIR / "SKILL.md"
PIPELINE_AGENT = ROOT / "agents" / "harness-pipeline.md"
RECOVERY_SCHEMA = SKILL_DIR / "schemas" / "recovery.schema.json"

LEAF_ROLES = {"harness-impl", "harness-test", "harness-debug"}

FORBIDDEN = [
    "plan/findings",
    "plan/pipelines",
    "plan/objective",
    "plan/scratch",
    "plan/prompts",
    "plan/report",
    "subagent_type",
    "task_id",
    "Task(",
    "${CLAUDE_SKILL_DIR}",
    "todowrite",
    "anthropic/",
    "claude-opus",
    "claude-sonnet",
    "claude-haiku",
    ".config/opencode",
]


def test_frontmatter_name():
    text = SKILL_OMP.read_text()
    assert text.startswith("---\n")
    frontmatter = text.split("---\n", 2)[1]
    assert re.search(r"^name: create-harness$", frontmatter, re.M)
    assert re.search(r"^description:", frontmatter, re.M)


@pytest.mark.parametrize("needle", FORBIDDEN)
def test_no_opencode_or_plan_dir_residue(needle):
    assert needle not in SKILL_OMP.read_text()


def test_mentioned_schemas_exist():
    names = set(re.findall(r"[\w-]+\.schema\.json", SKILL_OMP.read_text()))
    assert names
    for name in names:
        assert (SKILL_DIR / "schemas" / name).is_file(), name


def _csv(value):
    return {part.strip() for part in value.split(",") if part.strip()}


def test_spawns_line_matches_allowlist():
    spawns = re.findall(r"^spawns: (.+)$", SKILL_OMP.read_text(), re.M)
    assert len(spawns) == 1
    assert _csv(spawns[0]) == LEAF_ROLES


def _yaml_allowed(block_owner: Path) -> set:
    text = block_owner.read_text()
    m = re.search(r"^\s*task:\n\s*\"\*\": deny.*\n((?:\s+harness-[\w-]+: allow\n)+)", text, re.M)
    assert m, f"no task allowlist in {block_owner}"
    return set(re.findall(r"(harness-[\w-]+): allow", m.group(1)))


def test_skill_md_allowlist_matches_pipeline_agent():
    assert _yaml_allowed(SKILL_MD) == LEAF_ROLES
    assert _yaml_allowed(PIPELINE_AGENT) == LEAF_ROLES
    assert "harness-review: allow" not in SKILL_MD.read_text()


@pytest.fixture(scope="module")
def validator():
    schema = json.loads(RECOVERY_SCHEMA.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _report(mode, path):
    return {
        "finding_id": "F01",
        "attempt": 1,
        "diagnosis": {"failure_mode": mode, "summary": "s"},
        "revised_prompt_path": path,
        "changes": [],
        "budget_remaining": 1,
    }


def test_recovery_string_path_valid(validator):
    assert validator.is_valid(_report("timeout_token_limit", "local://prompts/F01.recovery-1.md"))


def test_recovery_blocked_with_string_invalid(validator):
    assert not validator.is_valid(_report("genuinely_blocked", "local://prompts/F01.recovery-1.md"))


def test_recovery_nonblocked_with_null_invalid(validator):
    assert not validator.is_valid(_report("timeout_token_limit", None))


def test_recovery_blocked_with_null_valid(validator):
    assert validator.is_valid(_report("genuinely_blocked", None))


def test_recovery_path_still_required(validator):
    report = _report("genuinely_blocked", None)
    del report["revised_prompt_path"]
    assert not validator.is_valid(report)


def test_skill_md_says_three_leaf_roles():
    text = SKILL_MD.read_text()
    assert "four leaf roles" not in text
    assert "three leaf roles" in text


def test_skill_omp_states_review_absent_by_design():
    assert re.search(r"`harness-review` is absent \*\*by design\*\*", SKILL_OMP.read_text())


NON_BLOCKED_MODES = [
    "timeout_token_limit",
    "empty_truncated_output",
    "wrong_file_edited",
    "lint_compile_error",
    "test_impl_disagreement",
]


@pytest.mark.parametrize("mode", NON_BLOCKED_MODES)
def test_recovery_every_nonblocked_mode_requires_string(validator, mode):
    assert not validator.is_valid(_report(mode, None))
    assert validator.is_valid(_report(mode, "local://prompts/F01.recovery-1.md"))


def test_recovery_empty_string_path_invalid(validator):
    assert not validator.is_valid(_report("wrong_file_edited", ""))


def test_recovery_additional_properties_rejected(validator):
    report = _report("genuinely_blocked", None)
    report["extra"] = 1
    assert not validator.is_valid(report)


# ---------------------------------------------------------------------------
# FX1: precondition scope, headless flags, retry rule, todo separator, residue.
# ---------------------------------------------------------------------------


def _load_build():
    import importlib.util

    spec = importlib.util.spec_from_file_location("omp_build", ROOT / "omp" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _precondition_section():
    text = SKILL_OMP.read_text()
    start = text.index("#### Preconditions")
    return text[start : text.index("### Phase 1", start)]


def test_structured_agents_named_in_skill_match_build_output_schemas():
    structured = set(_load_build().OUTPUT_SCHEMAS)
    section = _precondition_section()
    neither = {"harness-impl", "harness-test", "harness-debug", "harness-prompt"}
    assert neither.isdisjoint(structured)
    for agent in structured | neither:
        assert f"`{agent}`" in section, agent


def test_precondition_does_not_claim_structured_unhides_output_schema():
    section = _precondition_section()
    assert "does not unhide" in section
    assert "hidden and no `yield`" not in section


def test_headless_uses_plan_yolo_into_default():
    text = SKILL_OMP.read_text()
    assert "--plan-yolo --plan-yolo-into default" in text


def test_single_retry_rule_for_isolated_runners():
    text = SKILL_OMP.read_text()
    assert "non-resumable (task.md:78)" not in text
    assert "(task.md:54,126)" in text
    assert "unverified, so a fresh runner is the safe retry" in text
    assert "prefer a cold" not in text
    # no instruction to warm-write a pipeline runner by its literal name
    assert "write agent://PipelineF0N" not in text
    assert "PipelineF01.ImplF01" in text


def test_todo_separator_is_ascii_hyphen():
    text = SKILL_OMP.read_text()
    assert "`F01 - <title>`" in text
    assert "—" not in text.split("### Phase 2", 1)[1].split("### Phase 3", 1)[0]


@pytest.mark.parametrize(
    "residue",
    [
        "Deviations from the briefing",
        "not exercised",
        "was not exercised",
        "The only fallback",
        "assumed design",
        "Agent bodies still describe scratchpads",
        "required string in every verdict schema",
    ],
)
def test_no_process_residue(residue):
    assert residue not in SKILL_OMP.read_text()


def test_no_model_ids_or_model_table_pointer():
    text = SKILL_OMP.read_text()
    assert "model table" not in text
    assert "role-to-model" not in text
    assert "/modelpreset" in text
    assert not re.search(r"\b(opus|sonnet|haiku|gpt-\d|gemini)\b", text, re.I)


def test_where_omp_differs_is_numbered_contiguously():
    text = SKILL_OMP.read_text()
    section = text.split("## Where omp differs\n", 1)[1]
    numbers = [int(n) for n in re.findall(r"^(\d+)\. \*\*", section, re.M)]
    assert numbers == list(range(1, len(numbers) + 1))


def _verdict_validator():
    schema = json.loads((SKILL_DIR / "schemas" / "pipeline-verdict.schema.json").read_text())
    return jsonschema.Draft202012Validator(schema)


def test_pipeline_verdict_done_needs_passing_tests():
    verdict = {
        "finding_id": "F01",
        "status": "DONE",
        "title": "t",
        "files_changed": [],
        "tests": {"added": 0, "passed": 0, "total": 0, "result": "pass"},
        "child_agent_ids": {},
        "warm_retries": 0,
        "spillover": None,
        "blocker": None,
    }
    v = _verdict_validator()
    assert v.is_valid(verdict)
    verdict["tests"]["result"] = "not_run"
    assert not v.is_valid(verdict)


def _backticked(fragment):
    return set(re.findall(r"`(harness-[\w-]+)`", fragment))


def test_structured_partition_in_skill_equals_build_output_schemas():
    # B2: the agents the skill lists as structured must be exactly the build's
    # OUTPUT_SCHEMAS keys, and the "neither" list exactly the rest.
    structured = set(_load_build().OUTPUT_SCHEMAS)
    section = re.sub(r"\s+", " ", _precondition_section())
    yes = re.search(r"Exactly four agents also declare `structured: true` and an `output` schema: ([^.]+)\.", section)
    no = re.search(r"The other four \(([^)]+)\) correctly have neither", section)
    assert yes and no
    assert _backticked(yes.group(1)) == structured
    assert _backticked(no.group(1)) == {"harness-impl", "harness-test", "harness-debug", "harness-prompt"}
    assert len(structured) == 4
