"""Tests for parse_output.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pr-review" / "scripts"))
import parse_output


class TestExtractScore:
    """Tests for _extract_score()."""

    def test_score_with_slash(self):
        assert parse_output._extract_score("Score: 3/5") == 3

    def test_confidence_with_slash(self):
        assert parse_output._extract_score("Confidence: 4/5") == 4

    def test_score_without_slash(self):
        assert parse_output._extract_score("score: 2") == 2

    def test_case_insensitive(self):
        assert parse_output._extract_score("SCORE: 5/5") == 5

    def test_no_score(self):
        assert parse_output._extract_score("No score here") is None

    def test_score_in_context(self):
        text = "### Review\nSome text\nScore: 3/5\nMore text"
        assert parse_output._extract_score(text) == 3


class TestExtractFindings:
    """Tests for _extract_findings() with table-format input."""

    def test_table_findings(self, sample_review_output: str):
        """Should extract all 5 findings from the sample output."""
        findings = parse_output._extract_findings(sample_review_output)
        assert len(findings) >= 5

    def test_finding_has_required_fields(self, sample_review_output: str):
        """Each finding should have all required keys."""
        findings = parse_output._extract_findings(sample_review_output)
        required_keys = {"severity", "category", "file", "line", "problem", "fix"}
        for f in findings:
            assert required_keys.issubset(f.keys()), f"Missing keys in {f}"

    def test_severity_normalization(self, sample_review_output: str):
        """Severities should be normalized to standard values."""
        findings = parse_output._extract_findings(sample_review_output)
        valid_severities = {"critical", "high", "medium", "low", "info"}
        for f in findings:
            assert f["severity"] in valid_severities, f"Bad severity: {f['severity']}"

    def test_critical_finding_extracted(self, sample_review_output: str):
        """Should find the critical security finding."""
        findings = parse_output._extract_findings(sample_review_output)
        critical = [f for f in findings if f["severity"] == "critical"]
        assert len(critical) >= 1
        assert any("token" in f["problem"].lower() or "jwt" in f["problem"].lower() for f in critical)

    def test_empty_input(self):
        """Should return empty list for empty input."""
        assert parse_output._extract_findings("") == []

    def test_no_findings_text(self):
        """Should return empty list for text with no findings."""
        assert parse_output._extract_findings("Everything looks good!") == []


class TestParseFileLine:
    """Tests for _parse_file_line()."""

    def test_file_with_line(self):
        assert parse_output._parse_file_line("src/foo.ts:42") == ("src/foo.ts", 42)

    def test_file_without_line(self):
        assert parse_output._parse_file_line("src/foo.ts") == ("src/foo.ts", None)

    def test_file_with_line_in_parens(self):
        assert parse_output._parse_file_line("src/foo.ts (line 42)") == ("src/foo.ts", 42)

    def test_file_with_lines_range(self):
        path, line = parse_output._parse_file_line("src/foo.ts (lines 42-50)")
        assert path == "src/foo.ts"
        assert line == 42

    def test_backtick_stripped(self):
        assert parse_output._parse_file_line("`src/foo.ts:42`") == ("src/foo.ts", 42)

    def test_empty_string(self):
        assert parse_output._parse_file_line("") == ("", None)


class TestNormalizeSeverity:
    """Tests for _normalize_severity()."""

    def test_critical_variants(self):
        for s in ("Critical", "CRITICAL", "blocker", "Bug"):
            assert parse_output._normalize_severity(s) == "critical"

    def test_high_variants(self):
        for s in ("High", "Major", "important", "Error"):
            assert parse_output._normalize_severity(s) == "high"

    def test_medium_variants(self):
        for s in ("Medium", "moderate", "Warning"):
            assert parse_output._normalize_severity(s) == "medium"

    def test_low_variants(self):
        for s in ("Low", "Minor", "nit", "Nitpick", "suggestion"):
            assert parse_output._normalize_severity(s) == "low"

    def test_unknown_defaults_to_medium(self):
        assert parse_output._normalize_severity("something-else") == "medium"


class TestInferSeverity:
    """Tests for _infer_severity()."""

    def test_security_keywords(self):
        assert parse_output._infer_severity("SQL injection vulnerability") == "critical"
        assert parse_output._infer_severity("XSS attack vector") == "critical"

    def test_crash_keywords(self):
        assert parse_output._infer_severity("Null pointer crash") == "high"
        assert parse_output._infer_severity("Unhandled exception") == "high"

    def test_performance_keywords(self):
        assert parse_output._infer_severity("N+1 query pattern") == "medium"

    def test_generic_text(self):
        assert parse_output._infer_severity("Rename variable for clarity") == "low"


class TestFormatJson:
    """Tests for format_json()."""

    def test_valid_json_output(self):
        result = parse_output.format_json(3, [{"severity": "high", "file": "x.ts", "line": 1, "problem": "bad", "fix": "fix"}])
        parsed = json.loads(result)
        assert parsed["score"] == 3
        assert parsed["count"] == 1
        assert len(parsed["findings"]) == 1

    def test_empty_findings(self):
        result = parse_output.format_json(5, [])
        parsed = json.loads(result)
        assert parsed["count"] == 0
        assert parsed["findings"] == []

    def test_null_score(self):
        result = parse_output.format_json(None, [])
        parsed = json.loads(result)
        assert parsed["score"] is None


class TestFormatCaveman:
    """Tests for format_caveman()."""

    def test_single_finding(self):
        result = parse_output.format_caveman(3, [{
            "severity": "critical",
            "file": "src/auth.ts",
            "line": 42,
            "problem": "JWT not verified",
            "fix": "Add jwt.verify()",
        }])
        assert "src/auth.ts:L42" in result
        assert "bug:" in result
        assert "JWT not verified" in result

    def test_score_header(self):
        result = parse_output.format_caveman(4, [])
        assert "Score: 4/5" in result

    def test_no_score(self):
        result = parse_output.format_caveman(None, [])
        assert "Score:" not in result

    def test_missing_line_number(self):
        result = parse_output.format_caveman(None, [{
            "severity": "low",
            "file": "readme.md",
            "line": None,
            "problem": "Typo",
            "fix": "",
        }])
        assert "readme.md:" in result
        assert ":L" not in result  # No line number prefix


class TestFormatMarkdown:
    """Tests for format_markdown()."""

    def test_table_header(self):
        result = parse_output.format_markdown(3, [{
            "severity": "high",
            "file": "x.ts",
            "line": 1,
            "problem": "bad",
            "fix": "fix",
        }])
        assert "| Severity |" in result
        assert "| high |" in result

    def test_empty_findings(self):
        result = parse_output.format_markdown(5, [])
        assert "No findings" in result

    def test_score_displayed(self):
        result = parse_output.format_markdown(3, [])
        assert "3/5" in result


class TestEndToEnd:
    """End-to-end tests using the sample fixture."""

    def test_full_pipeline_json(self, sample_review_output: str):
        """Parse sample output and verify JSON format."""
        score = parse_output._extract_score(sample_review_output)
        findings = parse_output._extract_findings(sample_review_output)
        result = json.loads(parse_output.format_json(score, findings))

        assert result["score"] == 3
        assert result["count"] >= 5
        assert all("severity" in f for f in result["findings"])
        assert all("file" in f for f in result["findings"])

    def test_full_pipeline_caveman(self, sample_review_output: str):
        """Parse sample output and verify caveman format."""
        score = parse_output._extract_score(sample_review_output)
        findings = parse_output._extract_findings(sample_review_output)
        result = parse_output.format_caveman(score, findings)

        assert "Score: 3/5" in result
        assert "bug:" in result  # critical finding
        lines = [l for l in result.strip().split("\n") if l.strip() and "Score" not in l]
        assert len(lines) >= 5

    def test_full_pipeline_markdown(self, sample_review_output: str):
        """Parse sample output and verify markdown format."""
        score = parse_output._extract_score(sample_review_output)
        findings = parse_output._extract_findings(sample_review_output)
        result = parse_output.format_markdown(score, findings)

        assert "3/5" in result
        assert "| Severity |" in result
        assert "critical" in result
