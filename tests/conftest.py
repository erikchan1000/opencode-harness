"""Shared fixtures for pr-review tests."""

import sys
from pathlib import Path

import pytest

# Add scripts to path for direct imports in tests
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "pr-review" / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_review_output(fixtures_dir: Path) -> str:
    """Load the sample pr-agent review output."""
    return (fixtures_dir / "sample_review_output.md").read_text()


@pytest.fixture
def sample_diff(fixtures_dir: Path) -> str:
    """Load the sample diff patch."""
    return (fixtures_dir / "sample_diff.patch").read_text()


@pytest.fixture
def scripts_dir() -> Path:
    """Path to the pr-review scripts directory."""
    return SCRIPTS_DIR
