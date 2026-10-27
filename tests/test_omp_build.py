"""The omp files under omp/ are generated from the opencode ones.

These tests fail when someone edits agents/, roles.yaml, AGENTS.md,
omp/routing.md, the create-harness schemas or a model pin in opencode.jsonc
without re-running omp/build.py, so the omp harness cannot silently drift from
the opencode one. They also pin the omp-specific contracts: role-based model
pins, enforced spawn limits, read-only tool lists, structured output schemas,
and loud build failures on inconsistent sources.
"""
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("omp_build", REPO / "omp" / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

OMP = REPO / "omp"
FORK_DIR = Path(os.environ.get("OMP_FORK_DIR", Path.home() / "Documents/code/oh-my-pi"))
BUILTIN_NAMES_TS = FORK_DIR / "packages/coding-agent/src/tools/builtin-names.ts"
LEFTOVER = re.compile(r"Task\(|task_id|subagent_type|SendMessage|opencode|todowrite|Agent tool|(?i:scratch)|plan/")


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n")[1])


def tool_set(fm: dict) -> set[str]:
    assert "tools" in fm, "agent restricts nothing, so it has no explicit tool list"
    return {t.strip() for t in fm["tools"].split(",")}


def agent_docs() -> dict[str, dict]:
    return {p.stem: frontmatter(p) for p in sorted((OMP / "agents").glob("*.md"))}


def fragment() -> dict:
    return yaml.safe_load((OMP / "config.fragment.yml").read_text())


def test_generated_files_are_current():
    outputs = build.render_all()
    stale = [str(p.relative_to(REPO)) for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    assert not stale, f"out of date, run `python3 omp/build.py`: {stale}"


def test_no_orphaned_omp_agents():
    expected = {p.name for p in (REPO / "agents").glob("*.md")}
    actual = {p.name for p in (OMP / "agents").glob("*.md")}
    assert actual == expected


def test_frontmatter_parses_and_model_is_a_declared_role():
    docs = agent_docs()
    model_roles = fragment()["modelRoles"]
    for name, fm in docs.items():
        assert fm["name"] == name
        if "model" in fm:
            assert fm["model"].startswith("@")
            assert fm["model"][1:] in model_roles, f"{name}: {fm['model']}"
    roles_yaml = yaml.safe_load((REPO / "roles.yaml").read_text())["agents"]
    for name, fm in docs.items():
        if name in roles_yaml:
            assert fm["model"] == f"@{roles_yaml[name]}"
        else:
            assert "model" not in fm, f"{name} is unmapped and must inherit"


def test_only_pipeline_declares_spawns():
    spawning = {n: fm["spawns"] for n, fm in agent_docs().items() if "spawns" in fm}
    assert set(spawning) == {"harness-pipeline"}
    assert {s.strip() for s in spawning["harness-pipeline"].split(",")} == {"harness-impl", "harness-test", "harness-debug"}


def test_blocking_agents():
    assert {n for n, fm in agent_docs().items() if fm.get("blocking") is True} == {"harness-impl", "harness-test", "harness-debug"}
    assert all("blocking" not in fm or fm["blocking"] is True for fm in agent_docs().values())


def test_read_only_agents_have_no_write_tools():
    read_only = ["harness-research", "harness-debug", "harness-recovery", "harness-review", "hipaa-privacy-reviewer"]
    docs = agent_docs()
    for name in read_only:
        tools = tool_set(docs[name])
        assert not tools & {"edit", "write", "ast_edit"}, name
    impl_tools = tool_set(docs["harness-impl"])
    assert {"edit", "write", "ast_edit"} <= impl_tools


def test_denied_permissions_remove_their_tools():
    docs = agent_docs()
    tools = lambda n: tool_set(docs[n])
    assert "web_search" not in tools("scribe-test-engineer")
    assert "web_search" in tools("coder")
    assert "todo" not in tools("harness-impl")
    assert "ask" not in tools("harness-impl")


def test_every_tool_name_is_an_omp_builtin():
    assert BUILTIN_NAMES_TS.is_file(), f"omp fork checkout required: {BUILTIN_NAMES_TS}"
    builtin = set(re.findall(r'"([a-z_]+)"', BUILTIN_NAMES_TS.read_text().split("] as const")[0]))
    assert set(build.BASE_TOOLS) <= builtin, sorted(set(build.BASE_TOOLS) - builtin)
    emitted = {t for fm in agent_docs().values() if "tools" in fm for t in tool_set(fm)}
    assert emitted <= builtin, sorted(emitted - builtin)


def test_every_agent_lists_tools_and_drops_opencode_keys():
    for name, fm in agent_docs().items():
        if "tools" not in fm:
            continue
        tools = [t.strip() for t in fm["tools"].split(",")]
        assert tools and len(tools) == len(set(tools)), name
        assert not {"mode", "temperature", "permission"} & set(fm), name
        # task/wait are auto-added by omp from `spawns`; never listed by hand.
        assert not {"task", "wait"} & set(tools), name


def test_output_schemas_embedded_verbatim():
    docs = agent_docs()
    for agent, schema in build.OUTPUT_SCHEMAS.items():
        expected = json.loads((REPO / "skills/create-harness/schemas" / f"{schema}.schema.json").read_text())
        assert docs[agent]["output"] == expected
        assert docs[agent]["structured"] is True
    assert {n for n, fm in docs.items() if "output" in fm} == set(build.OUTPUT_SCHEMAS)
    assert docs["harness-review"]["autoloadSkills"] == "pr-review"


def test_rules_md_is_principles_only():
    text = (OMP / "RULES.md").read_text()
    assert text.split("-->\n\n", 1)[1].startswith("# Global engineering principles")
    assert "Strength-based" not in text


def test_agents_md_is_omp_routing_without_model_ids():
    text = (OMP / "AGENTS.md").read_text()
    assert "# Strength-based model routing" in text
    assert "`task` tool" in text and "agent://" in text
    assert not re.search(r"claude-|opus|sonnet|haiku", text, re.I)


def test_no_opencode_mechanics_left_in_agent_prompts():
    for path in (OMP / "agents").glob("*.md"):
        _, _, body = path.read_text().split("---\n", 2)
        fm = frontmatter(path)
        assert not LEFTOVER.search(body), path.name
        assert not LEFTOVER.search(fm["description"]), path.name
    assert not LEFTOVER.search((OMP / "AGENTS.md").read_text())


def body(name: str) -> str:
    return (OMP / "agents" / f"{name}.md").read_text().split("---\n", 2)[2]


def test_pipeline_warm_retry_uses_the_returned_agent_id():
    # omp qualifies a child's id under its parent (`PipelineF0N.ImplF0N`); a bare
    # `agent://ImplF0N` would be "Not found", so the runner must use the returned id.
    pipeline = body("harness-pipeline")
    assert 'name: "ImplF0N"' in pipeline and 'name: "TestF0N"' in pipeline and 'name: "DebugF0N"' in pipeline
    assert "RETURNS" in pipeline and "PipelineF0N.ImplF0N" in pipeline
    assert 'write(path: "agent://<impl_agent_id>"' in pipeline
    assert not re.search(r"agent://(?!<)[A-Za-z-]*F0N", pipeline)
    assert "`wait`" in pipeline


def test_pipeline_has_no_edit_tools_but_keeps_write():
    tools = tool_set(agent_docs()["harness-pipeline"])
    assert not tools & {"edit", "ast_edit"} and "write" in tools


def test_agent_prompts_use_omp_mechanics_not_scratchpads():
    for path in (OMP / "agents").glob("*.md"):
        text = path.read_text().split("---\n", 2)[2]
        assert not re.search(r"scratch|plan/", text, re.I), path.name
        assert not re.search(r"scratch|plan/", frontmatter(path)["description"], re.I), path.name
    for name in ["harness-impl", "harness-pipeline", "harness-prompt", "harness-recovery"]:
        assert "local://prompts/" in body(name), name
    for name in ["harness-recovery", "harness-pipeline"]:
        assert "history://" in body(name), name
    assert "history://<failed-agent-id>" in body("harness-recovery")
    for name in build.OUTPUT_SCHEMAS:
        assert "`yield`" in body(name), name


def test_source_agents_keep_their_scratchpad_protocol():
    assert "Scratchpad protocol" in (REPO / "agents/harness-impl.md").read_text()


def test_config_fragment():
    frag = fragment()
    roles = yaml.safe_load((REPO / "roles.yaml").read_text())
    for role, model in roles["roles"].items():
        assert frag["modelRoles"][role] == model
    mr = frag["modelRoles"]
    assert (mr["slow"], mr["plan"], mr["advisor"], mr["commit"]) == (mr["reason"], mr["reason"], mr["review"], mr["smol"])
    assert set(frag["modelPresets"]) == {"default"} | set(roles["presets"] or {})
    assert frag["modelPresets"]["default"]["modelRoles"]["impl"] == roles["roles"]["impl"]
    for preset in frag["modelPresets"].values():
        assert {"slow", "plan", "advisor", "commit"} <= set(preset["modelRoles"])
    assert frag["task"] == {"maxRecursionDepth": 2, "isolation": {"enabled": True}}
    settings = json.loads((REPO / "claude/settings.json").read_text())
    expected = {e.removeprefix("Bash(").removesuffix(")").replace(" *", "*") for e in settings["permissions"]["deny"]}
    denied = {p["match"] for p in frag["bash"]["patterns"] if p["approval"] == "deny"}
    assert denied == expected and denied, "bash deny patterns derive from claude/settings.json"


# --- failure cases: a minimal copy of the repo in tmp_path -------------------


@pytest.fixture
def tmp_repo(tmp_path):
    for name in ["roles.yaml", "AGENTS.md", "opencode.jsonc"]:
        shutil.copy(REPO / name, tmp_path / name)
    shutil.copytree(REPO / "agents", tmp_path / "agents")
    (tmp_path / "claude").mkdir()
    shutil.copy(REPO / "claude/settings.json", tmp_path / "claude/settings.json")
    (tmp_path / "omp").mkdir()
    shutil.copy(OMP / "routing.md", tmp_path / "omp" / "routing.md")
    shutil.copytree(REPO / "skills/create-harness/schemas", tmp_path / "skills/create-harness/schemas")
    (tmp_path / "skills/pr-review").mkdir(parents=True)
    shutil.copy(REPO / "skills/pr-review/SKILL.md", tmp_path / "skills/pr-review/SKILL.md")
    build.render_all(tmp_path)  # the copy is valid before each test breaks it
    return tmp_path


def test_agent_mapped_to_undefined_role_fails(tmp_repo):
    path = tmp_repo / "roles.yaml"
    path.write_text(path.read_text().replace("harness-pipeline: structured", "harness-pipeline: bogus"))
    with pytest.raises(SystemExit, match="harness-pipeline.*bogus"):
        build.render_all(tmp_repo)


def test_missing_autoload_skill_fails(tmp_repo):
    shutil.rmtree(tmp_repo / "skills/pr-review")
    with pytest.raises(SystemExit, match="pr-review"):
        build.render_all(tmp_repo)


def test_missing_schema_file_fails(tmp_repo):
    (tmp_repo / "skills/create-harness/schemas/findings.schema.json").unlink()
    with pytest.raises(SystemExit, match="findings.schema.json"):
        build.render_all(tmp_repo)


def test_invalid_schema_json_fails(tmp_repo):
    (tmp_repo / "skills/create-harness/schemas/recovery.schema.json").write_text("{not json")
    with pytest.raises(SystemExit, match="recovery.schema.json.*not valid JSON"):
        build.render_all(tmp_repo)


def test_pinned_agent_absent_from_roles_yaml_fails(tmp_repo):
    path = tmp_repo / "roles.yaml"
    path.write_text(path.read_text().replace("  harness-debug: reason\n", ""))
    with pytest.raises(SystemExit, match="harness-debug"):
        build.render_all(tmp_repo)


def test_opencode_jsonc_pin_absent_from_roles_yaml_fails(tmp_repo):
    path = tmp_repo / "roles.yaml"
    path.write_text(path.read_text().replace("  coder: impl\n", ""))
    with pytest.raises(SystemExit, match="coder"):
        build.render_all(tmp_repo)


def test_unknown_permission_key_fails(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    path.write_text(path.read_text().replace("  question: deny", "  bash: deny\n  question: deny", 1))
    with pytest.raises(SystemExit, match="unsupported permission key 'bash'"):
        build.render_all(tmp_repo)


def test_agent_without_permission_block_fails_naming_source(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    text = path.read_text()
    start, end = text.index("permission:"), text.index("---", text.index("permission:"))
    path.write_text(text[:start] + text[end:])
    with pytest.raises(SystemExit, match="coder.md.*no `permission` block"):
        build.render_all(tmp_repo)


def test_bad_task_permission_fails(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    path.write_text(path.read_text().replace("  question: deny", "  task: allow\n  question: deny", 1))
    with pytest.raises(SystemExit, match="permission.task"):
        build.render_all(tmp_repo)


def test_check_mode_fails_on_altered_file_and_orphan(tmp_repo):
    assert build.main(["--check"], repo=tmp_repo) == 1  # nothing generated yet
    assert build.main([], repo=tmp_repo) == 0
    assert build.main(["--check"], repo=tmp_repo) == 0
    (tmp_repo / "omp" / "RULES.md").write_text("altered")
    assert build.main(["--check"], repo=tmp_repo) == 1
    build.main([], repo=tmp_repo)
    (tmp_repo / "omp" / "agents" / "ghost.md").write_text("x")
    assert build.main(["--check"], repo=tmp_repo) == 1
    build.main([], repo=tmp_repo)
    assert not (tmp_repo / "omp" / "agents" / "ghost.md").exists()


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_render_all_is_pure_and_deterministic(tmp_repo):
    before = _snapshot(tmp_repo)
    first = build.render_all(tmp_repo)
    assert build.render_all(tmp_repo) == first
    assert _snapshot(tmp_repo) == before, "render_all must not write"
    assert all(p.is_relative_to(tmp_repo / "omp") for p in first)


def test_preset_with_undeclared_role_fails(tmp_repo):
    path = tmp_repo / "roles.yaml"
    path.write_text(path.read_text() + "  cheap:\n    bogusrole: anthropic/x\n")
    with pytest.raises(SystemExit, match="preset 'cheap'.*bogusrole"):
        build.render_all(tmp_repo)


def test_declared_role_colliding_with_derived_omp_role_fails(tmp_repo):
    path = tmp_repo / "roles.yaml"
    path.write_text(path.read_text().replace("roles:\n", "roles:\n  slow: anthropic/x\n", 1))
    with pytest.raises(SystemExit, match="slow"):
        build.render_all(tmp_repo)


def test_leftover_opencode_text_in_body_fails(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    path.write_text(path.read_text() + "\nThen call SendMessage to the parent.\n")
    with pytest.raises(SystemExit, match="agents/coder.md body.*SendMessage"):
        build.render_all(tmp_repo)


def test_scratch_path_in_agent_source_is_rewritten_not_rejected(tmp_repo):
    impl = tmp_repo / "agents" / "harness-impl.md"
    impl.write_text(impl.read_text().replace("## When invoked", "Notes go to the scratchpad.\n\n## When invoked", 1) + "\n  Scratchpad: plan/scratch/x.md\n")
    out = build.render_all(tmp_repo)[tmp_repo / "omp" / "agents" / "harness-impl.md"]
    assert "plan/scratch/x.md" not in out and "history://" in out


def test_unmapped_scratch_path_is_rejected(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    path.write_text(path.read_text() + "\nWrite notes to plan/scratch/x.md.\n")
    with pytest.raises(SystemExit, match="agents/coder.md body.*plan/scratch/x.md"):
        build.render_all(tmp_repo)


def test_stray_task_call_is_still_rejected_after_scratch_rewrite(tmp_repo):
    impl = tmp_repo / "agents" / "harness-impl.md"
    impl.write_text(impl.read_text() + '\nTask(subagent_type: "x")\n')
    with pytest.raises(SystemExit, match="harness-impl.md body.*Task\\("):
        build.render_all(tmp_repo)


def test_missing_rewrite_anchor_fails_naming_the_source(tmp_repo):
    path = tmp_repo / "agents" / "harness-recovery.md"
    path.write_text(path.read_text().replace("## Scratchpad protocol", "## Notes protocol", 1))
    with pytest.raises(SystemExit, match="harness-recovery.md body"):
        build.render_all(tmp_repo)


def test_untranslatable_bash_deny_entry_fails(tmp_repo):
    (tmp_repo / "claude/settings.json").write_text(json.dumps({"permissions": {"deny": ["Read(./.env)"]}}))
    with pytest.raises(SystemExit, match="Read"):
        build.render_all(tmp_repo)


def test_untranslatable_bash_deny_entry_fails_even_beside_valid_ones(tmp_repo):
    deny = ["Bash(rm -rf *)", "WebFetch(domain:example.com)"]
    (tmp_repo / "claude/settings.json").write_text(json.dumps({"permissions": {"deny": deny}}))
    with pytest.raises(SystemExit, match="WebFetch"):
        build.render_all(tmp_repo)


def test_bash_deny_patterns_follow_claude_settings(tmp_repo):
    # A new deny rule in claude/settings.json reaches omp without editing build.py.
    deny = ["Bash(git push --force *)", "Bash(shutdown)"]
    (tmp_repo / "claude/settings.json").write_text(json.dumps({"permissions": {"deny": deny}}))
    frag = yaml.safe_load(build.render_all(tmp_repo)[tmp_repo / "omp" / "config.fragment.yml"])
    assert frag["bash"]["patterns"] == [
        {"match": "git push --force*", "approval": "deny"},
        {"match": "shutdown", "approval": "deny"},
    ]


def test_default_preset_follows_roles(tmp_repo):
    path = tmp_repo / "roles.yaml"
    text = path.read_text()
    old = "  impl: anthropic/claude-sonnet-5-5\n"
    assert old in text
    path.write_text(text.replace(old, "  impl: anthropic/claude-test-impl\n", 1))
    frag = yaml.safe_load(build.render_all(tmp_repo)[tmp_repo / "omp" / "config.fragment.yml"])
    assert frag["modelPresets"]["default"]["modelRoles"]["impl"] == "anthropic/claude-test-impl"
    assert frag["modelRoles"]["impl"] == "anthropic/claude-test-impl"


def test_unrestricted_agent_omits_tools(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    text = path.read_text()
    start, end = text.index("permission:\n"), text.index("---\n", 4)
    # `task: deny` restricts spawning only, not the toolset.
    path.write_text(text[:start] + "permission:\n  task: deny\n" + text[end:])
    out = build.render_all(tmp_repo)[tmp_repo / "omp" / "agents" / "coder.md"]
    assert "tools" not in yaml.safe_load(out.split("---\n")[1])


def test_presets_default_in_roles_yaml_fails(tmp_repo):
    path = tmp_repo / "roles.yaml"
    path.write_text(path.read_text() + "  default:\n    default: anthropic/x\n")
    with pytest.raises(SystemExit, match="presets.default is derived"):
        build.render_all(tmp_repo)


def test_leftover_opencode_text_in_description_fails(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    path.write_text(path.read_text().replace("description: Code", "description: Uses subagent_type routing. Code", 1))
    with pytest.raises(SystemExit, match="agents/coder.md description.*subagent_type"):
        build.render_all(tmp_repo)


def test_non_deny_permission_value_fails(tmp_repo):
    path = tmp_repo / "agents" / "coder.md"
    path.write_text(path.read_text().replace("  question: deny", "  question: allow", 1))
    with pytest.raises(SystemExit, match=r"coder.md: permission.question must be 'deny'"):
        build.render_all(tmp_repo)


def test_task_allow_entry_with_non_allow_verdict_fails(tmp_repo):
    path = tmp_repo / "agents" / "harness-pipeline.md"
    path.write_text(path.read_text().replace("    harness-debug: allow", "    harness-debug: ask", 1))
    with pytest.raises(SystemExit, match="permission.task.harness-debug must be 'allow'"):
        build.render_all(tmp_repo)


def test_task_dict_without_wildcard_deny_fails(tmp_repo):
    path = tmp_repo / "agents" / "harness-pipeline.md"
    path.write_text(path.read_text().replace('    "*": deny\n', "", 1))
    with pytest.raises(SystemExit, match="harness-pipeline.md: permission.task"):
        build.render_all(tmp_repo)


def test_spawns_follow_the_opencode_task_allow_list(tmp_repo, monkeypatch):
    # harness-debug would be a restricted-spawn agent without a parent (the policy build refuses that).
    monkeypatch.setattr(build, "RESTRICTED_SPAWN", build.RESTRICTED_SPAWN - {"harness-debug"})
    path = tmp_repo / "agents" / "harness-pipeline.md"
    path.write_text(path.read_text().replace("    harness-debug: allow\n", "", 1))
    out = build.render_all(tmp_repo)[tmp_repo / "omp" / "agents" / "harness-pipeline.md"]
    fm = yaml.safe_load(out.split("---\n")[1])
    assert {s.strip() for s in fm["spawns"].split(",")} == {"harness-impl", "harness-test"}


def test_agents_md_without_routing_marker_fails(tmp_repo):
    path = tmp_repo / "AGENTS.md"
    path.write_text(path.read_text().replace("# Strength-based model routing", "# Routing", 1))
    with pytest.raises(SystemExit, match="Strength-based model routing"):
        build.render_all(tmp_repo)


def test_main_rejects_unknown_arguments(tmp_repo):
    with pytest.raises(SystemExit, match="usage"):
        build.main(["--bogus"], repo=tmp_repo)
    assert not (tmp_repo / "omp" / "agents").exists()


def test_pipeline_body_is_respawned_cold_and_does_not_overclaim_enforcement():
    body = (OMP / "agents" / "harness-pipeline.md").read_text().split("---\n", 2)[2]
    flat_body = " ".join(body.split())
    assert "you are being warm-retried" not in flat_body
    assert "**re-spawn**" in flat_body
    assert "This is enforced" not in flat_body
    assert "`bash` must stay read-only" in flat_body


def test_harness_debug_description_matches_the_spawn_guard():
    desc = frontmatter(OMP / "agents" / "harness-debug.md")["description"]
    assert "when verification reveals" not in desc
    assert "Manual smoke test" not in desc
    assert "Only harness-pipeline spawns this agent" in desc


def test_restricted_spawn_is_separate_from_blocking():
    assert build.RESTRICTED_SPAWN is not build.BLOCKING
