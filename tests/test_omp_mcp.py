"""Tests for omp/mcp.py (opencode mcp block -> omp mcp.json) and the generated omp/mcp.json.

Pure: nothing here reads ~/.config/opencode or any secret file; {file:} targets
in fixtures are tmp or nonexistent paths.
"""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("omp_mcp", REPO / "omp" / "mcp.py")
mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp)
_bspec = importlib.util.spec_from_file_location("omp_build", REPO / "omp" / "build.py")
build = importlib.util.module_from_spec(_bspec)
_bspec.loader.exec_module(build)

SOURCE = json.loads(build.strip_jsonc((REPO / "opencode.jsonc").read_text()))["mcp"]
GENERATED = json.loads((REPO / "omp" / "mcp.json").read_text())


def test_every_opencode_server_is_converted_and_rendered():
    converted = mcp.convert(SOURCE)
    assert list(converted["mcpServers"]) == list(SOURCE)
    rendered = json.loads(build.render_all()[REPO / "omp" / "mcp.json"])
    assert list(rendered["mcpServers"]) == list(SOURCE)
    assert rendered == converted


def test_env_forms():
    servers = mcp.convert(SOURCE)["mcpServers"]
    brave = servers["brave-search"]["env"]["BRAVE_API_KEY"]
    assert brave.startswith("!cat ") and brave.rstrip("'").endswith("brave-api-key")
    assert servers["figma"]["env"] == {"FIGMA_API_KEY": "${FIGMA_API_KEY}"}
    assert servers["figma"]["command"] == "npx" and servers["figma"]["args"][0] == "-y"
    assert "args" not in mcp.convert({"x": {"type": "local", "command": ["tool"]}})["mcpServers"]["x"]


def test_google_sheets_oauth_uses_placeholders():
    oauth = mcp.convert(SOURCE)["mcpServers"]["google-sheets"]["oauth"]
    assert oauth == {
        "clientId": "${GOOGLE_SHEETS_MCP_CLIENT_ID}",
        "clientSecret": "${GOOGLE_SHEETS_MCP_CLIENT_SECRET}",
        "scope": "https://www.googleapis.com/auth/spreadsheets",
        "redirectUri": "http://127.0.0.1:19876/mcp/oauth/callback",
    }


def test_no_secret_reaches_output_and_files_are_never_opened(tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("SENTINEL-SECRET-VALUE")
    cfg = {
        "brave-search": {"type": "local", "command": ["x"], "environment": {"K": f"{{file:{secret}}}"}},
        "google-sheets": {
            "type": "remote",
            "url": "https://example.test",
            "oauth": {"clientId": f"{{file:{secret}}}", "clientSecret": "{env:WHATEVER}", "scope": "s"},
        },
    }
    assert "SENTINEL" not in json.dumps(mcp.convert(cfg))
    cfg["brave-search"]["environment"]["K"] = "{file:/nonexistent/never-opened}"
    assert mcp.convert(cfg)["mcpServers"]["brave-search"]["env"]["K"] == "!cat /nonexistent/never-opened"


def test_literal_oauth_secret_raises():
    cfg = {"google-sheets": {"type": "remote", "url": "u", "oauth": {"clientSecret": "plain-secret"}}}
    with pytest.raises(ValueError, match="clientSecret"):
        mcp.convert(cfg)


def test_relative_file_reference_raises():
    with pytest.raises(ValueError, match="absolute"):
        mcp.convert({"x": {"type": "local", "command": ["a"], "env": {"K": "{file:rel/path}"}}})


def test_enabled_false_is_preserved():
    out = mcp.convert({"x": {"type": "remote", "url": "u", "enabled": False}, "y": {"type": "remote", "url": "u"}})
    assert out["mcpServers"]["x"]["enabled"] is False
    assert "enabled" not in out["mcpServers"]["y"]


@pytest.mark.parametrize(
    "cfg, match",
    [
        ({"type": "websocket", "url": "u"}, "websocket"),
        ({"type": "remote", "url": "u", "headers": {}}, "headers"),
        ({"type": "remote", "url": "u", "oauth": {"clientSecret": "{env:X}", "bogus": 1}}, "bogus"),
    ],
)
def test_unknown_input_raises(cfg, match):
    with pytest.raises(ValueError, match=match):
        mcp.convert({"srv": cfg})


def test_merge_adds_missing_keeps_existing_and_preserves_user_servers():
    generated = mcp.convert(SOURCE)
    mine = {"type": "http", "url": "https://mine.test"}
    changed = {"type": "http", "url": "https://changed.test"}
    existing = {"mcpServers": {"linear": changed, "mine": mine}}
    snap_gen, snap_existing = copy.deepcopy(generated), copy.deepcopy(existing)

    merged, changes = mcp.merge(generated, existing)

    assert generated == snap_gen and existing == snap_existing
    assert merged["mcpServers"]["linear"] == changed
    assert merged["mcpServers"]["mine"] == mine
    assert set(merged["mcpServers"]) == set(generated["mcpServers"]) | {"mine"}
    assert merged["$schema"] == generated["$schema"]
    assert "added cloudflare" in changes and not any(c.startswith("added linear") for c in changes)

    again, changes2 = mcp.merge(generated, merged)
    assert again == merged and not any(c.startswith("added") for c in changes2)


def test_merge_keeps_existing_schema():
    merged, _ = mcp.merge(mcp.convert(SOURCE), {"$schema": "mine", "mcpServers": {}})
    assert merged["$schema"] == "mine"


def test_cli_merge_backs_up_and_rejects_bad_input(tmp_path):
    target = tmp_path / "sub" / "mcp.json"
    cli = [sys.executable, str(REPO / "omp" / "mcp.py")]
    gen = str(REPO / "omp" / "mcp.json")
    subprocess.run([*cli, "merge", gen, str(target)], check=True, capture_output=True, text=True)
    assert json.loads(target.read_text()) == GENERATED and not list(target.parent.glob("*.bak-*"))
    proc = subprocess.run([*cli, "merge", gen, str(target)], check=True, capture_output=True, text=True)
    assert "(no changes)" in proc.stdout
    assert not list(target.parent.glob("mcp.json.bak-*"))  # unchanged content: no backup, no rewrite

    # a real change (a missing generated server) does back up
    cfg = json.loads(target.read_text())
    cfg["mcpServers"].pop(next(iter(cfg["mcpServers"])))
    target.write_text(json.dumps(cfg))
    subprocess.run([*cli, "merge", gen, str(target)], check=True, capture_output=True, text=True)
    assert len(list(target.parent.glob("mcp.json.bak-*"))) == 1

    target.write_text("[1]")
    proc = subprocess.run([*cli, "merge", gen, str(target)], capture_output=True, text=True)
    assert proc.returncode != 0 and "JSON object" in proc.stderr and target.read_text() == "[1]"

    assert subprocess.run([*cli, "bogus"], capture_output=True, text=True).returncode == 2


def test_committed_mcp_json_is_current():
    assert (REPO / "omp" / "mcp.json").read_text() == build.render_all()[REPO / "omp" / "mcp.json"]
    assert build.main(["--check"]) == 0


@pytest.mark.parametrize(
    "cfg, match",
    [
        ({"url": "u"}, "missing 'type'"),
        ({"type": "remote"}, "needs 'url'"),
        ({"type": "remote", "url": "u", "command": ["x"]}, "cannot have 'command'"),
        ({"type": "local"}, "non-empty list"),
        ({"type": "local", "command": []}, "non-empty list"),
        ({"type": "local", "command": ["x"], "url": "u"}, "cannot have 'url'"),
        ({"type": "local", "command": ["x"], "env": {}, "environment": {}}, "both 'env' and 'environment'"),
        ({"type": "remote", "url": "u", "env": {"K": "v"}}, "not valid on a remote server"),
        ({"type": "local", "command": ["x"], "env": {"K": "pre-{env:X}"}}, "whole value"),
        ({"type": "local", "command": ["x"], "env": {"K": 1}}, "expected a string"),
        ({"type": "remote", "url": "u", "enabled": "false"}, "expected a boolean"),
        ({"type": "remote", "url": "u", "oauth": {"clientId": "{env:X}"}}, "no redirect URI"),
    ],
)
def test_invalid_server_shapes_raise(cfg, match):
    with pytest.raises(ValueError, match=match):
        mcp.convert({"srv": cfg})


def test_oauth_env_reference_is_renamed_to_the_documented_variable():
    cfg = {"google-sheets": {"type": "remote", "url": "u", "oauth": {"clientId": "{env:SOMETHING_ELSE}"}}}
    oauth = mcp.convert(cfg)["mcpServers"]["google-sheets"]["oauth"]
    assert oauth == {"clientId": "${GOOGLE_SHEETS_MCP_CLIENT_ID}", "redirectUri": mcp.REDIRECT_URIS["google-sheets"]}


def test_file_reference_path_is_shell_quoted():
    out = mcp.convert({"x": {"type": "local", "command": ["a"], "env": {"K": "{file:/a dir/k$y}"}}})
    assert out["mcpServers"]["x"]["env"]["K"] == "!cat '/a dir/k$y'"


def test_environment_and_env_keys_both_land_in_env():
    a = mcp.convert({"x": {"type": "local", "command": ["a"], "environment": {"K": "v"}}})
    b = mcp.convert({"x": {"type": "local", "command": ["a"], "env": {"K": "v"}}})
    assert a == b and a["mcpServers"]["x"]["env"] == {"K": "v"}


def test_merge_into_empty_equals_generated_and_reports_every_add():
    generated = mcp.convert(SOURCE)
    merged, changes = mcp.merge(generated, {})
    assert merged == generated
    assert changes == [f"added {name}" for name in generated["mcpServers"]]


def test_merge_identical_existing_reports_no_changes():
    generated = mcp.convert(SOURCE)
    merged, changes = mcp.merge(generated, copy.deepcopy(generated))
    assert merged == generated and changes == []


def test_merge_rejects_non_object_servers():
    with pytest.raises(ValueError, match="'mcpServers' must be an object"):
        mcp.merge(mcp.convert(SOURCE), {"mcpServers": []})


def test_merge_result_does_not_alias_generated():
    generated = mcp.convert(SOURCE)
    merged, _ = mcp.merge(generated, {})
    merged["mcpServers"]["linear"]["url"] = "mutated"
    assert generated["mcpServers"]["linear"]["url"] != "mutated"
