"""Tests for omp/policy.py and the generated omp/extension/policy.json."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "omp"))
import build  # noqa: E402
import policy  # noqa: E402

POLICY_PATH = REPO / "omp" / "extension" / "policy.json"
POLICY = json.loads(POLICY_PATH.read_text())


def test_generated_policy_is_fresh():
    assert POLICY_PATH.read_text() == build.render_all(REPO)[POLICY_PATH]


def test_allow_sets():
    agents = POLICY["mcp"]["agents"]
    assert agents["harness-impl"] == ["codegraph", "context7", "dart", "paper", "playwright"]
    assert agents["harness-recovery"] == []
    assert agents["harness-pipeline"] == ["paper"]
    assert len(POLICY["mcp"]["servers"]) == 17


def test_every_agent_has_an_entry_and_main_sessions_do_not():
    names = {p.stem for p in (REPO / "agents").glob("*.md")}
    assert set(POLICY["mcp"]["agents"]) == names
    assert not {"build", "plan"} & set(POLICY["mcp"]["agents"])


def test_spawn_restrictions():
    parent = ["harness-pipeline"]
    assert POLICY["spawn"] == {"harness-impl": parent, "harness-test": parent, "harness-debug": parent}


CONFIG = {"permission": {"srv_*": "deny"}, "agent": {"a": {"permission": {"srv_*": "allow"}}}}


def test_render_policy_synthetic_ok():
    out = json.loads(policy.render_policy(CONFIG, {"a": {}, "b": {}, "p": {}}, {"p": ["a"]}, {"a"}))
    assert out == {"mcp": {"servers": ["srv"], "agents": {"a": ["srv"], "b": [], "p": []}}, "spawn": {"a": ["p"]}}


def test_render_policy_rejects_allow_of_unscoped_server():
    config = {"permission": {}, "agent": {"a": {"permission": {"srv_*": "allow"}}}}
    with pytest.raises(SystemExit):
        policy.render_policy(config, {"a": {}}, {}, set())


def test_render_policy_rejects_restricted_agent_without_parent():
    with pytest.raises(SystemExit):
        policy.render_policy(CONFIG, {"a": {}, "r": {}}, {"a": []}, {"r"})


def test_render_policy_rejects_unknown_restricted_agent():
    with pytest.raises(SystemExit):
        policy.render_policy(CONFIG, {"a": {}}, {"a": ["ghost"]}, {"ghost"})
