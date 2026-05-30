"""Tests for run_review.py."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pr-review" / "scripts"))
import run_review


class TestResolveModel:
    """Tests for _resolve_model()."""

    def test_default_model(self):
        """Should return default model when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert run_review._resolve_model() == run_review.DEFAULT_MODEL

    def test_custom_model_from_env(self):
        """Should return custom model from PR_AGENT_MODEL."""
        with patch.dict(os.environ, {"PR_AGENT_MODEL": "openai/gpt-4o"}):
            assert run_review._resolve_model() == "openai/gpt-4o"


class TestResolveApiKey:
    """Tests for _resolve_api_key()."""

    def test_anthropic_key_for_claude_model(self):
        """Should prefer ANTHROPIC_KEY for Claude models."""
        with patch.dict(os.environ, {"ANTHROPIC_KEY": "sk-ant-test"}, clear=True):
            result = run_review._resolve_api_key("anthropic/claude-sonnet-4-20250514")
            assert result == ("anthropic", "sk-ant-test")

    def test_openai_key_for_openai_model(self):
        """Should use OPENAI_KEY for OpenAI models."""
        with patch.dict(os.environ, {"OPENAI_KEY": "sk-test"}, clear=True):
            result = run_review._resolve_api_key("gpt-4o")
            assert result == ("openai", "sk-test")

    def test_fallback_to_any_available_key(self):
        """Should fall back to any available key."""
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk-test"}, clear=True):
            result = run_review._resolve_api_key("unknown/model")
            assert result == ("groq", "gsk-test")

    def test_returns_none_when_no_keys(self):
        """Should return None when no API keys or secrets file."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ("OPENAI_KEY", "ANTHROPIC_KEY", "GROQ_API_KEY", "DEEPSEEK_KEY"):
                os.environ.pop(key, None)
            with patch.object(run_review, "_read_secrets_toml", return_value={}):
                result = run_review._resolve_api_key("any-model")
                assert result is None

    def test_anthropic_key_preferred_for_anthropic_model(self):
        """When both keys present, should pick the right one for the model."""
        with patch.dict(os.environ, {
            "ANTHROPIC_KEY": "sk-ant",
            "OPENAI_KEY": "sk-oai",
        }):
            result = run_review._resolve_api_key("anthropic/claude-3-opus")
            assert result == ("anthropic", "sk-ant")

    def test_openai_fallback_for_generic_model(self):
        """Should fall back to OpenAI key for unrecognized provider."""
        with patch.dict(os.environ, {"OPENAI_KEY": "sk-oai"}, clear=True):
            result = run_review._resolve_api_key("some-random-model")
            assert result == ("openai", "sk-oai")

    def test_secrets_file_fallback_anthropic(self):
        """Should read from secrets.toml when env vars are empty."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ("OPENAI_KEY", "ANTHROPIC_KEY", "GROQ_API_KEY", "DEEPSEEK_KEY"):
                os.environ.pop(key, None)
            with patch.object(run_review, "_read_secrets_toml", return_value={
                "anthropic": {"key": "sk-ant-from-file"},
            }):
                result = run_review._resolve_api_key("anthropic/claude-sonnet")
                assert result == ("anthropic", "sk-ant-from-file")

    def test_secrets_file_fallback_openai(self):
        """Should read OpenAI key from secrets.toml."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ("OPENAI_KEY", "ANTHROPIC_KEY", "GROQ_API_KEY", "DEEPSEEK_KEY"):
                os.environ.pop(key, None)
            with patch.object(run_review, "_read_secrets_toml", return_value={
                "openai": {"key": "sk-oai-from-file"},
            }):
                result = run_review._resolve_api_key("gpt-4o")
                assert result == ("openai", "sk-oai-from-file")

    def test_env_var_takes_precedence_over_secrets_file(self):
        """Env var should win over secrets.toml."""
        with patch.dict(os.environ, {"ANTHROPIC_KEY": "sk-from-env"}):
            with patch.object(run_review, "_read_secrets_toml", return_value={
                "anthropic": {"key": "sk-from-file"},
            }):
                result = run_review._resolve_api_key("anthropic/claude-sonnet")
                assert result == ("anthropic", "sk-from-env")


class TestReadSecretsToml:
    """Tests for _read_secrets_toml()."""

    def test_reads_valid_file(self, tmp_path: Path):
        """Should parse sections and keys from TOML."""
        secrets_file = tmp_path / "secrets.toml"
        secrets_file.write_text('[anthropic]\nKEY = "sk-test-key"\n')
        with patch.object(run_review, "SECRETS_PATH", secrets_file):
            result = run_review._read_secrets_toml()
            assert result == {"anthropic": {"key": "sk-test-key"}}

    def test_handles_missing_file(self, tmp_path: Path):
        """Should return empty dict when file doesn't exist."""
        with patch.object(run_review, "SECRETS_PATH", tmp_path / "nonexistent.toml"):
            assert run_review._read_secrets_toml() == {}

    def test_handles_multiple_sections(self, tmp_path: Path):
        """Should parse multiple provider sections."""
        secrets_file = tmp_path / "secrets.toml"
        secrets_file.write_text(
            '[anthropic]\nKEY = "sk-ant"\n\n[openai]\nkey = "sk-oai"\n'
        )
        with patch.object(run_review, "SECRETS_PATH", secrets_file):
            result = run_review._read_secrets_toml()
            assert result["anthropic"]["key"] == "sk-ant"
            assert result["openai"]["key"] == "sk-oai"

    def test_ignores_comments(self, tmp_path: Path):
        """Should skip comment lines."""
        secrets_file = tmp_path / "secrets.toml"
        secrets_file.write_text('# comment\n[anthropic]\n# another\nKEY = "sk-test"\n')
        with patch.object(run_review, "SECRETS_PATH", secrets_file):
            result = run_review._read_secrets_toml()
            assert result["anthropic"]["key"] == "sk-test"

    def test_handles_equals_in_value(self, tmp_path: Path):
        """Should preserve = signs inside quoted values (e.g., base64 keys)."""
        secrets_file = tmp_path / "secrets.toml"
        secrets_file.write_text('[anthropic]\nKEY = "sk-ant-abc123+def=="\n')
        with patch.object(run_review, "SECRETS_PATH", secrets_file):
            result = run_review._read_secrets_toml()
            assert result["anthropic"]["key"] == "sk-ant-abc123+def=="



class TestMainValidation:
    """Tests for main() argument validation."""

    def test_no_url_or_local_returns_2(self):
        """Should exit 2 when neither --pr-url nor --local is specified."""
        with patch("sys.argv", ["run_review.py", "--command", "review"]):
            assert run_review.main() == 2

    def test_missing_api_key_returns_2(self):
        """Should exit 2 when no API key is available."""
        with patch("sys.argv", ["run_review.py", "--local", "--command", "review"]):
            with patch.object(run_review, "_venv_python") as mock_py:
                mock_py.return_value = MagicMock()
                mock_py.return_value.exists.return_value = True
                with patch.object(run_review, "_resolve_api_key", return_value=None):
                    assert run_review.main() == 2

    def test_missing_venv_returns_2(self):
        """Should exit 2 when venv doesn't exist."""
        with patch("sys.argv", ["run_review.py", "--local", "--command", "review"]):
            with patch.object(run_review, "_venv_python") as mock_py:
                mock_py.return_value = MagicMock()
                mock_py.return_value.exists.return_value = False
                assert run_review.main() == 2


class TestCheckHasDiff:
    """Tests for _check_has_diff()."""

    def test_has_diff(self):
        """Should return True when there are changes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=" src/foo.ts | 10 +++++++---\n 1 file changed\n"
            )
            assert run_review._check_has_diff("main") is True

    def test_no_diff(self):
        """Should return False when there are no changes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            assert run_review._check_has_diff("main") is False

    def test_handles_timeout(self):
        """Should return False on timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            assert run_review._check_has_diff("main") is False
