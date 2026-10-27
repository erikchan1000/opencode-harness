"""Tests for omp/install.sh, omp/merge_config.py and the SKILL.omp.md exclusion.

Every installer run gets HOME and PI_CODING_AGENT_DIR pointed into tmp_path;
nothing here may touch the real ~/.omp, ~/.claude or ~/.config/opencode.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "omp"))
import merge_config  # noqa: E402

FRAGMENT = yaml.safe_load((REPO / "omp" / "config.fragment.yml").read_text())
DENY = FRAGMENT["bash"]["patterns"]


@pytest.fixture
def allow_default_agent_dir():
    """Opt-out for the one test that checks the ~/.omp/agent default (HOME is still tmp)."""


@pytest.fixture(autouse=True)
def _installer_env_guard(request, tmp_path, monkeypatch):
    """Fail any installer subprocess whose HOME / PI_CODING_AGENT_DIR is not under tmp_path."""
    real_run = subprocess.run
    tmp = tmp_path.resolve()

    def guarded_run(args, *a, **kw):
        runs_installer = "-n" not in args and any(str(arg).endswith("install.sh") for arg in args)
        if runs_installer:
            env = kw.get("env")
            assert env is not None, "installer run without an explicit env"
            assert Path(env["HOME"]).resolve().is_relative_to(tmp), env["HOME"]
            if "allow_default_agent_dir" in request.fixturenames:
                assert "PI_CODING_AGENT_DIR" not in env
            else:
                assert Path(env["PI_CODING_AGENT_DIR"]).resolve().is_relative_to(tmp), env["PI_CODING_AGENT_DIR"]
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", guarded_run)


@pytest.fixture
def sandbox(tmp_path):
    home = tmp_path / "home"
    agent = tmp_path / "agent"
    home.mkdir()
    return home, agent


def run_installer(args, home, agent=None):
    """Run a repo installer with HOME (and PI_CODING_AGENT_DIR) in the sandbox."""
    real_home = Path(os.path.expanduser("~"))
    assert Path(home) != real_home
    # OMP_SKIP_BUILD: omp/install.sh must not regenerate files in the repo during tests;
    # generated-file freshness is covered by test_omp_build.py.
    env = {**os.environ, "HOME": str(home), "OMP_SKIP_BUILD": "1"}
    if agent is not None:
        assert Path(agent) != real_home / ".omp" / "agent"
        env["PI_CODING_AGENT_DIR"] = str(agent)
    else:
        env.pop("PI_CODING_AGENT_DIR", None)
    return subprocess.run(args, cwd=REPO, env=env, capture_output=True, text=True, check=True)


def assert_omp_layout(agent):
    for sub in ("agents/" + p.name for p in (REPO / "omp" / "agents").glob("*.md")):
        link = agent / sub
        assert link.is_symlink() and link.resolve() == (REPO / "omp" / sub).resolve()
    for name in ("RULES.md", "AGENTS.md"):
        assert (agent / name).is_symlink()
        assert (agent / name).resolve() == (REPO / "omp" / name).resolve()
    plain = agent / "skills" / "caveman"
    assert plain.is_symlink() and plain.resolve() == (REPO / "skills" / "caveman").resolve()
    copy = agent / "skills" / "create-harness"
    assert copy.is_dir() and not copy.is_symlink()
    assert (copy / "SKILL.md").read_text() == (REPO / "skills/create-harness/SKILL.omp.md").read_text()
    assert not (copy / "SKILL.omp.md").exists()
    assert not list(copy.rglob("__pycache__"))
    assert yaml.safe_load((agent / "config.yml").read_text())["task"]["maxRecursionDepth"] == 2


def test_omp_install_full_run(sandbox):
    home, agent = sandbox
    run_installer(["bash", "omp/install.sh"], home, agent)
    assert_omp_layout(agent)
    assert not (home / ".omp").exists()  # PI_CODING_AGENT_DIR, not the HOME default, was used


def test_omp_install_rerun_replaces_copy_without_backup(sandbox):
    home, agent = sandbox
    run_installer(["bash", "omp/install.sh"], home, agent)
    run_installer(["bash", "omp/install.sh"], home, agent)
    assert_omp_layout(agent)
    assert not list((agent / "skills").glob("*.bak-*"))


def test_install_sh_omp_dispatch(sandbox):
    home, agent = sandbox
    run_installer(["bash", "install.sh", "--omp"], home, agent)
    assert_omp_layout(agent)
    assert not (home / ".config").exists()  # did not fall through to the opencode install


def test_omp_default_agent_dir_is_under_home(sandbox, allow_default_agent_dir):
    home, _ = sandbox
    run_installer(["bash", "omp/install.sh"], home)
    assert (home / ".omp" / "agent" / "config.yml").is_file()


def test_opencode_install_hides_skill_omp_md(sandbox):
    home, agent = sandbox
    run_installer(["bash", "install.sh"], home, agent)
    skill = home / ".config/opencode/skills/create-harness"
    assert skill.is_dir() and not skill.is_symlink()
    assert not (skill / "SKILL.omp.md").exists()
    assert (skill / "SKILL.md").resolve() == (REPO / "skills/create-harness/SKILL.md").resolve()
    plain = home / ".config/opencode/skills/caveman"
    assert plain.is_symlink()
    # re-run replaces the farm cleanly
    run_installer(["bash", "install.sh"], home, agent)
    assert not agent.exists()  # opencode install never touches the omp agent dir
    assert not list((home / ".config/opencode/skills").glob("*.bak-*"))


def test_claude_installer_excludes_skill_omp_md_statically():
    # Not executed: it runs claude/mcp.sh. Check it routes skills through the
    # farm helper and skips opencode-only names already in skills/.
    text = (REPO / "claude/install.sh").read_text()
    assert 'link_skill "${skill_path%/}" "$CLAUDE_DIR/skills/' in text
    assert 'source "$REPO/lib/link.sh"' in text
    assert "! -name SKILL.omp.md" in (REPO / "lib/link.sh").read_text()
    assert '[ -d "$REPO/skills/$(basename "$skill_path")" ] && continue' in text


# --- merge_config ---------------------------------------------------------

USER_CONFIG = """\
# my comment
theme: dark
modelRoles:
  default: openai/gpt-x
  mine: openai/custom
modelPresets:
  default:
    modelRoles:
      default: openai/gpt-x
  work:
    modelRoles:
      default: openai/work
task:
  maxConcurrency: 4
  maxRecursionDepth: 9
bash:
  patterns:
  - match: ls*
    approval: allow
  - match: codegraph index*
    approval: deny
  other: 1
"""


def run_merge(target):
    return subprocess.run(
        [sys.executable, str(REPO / "omp/merge_config.py"), str(REPO / "omp/config.fragment.yml"), str(target)],
        capture_output=True, text=True, check=True,
    )


def test_merge_preserves_user_keys_and_sets_owned(tmp_path):
    target = tmp_path / "config.yml"
    target.write_text(USER_CONFIG)
    run_merge(target)
    out = yaml.safe_load(target.read_text())

    assert out["theme"] == "dark"
    assert out["bash"]["other"] == 1
    assert out["task"]["maxConcurrency"] == 4
    assert out["task"]["maxRecursionDepth"] == FRAGMENT["task"]["maxRecursionDepth"]
    assert out["modelRoles"]["mine"] == "openai/custom"
    assert out["modelRoles"]["default"] == FRAGMENT["modelRoles"]["default"]  # roles.yaml wins
    assert out["modelRoles"].keys() >= FRAGMENT["modelRoles"].keys()
    assert out["modelPresets"]["work"] == {"modelRoles": {"default": "openai/work"}}
    assert out["modelPresets"]["default"] == FRAGMENT["modelPresets"]["default"]  # replaced whole
    assert out["bash"]["patterns"] == DENY + [{"match": "ls*", "approval": "allow"}]  # denies first, no dupes

    backups = list(tmp_path.glob("config.yml.bak-*"))
    assert len(backups) == 1 and backups[0].read_text() == USER_CONFIG


def test_merge_idempotent(tmp_path):
    target = tmp_path / "config.yml"
    target.write_text(USER_CONFIG)
    run_merge(target)
    first = target.read_text()
    run_merge(target)
    assert target.read_text() == first
    assert yaml.safe_load(first)["bash"]["patterns"].count(DENY[0]) == 1


def test_merge_user_allow_cannot_precede_deny(tmp_path):
    target = tmp_path / "config.yml"
    target.write_text("bash:\n  patterns:\n  - match: codegraph*\n    approval: allow\n")
    run_merge(target)
    patterns = yaml.safe_load(target.read_text())["bash"]["patterns"]
    assert patterns[: len(DENY)] == DENY
    assert patterns[-1] == {"match": "codegraph*", "approval": "allow"}


def test_merge_creates_absent_target_with_only_owned_keys(tmp_path):
    target = tmp_path / "sub" / "config.yml"
    run_merge(target)
    assert yaml.safe_load(target.read_text()) == FRAGMENT
    assert not list(target.parent.glob("*.bak-*"))


@pytest.mark.parametrize("content", ["- a\n- b\n", "just a string\n"])
def test_merge_rejects_non_mapping_target(tmp_path, content):
    target = tmp_path / "config.yml"
    target.write_text(content)
    with pytest.raises(subprocess.CalledProcessError) as exc:
        run_merge(target)
    assert "expected a YAML mapping" in exc.value.stderr
    assert target.read_text() == content
    assert not list(tmp_path.glob("*.bak-*"))


def test_merge_function_does_not_mutate_input():
    current = yaml.safe_load(USER_CONFIG)
    snapshot = yaml.safe_load(USER_CONFIG)
    merge_config.merge(FRAGMENT, current)
    assert current == snapshot


def test_installer_env_guard_rejects_real_home(tmp_path):
    # The autouse guard itself: an installer run with HOME outside tmp_path must
    # fail before the subprocess starts. `true` is never reached.
    env = {**os.environ, "HOME": str(Path(os.path.expanduser("~"))), "PI_CODING_AGENT_DIR": str(tmp_path)}
    with pytest.raises(AssertionError):
        subprocess.run(["bash", "omp/install.sh"], cwd=REPO, env=env, check=True)
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("PI_CODING_AGENT_DIR", None)
    with pytest.raises(KeyError):
        subprocess.run(["bash", "omp/install.sh"], cwd=REPO, env=env, check=True)


def test_installer_scripts_parse():
    subprocess.run(["bash", "-n", "omp/install.sh", "install.sh", "claude/install.sh"], cwd=REPO, check=True)


# --- omp/install.sh over pre-existing state ------------------------------

def test_omp_install_backs_up_foreign_skill_dir_and_rules(sandbox):
    home, agent = sandbox
    foreign = agent / "skills" / "create-harness"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("user's own skill\n")
    (agent / "RULES.md").write_text("user rules\n")
    run_installer(["bash", "omp/install.sh"], home, agent)
    assert_omp_layout(agent)
    [skill_bak] = list((agent / "skills").glob("create-harness.bak-*"))
    assert (skill_bak / "SKILL.md").read_text() == "user's own skill\n"
    [rules_bak] = list(agent.glob("RULES.md.bak-*"))
    assert rules_bak.read_text() == "user rules\n"


def test_omp_install_replaces_symlinked_skill_copy_target(sandbox, tmp_path):
    home, agent = sandbox
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (agent / "skills").mkdir(parents=True)
    (agent / "skills" / "create-harness").symlink_to(elsewhere)
    run_installer(["bash", "omp/install.sh"], home, agent)
    assert_omp_layout(agent)
    assert list(elsewhere.iterdir()) == []  # wrote a fresh dir, not through the old link
    assert not list((agent / "skills").glob("*.bak-*"))


def test_omp_install_rerun_drops_stale_files_from_copy(sandbox):
    home, agent = sandbox
    run_installer(["bash", "omp/install.sh"], home, agent)
    stale = agent / "skills" / "create-harness" / "stale.md"
    stale.write_text("left over\n")
    run_installer(["bash", "omp/install.sh"], home, agent)
    assert not stale.exists()


def test_omp_install_merges_existing_config(sandbox):
    home, agent = sandbox
    agent.mkdir()
    (agent / "config.yml").write_text(USER_CONFIG)
    run_installer(["bash", "omp/install.sh"], home, agent)
    first = (agent / "config.yml").read_text()
    out = yaml.safe_load(first)
    assert out["theme"] == "dark" and out["modelPresets"]["work"]["modelRoles"]["default"] == "openai/work"
    assert out["bash"]["patterns"][: len(DENY)] == DENY
    backups = list(agent.glob("config.yml.bak-*"))
    assert backups and any(b.read_text() == USER_CONFIG for b in backups)

    run_installer(["bash", "omp/install.sh"], home, agent)
    assert (agent / "config.yml").read_text() == first


# --- merge_config edge cases ----------------------------------------------

def test_merge_empty_target_gets_owned_keys_and_backup(tmp_path):
    target = tmp_path / "config.yml"
    target.write_text("")
    run_merge(target)
    assert yaml.safe_load(target.read_text()) == FRAGMENT
    [backup] = list(tmp_path.glob("config.yml.bak-*"))
    assert backup.read_text() == ""


@pytest.mark.parametrize(
    "content, key",
    [
        ("modelRoles: openai/x\n", "modelRoles"),
        ("task: 3\n", "task"),
        ("bash:\n  patterns: nope\n", "bash.patterns"),
    ],
)
def test_merge_rejects_wrong_typed_owned_section(tmp_path, content, key):
    target = tmp_path / "config.yml"
    target.write_text(content)
    with pytest.raises(subprocess.CalledProcessError) as exc:
        run_merge(target)
    assert f"'{key}'" in exc.value.stderr
    assert target.read_text() == content  # never overwritten


def test_merge_function_reports_no_changes_on_merged_input():
    merged, changes = merge_config.merge(FRAGMENT, yaml.safe_load(USER_CONFIG))
    assert changes
    again, changes2 = merge_config.merge(FRAGMENT, merged)
    assert again == merged and changes2 == []


def test_merge_cli_rejects_wrong_arg_count():
    proc = subprocess.run([sys.executable, str(REPO / "omp/merge_config.py")], capture_output=True, text=True)
    assert proc.returncode == 2
    assert "Usage" in proc.stderr


def test_omp_install_merges_mcp_json_without_touching_existing_entries(sandbox):
    home, agent = sandbox
    agent.mkdir()
    generated = json.loads((REPO / "omp" / "mcp.json").read_text())["mcpServers"]
    user_server = {"type": "http", "url": "https://mine.test"}
    modified = {"type": "http", "url": "https://modified.test"}
    original = json.dumps({"mcpServers": {"mine": user_server, "linear": modified}})
    (agent / "mcp.json").write_text(original)
    run_installer(["bash", "omp/install.sh"], home, agent)
    servers = json.loads((agent / "mcp.json").read_text())["mcpServers"]
    assert servers["mine"] == user_server
    assert servers["linear"] == modified
    assert {k: v for k, v in servers.items() if k not in ("mine", "linear")} == {
        k: v for k, v in generated.items() if k != "linear"
    }
    [backup] = list(agent.glob("mcp.json.bak-*"))
    assert backup.read_text() == original


def test_omp_install_creates_mcp_json_when_absent_and_rerun_is_noop(sandbox):
    home, agent = sandbox
    generated = json.loads((REPO / "omp" / "mcp.json").read_text())
    run_installer(["bash", "omp/install.sh"], home, agent)
    assert json.loads((agent / "mcp.json").read_text()) == generated
    assert not list(agent.glob("mcp.json.bak-*"))
    proc = run_installer(["bash", "omp/install.sh"], home, agent)
    assert json.loads((agent / "mcp.json").read_text()) == generated
    assert "(no changes)" in proc.stdout
    assert not list(agent.glob("mcp.json.bak-*"))


def test_omp_install_adds_extension_dir_once_and_keeps_user_entries(sandbox):
    home, agent = sandbox
    agent.mkdir()
    (agent / "config.yml").write_text("extensions:\n  - /somewhere/user-ext\n")
    ext = str(REPO / "omp" / "extension")
    run_installer(["bash", "omp/install.sh"], home, agent)
    first = yaml.safe_load((agent / "config.yml").read_text())["extensions"]
    assert first == ["/somewhere/user-ext", ext]
    run_installer(["bash", "omp/install.sh"], home, agent)
    assert yaml.safe_load((agent / "config.yml").read_text())["extensions"] == first


def test_merge_extension_dirs_appends_once_and_reports_change():
    current = {"extensions": ["/user/ext"]}
    merged, changes = merge_config.merge(FRAGMENT, current, ("/repo/omp/extension",))
    assert merged["extensions"] == ["/user/ext", "/repo/omp/extension"]
    assert "extensions: added /repo/omp/extension" in changes
    assert current == {"extensions": ["/user/ext"]}  # input not mutated
    again, changes2 = merge_config.merge(FRAGMENT, merged, ("/repo/omp/extension",))
    assert again["extensions"] == ["/user/ext", "/repo/omp/extension"]
    assert not [c for c in changes2 if c.startswith("extensions")]


def test_merge_without_extension_dirs_leaves_extensions_absent():
    merged, _ = merge_config.merge(FRAGMENT, {})
    assert "extensions" not in merged


def test_merge_rejects_non_list_extensions():
    with pytest.raises(ValueError, match="extensions"):
        merge_config.merge(FRAGMENT, {"extensions": "/user/ext"}, ("/repo/omp/extension",))


def test_merge_cli_rejects_relative_extension_dir(tmp_path):
    target = tmp_path / "config.yml"
    proc = subprocess.run(
        [sys.executable, str(REPO / "omp/merge_config.py"), str(REPO / "omp/config.fragment.yml"), str(target),
         "--extension-dir", "relative/ext"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "absolute" in proc.stderr
    assert not target.exists()


def test_merge_cli_extension_dir_flag_is_repeatable(tmp_path):
    target = tmp_path / "config.yml"
    proc = subprocess.run(
        [sys.executable, str(REPO / "omp/merge_config.py"), "--extension-dir", "/a/ext",
         str(REPO / "omp/config.fragment.yml"), str(target), "--extension-dir", "/b/ext"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert yaml.safe_load(target.read_text())["extensions"] == ["/a/ext", "/b/ext"]


def test_merge_cli_noop_rerun_makes_no_backup_and_keeps_bytes(tmp_path):
    target = tmp_path / "config.yml"
    argv = ["merge_config.py", str(REPO / "omp/config.fragment.yml"), str(target)]
    assert merge_config.main(argv) == 0
    assert merge_config.main(argv) == 0  # second run settles any key reordering
    settled = target.read_text()
    # a user comment would be stripped by a re-dump; a no-op run must not touch the file
    target.write_text("# user comment\n" + settled)
    before = target.read_text()
    assert merge_config.main(argv) == 0
    assert target.read_text() == before
    assert not list(tmp_path.glob("config.yml.bak-*"))
