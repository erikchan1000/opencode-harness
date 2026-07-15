#!/usr/bin/env python3
"""Parse pr-agent review output into structured formats.

Reads pr-agent markdown output from stdin and converts it to one of:
  - json:     structured JSON with findings array
  - caveman:  one-line-per-finding format (L<n>: severity: problem. fix.)
  - markdown: clean markdown table (default)

Usage:
    cat review_output.md | python parse_output.py [--format json|caveman|markdown]

Exit codes:
    0 — parsed successfully
    1 — parse error
    2 — invalid arguments
"""

import argparse
import json
import re
import sys
from typing import Any


def _extract_score(text: str) -> int | None:
    """Extract confidence/review score from pr-agent output."""
    # Matches patterns like "Score: 3/5", "Confidence: 4/5", "score: 2"
    m = re.search(r"(?:score|confidence)[:\s]+(\d+)(?:\s*/\s*\d+)?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_findings(text: str) -> list[dict[str, Any]]:
    """Extract individual findings from pr-agent review output.

    PR-Agent review output varies by version, but common patterns include:
    - Inline code suggestions with file paths and line numbers
    - Severity indicators (critical, major, medium, minor, low)
    - Problem descriptions with suggested fixes
    """
    findings: list[dict[str, Any]] = []

    # Pattern 1: Table-style findings
    # | # | Category | File | Problem | Suggestion | Severity |
    table_pattern = re.compile(
        r"\|\s*\d+\s*\|"           # row number
        r"\s*([^|]+?)\s*\|"        # category
        r"\s*([^|]+?)\s*\|"        # file (may include line info)
        r"\s*([^|]+?)\s*\|"        # problem
        r"\s*([^|]+?)\s*\|"        # suggestion
        r"\s*([^|]*?)\s*\|",       # severity (optional)
    )
    for m in table_pattern.finditer(text):
        category, file_info, problem, suggestion, severity = (
            m.group(1).strip(),
            m.group(2).strip(),
            m.group(3).strip(),
            m.group(4).strip(),
            m.group(5).strip(),
        )

        # Extract file:line from file_info
        file_path, line = _parse_file_line(file_info)

        findings.append({
            "severity": _normalize_severity(severity or category),
            "category": category,
            "file": file_path,
            "line": line,
            "problem": _clean_markdown(problem),
            "fix": _clean_markdown(suggestion),
        })

    # Pattern 2: Inline comment-style findings
    # **file.py (line 42)** — Problem description
    inline_pattern = re.compile(
        r"\*\*([^*]+?)\s*"                    # file path
        r"(?:\(lines?\s*(\d+)(?:-\d+)?\))?"   # optional line number
        r"\*\*"                                # closing bold
        r"\s*(?:—|-|:)\s*"                     # separator
        r"(.+?)$",                             # problem description
        re.MULTILINE,
    )
    for m in inline_pattern.finditer(text):
        file_path = m.group(1).strip()
        line = int(m.group(2)) if m.group(2) else None
        problem = m.group(3).strip()

        # Avoid duplicates if already captured in table
        if not any(f["file"] == file_path and f["line"] == line for f in findings):
            findings.append({
                "severity": _infer_severity(problem),
                "category": "review",
                "file": file_path,
                "line": line,
                "problem": _clean_markdown(problem),
                "fix": "",
            })

    # Pattern 3: Bullet-style findings
    # - **severity**: description [file:line]
    bullet_pattern = re.compile(
        r"^[-*]\s+"
        r"(?:\*\*([^*]+)\*\*\s*[:]\s*)?"       # optional bold severity
        r"(.+?)"                                # description
        r"(?:\[`?([^]\s]+?(?::\d+)?)`?\])?"     # optional [file:line]
        r"\s*$",
        re.MULTILINE,
    )
    for m in bullet_pattern.finditer(text):
        severity_raw = m.group(1) or ""
        description = m.group(2).strip()
        file_line = m.group(3) or ""

        if not file_line and not severity_raw:
            continue  # Skip generic bullets

        file_path, line = _parse_file_line(file_line)

        if not any(f["file"] == file_path and f["line"] == line for f in findings if f["file"]):
            findings.append({
                "severity": _normalize_severity(severity_raw) if severity_raw else _infer_severity(description),
                "category": "review",
                "file": file_path or "",
                "line": line,
                "problem": _clean_markdown(description),
                "fix": "",
            })

    return findings


def _parse_file_line(text: str) -> tuple[str, int | None]:
    """Parse 'file.py:42' or 'file.py (line 42)' into (path, line)."""
    text = text.strip().strip("`")

    # file.py:42
    m = re.match(r"^(.+?):(\d+)$", text)
    if m:
        return m.group(1).strip(), int(m.group(2))

    # file.py (line 42) or file.py (lines 42-50)
    m = re.match(r"^(.+?)\s*\(lines?\s*(\d+)", text)
    if m:
        return m.group(1).strip(), int(m.group(2))

    return text, None


def _normalize_severity(raw: str) -> str:
    """Normalize severity strings to: critical, high, medium, low, info."""
    raw = raw.lower().strip()
    raw = re.sub(r"[^a-z]", "", raw)  # Remove emoji and punctuation

    if raw in ("critical", "blocker", "bug"):
        return "critical"
    if raw in ("high", "major", "important", "error"):
        return "high"
    if raw in ("medium", "moderate", "warning"):
        return "medium"
    if raw in ("low", "minor", "suggestion", "trivial", "nit", "nitpick"):
        return "low"
    if raw in ("info", "informational", "note"):
        return "info"
    return "medium"  # Default


def _infer_severity(text: str) -> str:
    """Infer severity from problem description text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ("security", "injection", "xss", "vulnerability", "auth")):
        return "critical"
    if any(w in text_lower for w in ("crash", "error", "exception", "null", "undefined", "leak")):
        return "high"
    if any(w in text_lower for w in ("performance", "n+1", "slow", "missing index")):
        return "medium"
    return "low"


def _clean_markdown(text: str) -> str:
    """Remove markdown formatting for plain-text output."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)       # italic
    text = re.sub(r"`(.+?)`", r"\1", text)         # inline code
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links
    return text.strip()


def _severity_emoji(severity: str) -> str:
    """Map severity to caveman-review emoji prefix."""
    return {
        "critical": "bug",
        "high": "risk",
        "medium": "risk",
        "low": "nit",
        "info": "q",
    }.get(severity, "nit")


def format_json(score: int | None, findings: list[dict]) -> str:
    """Format as JSON."""
    return json.dumps(
        {"score": score, "findings": findings, "count": len(findings)},
        indent=2,
    )


def format_caveman(score: int | None, findings: list[dict]) -> str:
    """Format as caveman-review one-liners."""
    lines = []
    if score is not None:
        lines.append(f"Score: {score}/5")
        lines.append("")

    for f in findings:
        prefix = _severity_emoji(f["severity"])
        loc = f["file"] or "?"
        if f["line"]:
            loc = f"{loc}:L{f['line']}"

        fix_part = f" {f['fix']}." if f["fix"] else ""
        lines.append(f"{loc}: {prefix}: {f['problem']}.{fix_part}")

    return "\n".join(lines)


def format_markdown(score: int | None, findings: list[dict]) -> str:
    """Format as a clean markdown table."""
    lines = []
    if score is not None:
        lines.append(f"**Review Score: {score}/5**")
        lines.append("")

    if not findings:
        lines.append("No findings.")
        return "\n".join(lines)

    lines.append("| Severity | File | Line | Problem | Fix |")
    lines.append("|----------|------|------|---------|-----|")
    for f in findings:
        line_str = str(f["line"]) if f["line"] else "-"
        lines.append(
            f"| {f['severity']} | {f['file'] or '-'} | {line_str} "
            f"| {f['problem']} | {f['fix'] or '-'} |"
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse pr-agent review output")
    parser.add_argument(
        "--format",
        choices=["json", "caveman", "markdown"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    args = parser.parse_args()

    raw_input = sys.stdin.read()
    if not raw_input.strip():
        if args.format == "json":
            print(json.dumps({"score": None, "findings": [], "count": 0}))
        else:
            print("No review output to parse.")
        return 0

    score = _extract_score(raw_input)
    findings = _extract_findings(raw_input)

    formatters = {
        "json": format_json,
        "caveman": format_caveman,
        "markdown": format_markdown,
    }

    print(formatters[args.format](score, findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
