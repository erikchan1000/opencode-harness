"""Tests for ensure_installed.py."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pr-review" / "scripts"))
import ensure_installed


class TestGetInstalledVersion:
    """Tests for _get_installed_version()."""

    def test_returns_version_when_installed(self, tmp_path: Path):
        """Should parse version from pip show output."""
        with patch.object(ensure_installed, "VENV_DIR", tmp_path):
            with patch.object(ensure_installed, "_python_bin") as mock_bin:
                mock_bin.return_value = tmp_path / "bin" / "python"
                # Create the fake binary path so .exists() returns True
                (tmp_path / "bin").mkdir()
                (tmp_path / "bin" / "python").touch()

                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout="Name: pr-agent\nVersion: 0.35.0\nSummary: ...\n",
                    )
                    assert ensure_installed._get_installed_version() == "0.35.0"

    def test_returns_none_when_not_installed(self, tmp_path: Path):
        """Should return None when pip show fails."""
        with patch.object(ensure_installed, "VENV_DIR", tmp_path):
            with patch.object(ensure_installed, "_python_bin") as mock_bin:
                mock_bin.return_value = tmp_path / "bin" / "python"
                (tmp_path / "bin").mkdir()
                (tmp_path / "bin" / "python").touch()

                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=1, stdout="")
                    assert ensure_installed._get_installed_version() is None

    def test_returns_none_when_venv_missing(self, tmp_path: Path):
        """Should return None when venv Python doesn't exist."""
        with patch.object(ensure_installed, "_python_bin") as mock_bin:
            mock_bin.return_value = tmp_path / "nonexistent" / "python"
            assert ensure_installed._get_installed_version() is None

    def test_handles_timeout(self, tmp_path: Path):
        """Should return None on subprocess timeout."""
        with patch.object(ensure_installed, "VENV_DIR", tmp_path):
            with patch.object(ensure_installed, "_python_bin") as mock_bin:
                mock_bin.return_value = tmp_path / "bin" / "python"
                (tmp_path / "bin").mkdir()
                (tmp_path / "bin" / "python").touch()

                with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
                    assert ensure_installed._get_installed_version() is None


class TestPythonBin:
    """Tests for _python_bin()."""

    def test_unix_path(self):
        """Should return bin/python on Unix."""
        with patch("sys.platform", "linux"):
            result = ensure_installed._python_bin()
            assert result.name == "python"
            assert "bin" in str(result)

    def test_windows_path(self):
        """Should return Scripts/python.exe on Windows."""
        with patch("sys.platform", "win32"):
            result = ensure_installed._python_bin()
            assert result.name == "python.exe"
            assert "Scripts" in str(result)


class TestMainCheckOnly:
    """Tests for main() in --check-only mode."""

    def test_check_only_installed_returns_0(self):
        """Should exit 0 when pr-agent is installed."""
        with patch.object(ensure_installed, "_get_installed_version", return_value="0.35.0"):
            with patch("sys.argv", ["ensure_installed.py", "--check-only", "--json"]):
                assert ensure_installed.main() == 0

    def test_check_only_missing_returns_1(self):
        """Should exit 1 when pr-agent is not installed."""
        with patch.object(ensure_installed, "_get_installed_version", return_value=None):
            with patch("sys.argv", ["ensure_installed.py", "--check-only", "--json"]):
                assert ensure_installed.main() == 1

    def test_check_only_json_output_shape(self, capsys):
        """Should output valid JSON with expected keys."""
        with patch.object(ensure_installed, "_get_installed_version", return_value="0.35.0"):
            with patch("sys.argv", ["ensure_installed.py", "--check-only", "--json"]):
                ensure_installed.main()
                output = json.loads(capsys.readouterr().out)
                assert output["installed"] is True
                assert output["version"] == "0.35.0"
                assert "venv_path" in output

    def test_check_only_missing_json_output_shape(self, capsys):
        """Should output JSON with installed=False when missing."""
        with patch.object(ensure_installed, "_get_installed_version", return_value=None):
            with patch("sys.argv", ["ensure_installed.py", "--check-only", "--json"]):
                ensure_installed.main()
                output = json.loads(capsys.readouterr().out)
                assert output["installed"] is False
                assert output["version"] is None


class TestMainInstall:
    """Tests for main() install flow."""

    def test_install_success(self, capsys):
        """Should install and exit 0 on success."""
        with patch.object(
            ensure_installed,
            "_get_installed_version",
            side_effect=[None, "0.35.0"],  # first call: not installed, second: installed
        ):
            with patch.object(ensure_installed, "_python_bin") as mock_bin:
                mock_bin.return_value = Path("/fake/bin/python")
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(ensure_installed, "_install_pr_agent", return_value=True):
                        with patch("sys.argv", ["ensure_installed.py", "--json"]):
                            result = ensure_installed.main()
                            assert result == 0

    def test_install_failure_returns_2(self):
        """Should exit 2 when installation fails."""
        with patch.object(ensure_installed, "_get_installed_version", return_value=None):
            with patch.object(ensure_installed, "_python_bin") as mock_bin:
                mock_bin.return_value = Path("/fake/bin/python")
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(ensure_installed, "_install_pr_agent", return_value=False):
                        with patch("sys.argv", ["ensure_installed.py"]):
                            assert ensure_installed.main() == 2
