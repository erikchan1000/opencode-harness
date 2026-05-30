#!/usr/bin/env python3
"""Run pr-agent review and capture output.

Invokes pr-agent CLI in local-stdout mode (publish_output=false), merging
the default template config with any repo-local .pr_agent.toml overrides
and CLI arguments.

Usage:
    # Review a remote PR
    python run_review.py --pr-url https://github.com/owner/repo/pull/123 --command review

    # Review local branch diff against main
    python run_review.py --local --command review

    # With extra instructions
    python run_review.py --local --command review \
        --extra-instructions "Focus on HIPAA compliance and PHI exposure"

    # JSON output (wraps pr-agent output + metadata)
    python run_review.py --local --command review --json

Environment variables:
    PR_AGENT_MODEL       — LLM model (default: anthropic/claude-sonnet-4-20250514)
    OPENAI_KEY           — OpenAI API key (for OpenAI models)
    ANTHROPIC_KEY        — Anthropic API key (for Claude models)
    PR_AGENT_SECRETS     — Path to .secrets.toml (optional)

Exit codes:
    0 — review completed successfully
    1 — pr-agent error (non-zero exit)
    2 — configuration error (missing key, bad args)
    3 — no diff found (nothing to review)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "templates"
VENV_DIR = Path.home() / ".local" / "share" / "opencode-harness" / "pr-agent-venv"

DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"
SUPPORTED_COMMANDS = ("review", "improve", "describe", "ask")


def _venv_python() -> Path:
    """Return path to the venv Python."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _resolve_model() -> str:
    """Resolve the LLM model from env or default."""
    return os.environ.get("PR_AGENT_MODEL", DEFAULT_MODEL)


def _resolve_api_key(model: str) -> tuple[str, str] | None:
    """Resolve the API key for the given model.

    Returns (key_name, key_value) or None if not found.
    """
    model_lower = model.lower()

    # Anthropic models
    if "anthropic" in model_lower or "claude" in model_lower:
        key = os.environ.get("ANTHROPIC_KEY")
        if key:
            return ("anthropic", key)

    # OpenAI models (default)
    key = os.environ.get("OPENAI_KEY")
    if key:
        return ("openai", key)

    # Fallback: check for any known key
    for env_var, provider in [
        ("ANTHROPIC_KEY", "anthropic"),
        ("OPENAI_KEY", "openai"),
        ("GROQ_API_KEY", "groq"),
        ("DEEPSEEK_KEY", "deepseek"),
    ]:
        key = os.environ.get(env_var)
        if key:
            return (provider, key)

    return None


def _build_config(
    model: str,
    api_key_info: tuple[str, str],
    command: str,
    extra_instructions: str,
    local_mode: bool,
    repo_config: Path | None,
) -> str:
    """Build a merged .pr_agent.toml config string."""
    provider, key = api_key_info

    lines = [
        "[config]",
        f'model = "{model}"',
        "publish_output = false",
        "verbosity_level = 0",
    ]

    if local_mode:
        lines.append('git_provider = "local"')
    else:
        lines.append('git_provider = "github"')

    lines.append("")

    # Secrets section
    if provider == "openai":
        lines.extend(["[openai]", f'key = "{key}"'])
    elif provider == "anthropic":
        lines.extend(["[anthropic]", f'KEY = "{key}"'])
    elif provider == "groq":
        lines.extend(["[groq]", f'key = "{key}"'])
    elif provider == "deepseek":
        lines.extend(["[deepseek]", f'key = "{key}"'])
    lines.append("")

    # Reviewer config
    lines.extend([
        "[pr_reviewer]",
        "require_score_review = true",
        "require_tests_review = true",
        "require_security_review = true",
        "require_estimate_effort_to_review = true",
        "num_max_findings = 10",
        "persistent_comment = false",
    ])

    if extra_instructions:
        # Escape quotes in instructions
        escaped = extra_instructions.replace('"', '\\"')
        lines.append(f'extra_instructions = "{escaped}"')
    lines.append("")

    # Code suggestions config
    lines.extend([
        "[pr_code_suggestions]",
        "num_code_suggestions_per_chunk = 4",
        "max_number_of_calls = 3",
        "focus_only_on_problems = true",
    ])

    return "\n".join(lines)


def _get_local_pr_url() -> str | None:
    """Derive a PR URL from the current branch's upstream, or return None."""
    try:
        # Get the remote URL
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        remote_url = result.stdout.strip()

        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()

        # Try to find an open PR for this branch
        if shutil.which("gh"):
            result = subprocess.run(
                ["gh", "pr", "view", branch, "--json", "url", "-q", ".url"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _check_has_diff(base_branch: str) -> bool:
    """Check if there are any changes between HEAD and base branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}...HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pr-agent review")
    parser.add_argument(
        "--pr-url",
        help="PR URL to review (e.g., https://github.com/owner/repo/pull/123)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Review local branch diff instead of a remote PR",
    )
    parser.add_argument(
        "--base-branch",
        default="main",
        help="Base branch for local diff comparison (default: main)",
    )
    parser.add_argument(
        "--command",
        choices=SUPPORTED_COMMANDS,
        default="review",
        help="PR-Agent command to run (default: review)",
    )
    parser.add_argument(
        "--extra-instructions",
        default="",
        help="Extra review instructions (e.g., 'Focus on HIPAA compliance')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Wrap output in JSON with metadata",
    )
    args = parser.parse_args()

    # Validate args
    if not args.pr_url and not args.local:
        print("error: must specify --pr-url or --local", file=sys.stderr)
        return 2

    # Check pr-agent is installed
    python = _venv_python()
    if not python.exists():
        print(
            "error: pr-agent is not installed. "
            "Run ensure_installed.py first.",
            file=sys.stderr,
        )
        return 2

    # Resolve model and API key
    model = _resolve_model()
    api_key_info = _resolve_api_key(model)
    if not api_key_info:
        print(
            "error: no LLM API key found. Set one of: "
            "OPENAI_KEY, ANTHROPIC_KEY, GROQ_API_KEY, DEEPSEEK_KEY",
            file=sys.stderr,
        )
        return 2

    # Determine PR URL
    pr_url = args.pr_url
    if args.local:
        if not _check_has_diff(args.base_branch):
            print(f"No diff found between {args.base_branch} and HEAD.", file=sys.stderr)
            return 3

        pr_url = _get_local_pr_url()
        if not pr_url:
            # Fall back to a dummy URL for local mode
            pr_url = "https://github.com/local/repo/pull/0"

    # Build config
    config_content = _build_config(
        model=model,
        api_key_info=api_key_info,
        command=args.command,
        extra_instructions=args.extra_instructions,
        local_mode=args.local,
        repo_config=None,
    )

    # Write temp config and run pr-agent
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", prefix="pr_agent_", delete=False
    ) as f:
        f.write(config_content)
        config_path = f.name

    try:
        cmd = [
            str(python), "-m", "pr_agent.cli",
            f"--pr_url={pr_url}",
            args.command,
        ]

        env = os.environ.copy()
        env["CONFIG_PATH"] = config_path

        print(
            f"Running: pr-agent {args.command} (model={model}, "
            f"provider={api_key_info[0]})",
            file=sys.stderr,
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
            env=env,
        )

        output = result.stdout
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            print(
                f"error: pr-agent exited with code {result.returncode}",
                file=sys.stderr,
            )
            if args.json:
                print(json.dumps({
                    "success": False,
                    "exit_code": result.returncode,
                    "output": output,
                    "error": result.stderr,
                    "model": model,
                    "command": args.command,
                }))
            elif output:
                print(output)
            return 1

        if args.json:
            print(json.dumps({
                "success": True,
                "exit_code": 0,
                "output": output,
                "model": model,
                "command": args.command,
                "pr_url": pr_url,
            }))
        else:
            print(output)

        return 0

    except subprocess.TimeoutExpired:
        print("error: pr-agent timed out after 600s", file=sys.stderr)
        return 1
    finally:
        try:
            os.unlink(config_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
