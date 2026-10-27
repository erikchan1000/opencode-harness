"""roles.yaml is the single source for role -> model and agent -> role.

Until the opencode/Claude generators read it (Phase 2), these tests fail when
a model pin in opencode.jsonc or agents/*.md drifts from roles.yaml, when an
agent gains or loses a pin without being listed, or when roles/presets go
out of sync with each other.
"""
import importlib.util
import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("claude_build", REPO / "claude" / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

# Agents defined only in opencode.jsonc (no agents/<name>.md file).
BUILTINS = {"build", "general", "explore"}

ROLES_YAML = yaml.safe_load((REPO / "roles.yaml").read_text())
ROLES = ROLES_YAML["roles"]
AGENTS = ROLES_YAML["agents"]
# Extra presets only: the build derives `default` from `roles:`.
PRESETS = ROLES_YAML["presets"] or {}
CONFIG = json.loads(build.strip_jsonc((REPO / "opencode.jsonc").read_text()))


def frontmatter(src: Path) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", src.read_text(), re.S)
    assert m, f"{src}: no frontmatter"
    return yaml.safe_load(m.group(1))


def file_agents() -> dict[str, dict]:
    return {src.stem: frontmatter(src) for src in sorted((REPO / "agents").glob("*.md"))}


def frontmatter_pin(name: str, fm: dict) -> str | None:
    """The agent's frontmatter `model:`; absent means no frontmatter pin."""
    if "model" not in fm:
        return None
    model = fm["model"]
    assert isinstance(model, str) and model, f"{name}: frontmatter model is {model!r}"
    return model


def config_pin(name: str) -> str | None:
    """The agent's opencode.jsonc `agent.<name>.model`; absent means no config pin."""
    if name not in CONFIG["agent"] or "model" not in CONFIG["agent"][name]:
        return None
    return CONFIG["agent"][name]["model"]


def pin(name: str, fm: dict | None) -> str | None:
    """Same precedence as claude/build.py convert: frontmatter, then opencode.jsonc."""
    if fm is not None:
        fm_pin = frontmatter_pin(name, fm)
        if fm_pin is not None:
            return fm_pin
    return config_pin(name)


def drift(roles: dict, agents: dict) -> list[str]:
    """Agents whose roles.yaml model differs from their on-disk pin."""
    files = file_agents()
    out = []
    for name, role in agents.items():
        expected = roles[role]
        actual = pin(name, files[name] if name in files else None)
        if actual != expected:
            out.append(f"{name}: roles.yaml role {role!r} -> {expected!r}, but pin is {actual!r}")
    return out


def parses_as_model_id(value: str) -> bool:
    parts = value.split("/")
    return len(parts) == 2 and all(parts)


def test_agent_roles_resolve_to_existing_pins():
    mismatches = drift(ROLES, AGENTS)
    assert not mismatches, "\n".join(mismatches)


def test_drift_check_detects_a_changed_role_model():
    # Guards the comparison itself: a roles.yaml edit that no pin follows must be reported.
    mutated = dict(ROLES, impl="anthropic/claude-opus-5-5")
    mismatches = drift(mutated, AGENTS)
    impl_agents = sorted(name for name, role in AGENTS.items() if role == "impl")
    assert impl_agents == ["coder", "harness-impl"]
    assert sorted(m.split(":")[0] for m in mismatches) == impl_agents


def test_builtins_have_explicit_opencode_pin():
    # Built-ins have no agents/<name>.md, so opencode.jsonc is their only pin source.
    for name in sorted(BUILTINS):
        assert not (REPO / "agents" / f"{name}.md").exists(), f"built-in {name} has an agents/ file"
        assert "model" in CONFIG["agent"][name], f"opencode.jsonc agent.{name} has no model"
        assert CONFIG["agent"][name]["model"] == ROLES[AGENTS[name]]


def test_frontmatter_and_config_pins_agree():
    # build.py prefers frontmatter, so a differing opencode.jsonc pin would be silently shadowed.
    for name, fm in file_agents().items():
        fm_pin, cfg_pin = frontmatter_pin(name, fm), config_pin(name)
        if fm_pin is not None and cfg_pin is not None:
            assert fm_pin == cfg_pin, f"{name}: frontmatter {fm_pin!r} vs opencode.jsonc {cfg_pin!r}"


def test_unpinned_domain_agents_are_not_listed():
    files = file_agents()
    unpinned = sorted(name for name, fm in files.items() if pin(name, fm) is None)
    assert unpinned == [
        "ehr-fhir-sync-architect",
        "hipaa-privacy-reviewer",
        "home-health-scribe-architect",
        "scribe-test-engineer",
    ]
    listed = sorted(set(unpinned) & set(AGENTS))
    assert not listed, f"unpinned agents listed in roles.yaml: {listed}"


def test_roles_yaml_top_level_keys():
    assert set(ROLES_YAML) == {"roles", "agents", "presets"}


def test_every_pinned_agent_is_listed():
    files = file_agents()
    pinned = {name for name, fm in files.items() if pin(name, fm) is not None}
    pinned |= {name for name, cfg in CONFIG["agent"].items() if "model" in cfg}
    assert pinned == set(AGENTS), (
        f"pinned but unlisted: {sorted(pinned - set(AGENTS))}; "
        f"listed but unpinned: {sorted(set(AGENTS) - pinned)}"
    )


def test_file_backed_agents_exist():
    files = set(file_agents())
    missing = sorted(set(AGENTS) - BUILTINS - files)
    assert not missing, f"roles.yaml agents without agents/<name>.md: {missing}"
    for name in BUILTINS:
        assert name in AGENTS, f"built-in {name} missing from roles.yaml agents"
        assert name in CONFIG["agent"], f"built-in {name} missing from opencode.jsonc"


def test_roles_are_consistent():
    undeclared = sorted(set(AGENTS.values()) - set(ROLES))
    assert not undeclared, f"agents reference undeclared roles: {undeclared}"
    unused = sorted(set(ROLES) - set(AGENTS.values()))
    assert not unused, f"roles unused by any agent: {unused}"
    for role, model in ROLES.items():
        assert parses_as_model_id(model), f"role {role}: {model!r} is not provider/model"


def test_default_preset_is_derived_not_declared():
    assert "default" not in PRESETS


def test_presets_use_declared_roles_and_valid_models():
    for preset, mapping in PRESETS.items():
        for role, model in mapping.items():
            assert role in ROLES, f"preset {preset}: undeclared role {role!r}"
            assert parses_as_model_id(model), f"preset {preset}.{role}: {model!r} is not provider/model"
