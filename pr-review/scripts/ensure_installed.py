#!/usr/bin/env python3
"""Ensure pr-agent is installed in an isolated venv.

Usage:
    python ensure_installed.py [--check-only] [--json] [--version VERSION]

Exit codes:
    0 — pr-agent is installed and ready
    1 — not installed (--check-only mode)
    2 — installation failed
"""

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

VENV_DIR = Path.home() / ".local" / "share" / "opencode-harness" / "pr-agent-venv"
DEFAULT_VERSION = "0.35.0"


def _python_bin() -> Path:
    """Return the path to the venv's Python binary."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _get_installed_version() -> str | None:
    """Return the installed pr-agent version, or None if not installed."""
    python = _python_bin()
    if not python.exists():
        return None
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "show", "pr-agent"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _create_venv() -> bool:
    """Create the isolated venv. Returns True on success."""
    try:
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        venv.create(str(VENV_DIR), with_pip=True, clear=True)
        return _python_bin().exists()
    except Exception as exc:
        print(f"error: failed to create venv at {VENV_DIR}: {exc}", file=sys.stderr)
        return False


def _install_pr_agent(version: str) -> bool:
    """Install pr-agent into the venv. Returns True on success."""
    python = _python_bin()
    pkg = f"pr-agent=={version}" if version else "pr-agent"
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", pkg],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"error: pip install failed:\n{result.stderr}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print("error: pip install timed out after 300s", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure pr-agent is installed")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check without installing; exit 1 if missing",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )
    parser.add_argument(
        "--version",
        default=os.environ.get("PR_AGENT_VERSION", DEFAULT_VERSION),
        help=f"pr-agent version to install (default: {DEFAULT_VERSION})",
    )
    args = parser.parse_args()

    installed_version = _get_installed_version()

    if installed_version:
        result = {
            "installed": True,
            "version": installed_version,
            "venv_path": str(VENV_DIR),
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"pr-agent {installed_version} is installed at {VENV_DIR}")
        return 0

    if args.check_only:
        result = {
            "installed": False,
            "version": None,
            "venv_path": str(VENV_DIR),
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"pr-agent is not installed (venv: {VENV_DIR})")
        return 1

    # Install
    print(f"Installing pr-agent {args.version} into {VENV_DIR}...", file=sys.stderr)

    if not _python_bin().exists():
        if not _create_venv():
            return 2

    if not _install_pr_agent(args.version):
        return 2

    installed_version = _get_installed_version()
    if not installed_version:
        print("error: installation appeared to succeed but version check failed", file=sys.stderr)
        return 2

    result = {
        "installed": True,
        "version": installed_version,
        "venv_path": str(VENV_DIR),
    }
    if args.json:
        print(json.dumps(result))
    else:
        print(f"pr-agent {installed_version} installed at {VENV_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
