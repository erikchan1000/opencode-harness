#!/usr/bin/env python3
"""Run pr-agent review and capture output.

Invokes pr-agent CLI in local-stdout mode (publish_output=false) with
inline config overrides via CLI arguments.

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
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "templates"
VENV_DIR = Path.home() / ".local" / "share" / "opencode-harness" / "pr-agent-venv"

DEFAULT_MODEL = "anthropic/claude-opus-4-6"
SUPPORTED_COMMANDS = ("review", "improve", "describe", "ask")


def _venv_python() -> Path:
    """Return path to the venv Python."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _resolve_model() -> str:
    """Resolve the LLM model from env or default."""
    return os.environ.get("PR_AGENT_MODEL", DEFAULT_MODEL)


SECRETS_PATH = Path.home() / ".pr_agent_secrets.toml"


def _resolve_github_token() -> str | None:
    """Try to get a GitHub token from gh CLI or secrets file."""
    import shutil

    # 1. Try gh CLI
    if shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # 2. Try secrets file
    secrets = _read_secrets_toml()
    return secrets.get("github", {}).get("user_token")



def _read_secrets_toml() -> dict[str, dict[str, str]]:
    """Read ~/.pr_agent_secrets.toml and return parsed sections.

    Expected format:
        [anthropic]
        KEY = "sk-ant-..."

        [openai]
        key = "sk-..."
    """
    if not SECRETS_PATH.exists():
        return {}
    try:
        # Minimal TOML parser — handles [section] + KEY = "value" lines.
        # Avoids adding a toml dependency.
        sections: dict[str, dict[str, str]] = {}
        current_section = ""
        for raw_line in SECRETS_PATH.read_text().splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1].strip().lower()
                sections.setdefault(current_section, {})
            elif "=" in stripped and current_section:
                k, _, rest = stripped.partition("=")
                rest = rest.strip()
                # Handle quoted values (preserves = signs inside quotes)
                if (rest.startswith('"') and rest.endswith('"')) or \
                   (rest.startswith("'") and rest.endswith("'")):
                    v = rest[1:-1]
                else:
                    v = rest
                sections[current_section][k.strip().lower()] = v
        return sections
    except OSError:
        return {}


_PROVIDER_ENV_VARS = [
    ("anthropic", "ANTHROPIC_KEY"),
    ("openai", "OPENAI_KEY"),
    ("groq", "GROQ_API_KEY"),
    ("deepseek", "DEEPSEEK_KEY"),
]


def _model_provider_hint(model: str) -> str | None:
    """Return the preferred provider name based on the model string."""
    model_lower = model.lower()
    if "anthropic" in model_lower or "claude" in model_lower:
        return "anthropic"
    if "gpt" in model_lower or "openai" in model_lower:
        return "openai"
    if "groq" in model_lower:
        return "groq"
    if "deepseek" in model_lower:
        return "deepseek"
    return None


def _resolve_api_key(model: str) -> tuple[str, str] | None:
    """Resolve the API key for the given model.

    Resolution order:
      1. Environment variable matching the model's provider
      2. Any available environment variable
      3. Secrets file entry matching the model's provider
      4. Any available secrets file entry

    Returns (provider_name, key_value) or None if not found.
    """
    hint = _model_provider_hint(model)

    # --- 1. Env var for the model's provider ---
    if hint:
        for provider, env_var in _PROVIDER_ENV_VARS:
            if provider == hint:
                key = os.environ.get(env_var)
                if key:
                    return (provider, key)

    # --- 2. Any env var ---
    for provider, env_var in _PROVIDER_ENV_VARS:
        key = os.environ.get(env_var)
        if key:
            return (provider, key)

    # --- 3. Secrets file for the model's provider ---
    secrets = _read_secrets_toml()

    if hint:
        key = secrets.get(hint, {}).get("key")
        if key:
            return (hint, key)

    # --- 4. Any secrets file entry ---
    for provider, _ in _PROVIDER_ENV_VARS:
        key = secrets.get(provider, {}).get("key")
        if key:
            return (provider, key)

    return None



def _get_local_pr_url() -> str | None:
    """Derive a PR URL from the current branch's upstream, or return None."""
    import shutil

    if not shutil.which("git"):
        return None

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
            "OPENAI_KEY, ANTHROPIC_KEY, GROQ_API_KEY, DEEPSEEK_KEY "
            "or add keys to ~/.pr_agent_secrets.toml",
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

    # Build CLI command with inline config overrides.
    # PR-Agent CLI reads --section.key=value via dynaconf. The format
    # --pr_reviewer.key=value (without config. prefix) is the documented
    # format: see https://docs.pr-agent.ai/usage-guide/configuration_options/
    cmd = [
        str(python), "-m", "pr_agent.cli",
        f"--pr_url={pr_url}",
        args.command,
        f"--config.model={model}",
        "--config.publish_output=false",
        # verbosity=2 is required so PR-Agent logs the review YAML
        # to stderr (our capture channel). Without it, the review
        # is generated but never output when publish_output=false.
        "--config.verbosity_level=2",
        f"--config.fallback_models=[\"{model}\"]",
        "--pr_reviewer.require_score_review=true",
        "--pr_reviewer.require_tests_review=true",
        "--pr_reviewer.require_security_review=true",
        "--pr_reviewer.require_estimate_effort_to_review=true",
        "--pr_reviewer.num_max_findings=10",
    ]

    if args.extra_instructions:
        cmd.append(f"--pr_reviewer.extra_instructions={args.extra_instructions}")

    # Set up env vars for secrets (dynaconf SECTION__KEY format)
    env = os.environ.copy()
    provider, key = api_key_info

    if provider == "anthropic":
        env["ANTHROPIC__KEY"] = key
    elif provider == "openai":
        env["OPENAI__KEY"] = key
    elif provider == "groq":
        env["GROQ__KEY"] = key
    elif provider == "deepseek":
        env["DEEPSEEK__KEY"] = key

    # GitHub token for PR access
    github_token = os.environ.get("GITHUB_TOKEN") or _resolve_github_token()
    if github_token:
        env["GITHUB__USER_TOKEN"] = github_token

    print(
        f"Running: pr-agent {args.command} (model={model}, "
        f"provider={api_key_info[0]})",
        file=sys.stderr,
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
            env=env,
        )
    except subprocess.TimeoutExpired:
        print("error: pr-agent timed out after 600s", file=sys.stderr)
        return 1

    output = result.stdout
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(
            f"error: pr-agent exited with code {result.returncode}",
            file=sys.stderr,
        )
        if output:
            print(output)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
