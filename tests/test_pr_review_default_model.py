"""PR-Agent's default model must match the `review` role in roles.yaml.

PR-Agent takes its own litellm model id, so run_review.DEFAULT_MODEL stays a
literal (it is paired with DEFAULT_MODEL_MAX_TOKENS and cannot be read from a
role at runtime). Without this test only prose keeps it in sync with
roles.yaml, and a review-role change would silently leave PR-Agent on the old
model. Drift must fail CI.
"""
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "pr-review" / "scripts"))
import run_review

ROLES = yaml.safe_load((REPO / "roles.yaml").read_text())["roles"]


def drifted(default: str, roles: dict) -> str | None:
    review = roles["review"]
    if default == review:
        return None
    return (
        f"run_review.DEFAULT_MODEL {default!r} != roles.yaml roles.review {review!r}: "
        "update run_review.py DEFAULT_MODEL, DEFAULT_MODEL_MAX_TOKENS and "
        "skills/pr-review/SKILL.md together"
    )


def test_default_model_matches_review_role():
    message = drifted(run_review.DEFAULT_MODEL, ROLES)
    assert message is None, message


def test_drift_check_detects_a_changed_review_role():
    # Guards the comparison itself: a roles.yaml review change must be reported.
    mutated = dict(ROLES, review="anthropic/claude-sonnet-5-5")
    message = drifted(run_review.DEFAULT_MODEL, mutated)
    assert message is not None
    assert run_review.DEFAULT_MODEL in message
    assert "anthropic/claude-sonnet-5-5" in message
