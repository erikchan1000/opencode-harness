#!/usr/bin/env python3
"""Run pr-agent review and capture output.

Invokes pr-agent CLI in local-stdout mode (publish_output=false) with
inline config overrides via CLI arguments.

Usage:
    # Review a remote PR
    python run_review.py --pr-url https://github.com/owner/repo/pull/123 --command review

    # Review local branch diff against main (works from worktrees + dirty trees)
    python run_review.py --local --command review

    # With extra instructions
    python run_review.py --local --command review \
        --extra-instructions "Focus on HIPAA compliance and PHI exposure"

Environment variables:
    PR_AGENT_MODEL       — LLM model (default: anthropic/claude-opus-5-5).
                           Must either be registered in pr-agent's MAX_TOKENS
                           table or be paired with PR_AGENT_MODEL_MAX_TOKENS;
                           the script validates and lists options on mismatch.
    PR_AGENT_MODEL_MAX_TOKENS
                         — Input-window size (tokens) for a model pr-agent
                           doesn't know about, passed through as
                           config.custom_model_max_tokens. Defaults to
                           1_000_000 for the default model only; required
                           when overriding PR_AGENT_MODEL with anything else
                           unregistered.
    PR_AGENT_TEMPERATURE — Sampling temperature passed to the model
                           (default: 1). Newer Anthropic models REJECT
                           pr-agent's built-in 0.2 default with
                           "temperature is deprecated for this model", so 1
                           is the safe default; override only if your model
                           accepts it.
    OPENAI_KEY           — OpenAI API key (for OpenAI models)
    ANTHROPIC_KEY        — Anthropic API key (for Claude models)
    PR_AGENT_SECRETS     — Path to .secrets.toml (optional)

Exit codes:
    0 — review completed successfully
    1 — pr-agent error (non-zero exit)
    2 — configuration error (missing key, bad args, unregistered model)
    3 — no diff found (nothing to review)

Large-PR note: GitHub's API refuses diffs beyond ~300 files / ~20k lines
with HTTP 406, which pr-agent surfaces as "PR has no files". When that
happens on a --pr-url run and the current checkout is on the PR's head
branch, this script automatically falls back to --local mode against the
PR's base branch.

Local-mode mechanics: pr-agent's LocalGitProvider requires (a) `.git` to be
a DIRECTORY — git worktrees have a `.git` file and fail root discovery —
(b) a clean tree, and (c) the base branch to exist as a LOCAL branch. To
satisfy all three uniformly, --local runs against a throwaway
`git clone --local` of the repo in a temp dir (cheap: hardlinked objects),
checked out at the current branch's HEAD commit. Uncommitted changes are
therefore NOT reviewed — the script warns when the tree is dirty.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "templates"
VENV_DIR = Path.home() / ".local" / "share" / "opencode-harness" / "pr-agent-venv"

# Opus 5.5 is the strongest reviewer available and carries a 1M-token input
# window — the difference between a pruned review and a full one on
# multi-wave harness PRs. It is NOT in pr-agent 0.35.0's MAX_TOKENS table
# (that release predates it), so it only works with an explicit
# custom_model_max_tokens; see DEFAULT_MODEL_MAX_TOKENS below.
DEFAULT_MODEL = "anthropic/claude-opus-5-5"
# Input-window size for DEFAULT_MODEL, matching litellm's model_cost entry
# (max_input_tokens = 1_000_000). Only consulted when the model is absent
# from pr-agent's registry.
DEFAULT_MODEL_MAX_TOKENS = 1_000_000
DEFAULT_TEMPERATURE = "1"
SUPPORTED_COMMANDS = ("review", "improve", "describe", "ask")

# pr-agent surfaces GitHub's HTTP 406 (diff too large for the API) as this
# log line and exits 0 — a silent no-op unless we detect it.
_NO_FILES_MARKER = "PR has no files"


def _venv_python() -> Path:
    """Return path to the venv Python."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _resolve_model() -> str:
    """Resolve the LLM model from env or default."""
    return os.environ.get("PR_AGENT_MODEL", DEFAULT_MODEL)


def _resolve_model_max_tokens(model: str) -> int | None:
    """Input-window size to hand pr-agent as custom_model_max_tokens.

    Only needed for models missing from pr-agent's MAX_TOKENS registry.
    Returns None when no authoritative number is known — the validator then
    refuses rather than inventing a window size, since a wrong number either
    truncates the diff silently or overruns the model's context.
    """
    raw = os.environ.get("PR_AGENT_MODEL_MAX_TOKENS")
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            raise ValueError(
                f"PR_AGENT_MODEL_MAX_TOKENS={raw!r} is not an integer"
            ) from None
        if parsed <= 0:
            raise ValueError(
                f"PR_AGENT_MODEL_MAX_TOKENS={raw!r} must be positive"
            )
        return parsed
    if model == DEFAULT_MODEL:
        return DEFAULT_MODEL_MAX_TOKENS
    return None


def _validate_model_registered(python: Path, model: str,
                               custom_max_tokens: int | None) -> str | None:
    """Check pr-agent can determine a token budget for the model.

    pr-agent hard-fails mid-review ("Model X is not defined in MAX_TOKENS")
    for unregistered model strings, after burning the diff-fetch work. Catch
    it up front. An unregistered model is fine when we supply
    custom_model_max_tokens. Returns an error message, or None if OK.
    """
    probe = (
        "from pr_agent.algo import MAX_TOKENS; import sys; "
        f"m={model!r}; "
        "ok = m in MAX_TOKENS; "
        "print('OK' if ok else 'MISSING'); "
        "sys.exit(0)"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", probe],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None  # probe unavailable — let pr-agent be the judge
    if "MISSING" not in result.stdout:
        return None
    if custom_max_tokens is not None:
        return None  # unregistered, but we pass an explicit window size
    # Build a helpful suggestion list.
    listing = subprocess.run(
        [str(python), "-c",
         "from pr_agent.algo import MAX_TOKENS; "
         "print('\\n'.join(sorted(k for k in MAX_TOKENS "
         "if k.startswith('anthropic/'))))"],
        capture_output=True, text=True, timeout=30,
    )
    options = listing.stdout.strip() or "(could not enumerate)"
    return (
        f"model {model!r} is not in pr-agent's MAX_TOKENS registry — the "
        f"review would fail after the diff fetch. Either set "
        f"PR_AGENT_MODEL_MAX_TOKENS to the model's input-window size, or "
        f"pick a registered anthropic/ option:\n{options}"
    )


SECRETS_PATH = Path.home() / ".pr_agent_secrets.toml"


def _resolve_github_token() -> str | None:
    """Try to get a GitHub token from gh CLI or secrets file."""
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


def _git(args: list[str], cwd: Path | None = None) -> str | None:
    """Run a git command, returning stripped stdout or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=60, cwd=cwd,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _check_has_diff(base_branch: str) -> bool:
    """Check if there are any changes between HEAD and base branch."""
    # Try the local branch first, then origin/<base> — a worktree checkout
    # often has no local base branch ref of its own.
    for ref in (base_branch, f"origin/{base_branch}"):
        out = _git(["diff", "--stat", f"{ref}...HEAD"])
        if out is not None:
            return bool(out)
    return False


def _prepare_local_clone(base_branch: str) -> tuple[Path, str] | None:
    """Create a throwaway local clone satisfying LocalGitProvider's needs.

    Returns (clone_path, base_branch_name) or None on failure. The caller
    is responsible for deleting the clone directory.

    Why a clone instead of running in place (each is a hard failure mode
    of pr-agent's LocalGitProvider, observed 2026-08-29):
      - worktrees: `.git` is a file, and the provider's root discovery
        requires a `.git` DIRECTORY;
      - dirty trees: the provider refuses with "repository is not in a
        clean state";
      - missing local base: the provider indexes `repo.heads`, so an
        origin-only base branch raises KeyError.
    A `git clone --local` is cheap (hardlinked objects) and neutralizes
    all three at once.
    """
    # --show-toplevel works in both plain checkouts and worktrees.
    repo_root = _git(["rev-parse", "--show-toplevel"])
    if not repo_root:
        print("error: --local requires running inside a git repo", file=sys.stderr)
        return None

    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if not branch or branch == "HEAD":
        print("error: --local requires a checked-out branch (not detached HEAD)",
              file=sys.stderr)
        return None

    if _git(["status", "--porcelain"]):
        print(
            "warning: working tree is dirty — --local reviews the HEAD "
            "commit; uncommitted changes are NOT included.",
            file=sys.stderr,
        )

    clone_dir = Path(tempfile.mkdtemp(prefix="pr-review-clone-"))
    if _git(["clone", "--quiet", "--local", repo_root, str(clone_dir)]) is None:
        print("error: git clone --local failed", file=sys.stderr)
        shutil.rmtree(clone_dir, ignore_errors=True)
        return None

    if _git(["checkout", "--quiet", branch], cwd=clone_dir) is None:
        print(f"error: could not check out {branch!r} in the review clone",
              file=sys.stderr)
        shutil.rmtree(clone_dir, ignore_errors=True)
        return None

    # Ensure the base exists as a LOCAL branch in the clone.
    if _git(["rev-parse", "--verify", f"refs/heads/{base_branch}"],
            cwd=clone_dir) is None:
        if _git(["branch", base_branch, f"origin/{base_branch}"],
                cwd=clone_dir) is None:
            print(
                f"error: base branch {base_branch!r} not found locally or on "
                f"origin in the review clone",
                file=sys.stderr,
            )
            shutil.rmtree(clone_dir, ignore_errors=True)
            return None

    return clone_dir, base_branch


def _build_cmd(python: Path, pr_url: str, command: str, model: str,
               extra_instructions: str,
               custom_max_tokens: int | None) -> list[str]:
    """Assemble the pr_agent.cli invocation.

    NOTE: git_provider must be set via the CONFIG__GIT_PROVIDER env var,
    never via --config.git_provider — pr-agent selects the provider inside
    apply_repo_settings() BEFORE CLI config args are applied, so the CLI
    form arrives too late and the github provider chokes on a branch name.
    """
    temperature = os.environ.get("PR_AGENT_TEMPERATURE", DEFAULT_TEMPERATURE)
    cmd = [
        str(python), "-m", "pr_agent.cli",
        f"--pr_url={pr_url}",
        command,
        f"--config.model={model}",
        # Newer Anthropic models reject pr-agent's 0.2 default outright
        # ("temperature is deprecated for this model") — see module doc.
        f"--config.temperature={temperature}",
        "--config.publish_output=false",
        # verbosity=2 is required so PR-Agent logs the review YAML
        # to its output (our capture channel). Without it, the review
        # is generated but never printed when publish_output=false.
        "--config.verbosity_level=2",
        f"--config.fallback_models=[\"{model}\"]",
        "--pr_reviewer.require_score_review=true",
        "--pr_reviewer.require_tests_review=true",
        "--pr_reviewer.require_security_review=true",
        "--pr_reviewer.require_estimate_effort_to_review=true",
        "--pr_reviewer.num_max_findings=10",
    ]
    if custom_max_tokens is not None:
        # Required for models pr-agent 0.35.0 doesn't ship in MAX_TOKENS
        # (e.g. claude-opus-5-5). Ignored when the model IS registered —
        # get_max_tokens() prefers the registry entry.
        cmd.append(f"--config.custom_model_max_tokens={custom_max_tokens}")
    if extra_instructions:
        cmd.append(f"--pr_reviewer.extra_instructions={extra_instructions}")
    return cmd


def _run_pr_agent(cmd: list[str], env: dict[str, str],
                  cwd: Path | None = None) -> tuple[int, str, str]:
    """Run pr-agent, returning (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,  # 15 min — big local diffs take a while
            env=env,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return (1, "", "error: pr-agent timed out after 900s")
    return (result.returncode, result.stdout, result.stderr)


def _pr_base_and_head(pr_url: str) -> tuple[str, str] | None:
    """Look up a PR's base and head branch names via gh."""
    if not shutil.which("gh"):
        return None
    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_url, "--json", "baseRefName,headRefName",
             "-q", ".baseRefName + \" \" + .headRefName"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None
    return (parts[0], parts[1])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pr-agent review")
    parser.add_argument(
        "--pr-url",
        help="PR URL to review (e.g., https://github.com/owner/repo/pull/123)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Review local branch diff instead of a remote PR "
             "(works from worktrees and dirty trees via a temp clone)",
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
    try:
        custom_max_tokens = _resolve_model_max_tokens(model)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    model_error = _validate_model_registered(python, model, custom_max_tokens)
    if model_error:
        print(f"error: {model_error}", file=sys.stderr)
        return 2
    api_key_info = _resolve_api_key(model)
    if not api_key_info:
        print(
            "error: no LLM API key found. Set one of: "
            "OPENAI_KEY, ANTHROPIC_KEY, GROQ_API_KEY, DEEPSEEK_KEY "
            "or add keys to ~/.pr_agent_secrets.toml",
            file=sys.stderr,
        )
        return 2

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

    def run_local(base_branch: str) -> int:
        if not _check_has_diff(base_branch):
            print(f"No diff found between {base_branch} and HEAD.",
                  file=sys.stderr)
            return 3
        prepared = _prepare_local_clone(base_branch)
        if prepared is None:
            return 2
        clone_dir, base = prepared
        try:
            local_env = env.copy()
            local_env["CONFIG__GIT_PROVIDER"] = "local"
            cmd = _build_cmd(python, base, args.command, model,
                             args.extra_instructions, custom_max_tokens)
            print(
                f"Running: pr-agent {args.command} (model={model}, "
                f"provider=local, base={base}, clone={clone_dir})",
                file=sys.stderr,
            )
            code, out, err = _run_pr_agent(cmd, local_env, cwd=clone_dir)
            if err:
                print(err, file=sys.stderr)
            # The review YAML rides the verbosity-2 log stream on stdout;
            # print it verbatim for parse_output.py.
            print(out)
            if code != 0:
                print(f"error: pr-agent exited with code {code}",
                      file=sys.stderr)
                return 1
            return 0
        finally:
            shutil.rmtree(clone_dir, ignore_errors=True)

    # ---- local mode ----
    if args.local:
        return run_local(args.base_branch)

    # ---- remote mode ----
    cmd = _build_cmd(python, args.pr_url, args.command, model,
                     args.extra_instructions, custom_max_tokens)
    print(
        f"Running: pr-agent {args.command} (model={model}, "
        f"provider={provider})",
        file=sys.stderr,
    )
    code, out, err = _run_pr_agent(cmd, env)
    combined = out + "\n" + err

    # GitHub returns HTTP 406 for diffs beyond ~300 files / ~20k lines;
    # pr-agent logs "PR has no files" and exits 0. Fall back to local mode
    # when the current checkout is on the PR's head branch.
    if _NO_FILES_MARKER in combined:
        print(
            "warning: GitHub API refused the PR diff (usually >20k lines / "
            ">300 files → HTTP 406). Attempting local-clone fallback...",
            file=sys.stderr,
        )
        refs = _pr_base_and_head(args.pr_url)
        current = _git(["rev-parse", "--abbrev-ref", "HEAD"])
        if refs and current == refs[1]:
            return run_local(refs[0])
        print(
            "error: cannot auto-fallback — check out the PR's head branch "
            "and re-run with --local --base-branch <base>.",
            file=sys.stderr,
        )
        return 1

    if err:
        print(err, file=sys.stderr)
    print(out)
    if code != 0:
        print(f"error: pr-agent exited with code {code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
