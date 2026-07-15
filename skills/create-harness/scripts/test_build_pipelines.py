#!/usr/bin/env python3
"""Tests for build_pipelines.py.

Run with:  python -m unittest scripts/test_build_pipelines.py -v
       or: python scripts/test_build_pipelines.py
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_pipelines import (  # noqa: E402
    Finding,
    build_dag,
    detect_cycles,
    explicit_linear_order,
    normalize_path,
    parse_findings_table,
    sort_into_waves,
    validate_waves,
    warn_basename_collisions,
)

HEADER = (
    "| ID | Severity | Area | Title | File:Line | Depends on | Touches files |\n"
    "|----|----------|------|-------|-----------|------------|---------------|\n"
)

HEADER_WITH_STATUS = (
    "| ID | Severity | Area | Title | File:Line | Depends on | Touches files | Status |\n"
    "|----|----------|------|-------|-----------|------------|---------------|--------|\n"
)


def table(rows: list[str], header: str = HEADER) -> str:
    return header + "\n".join(rows) + "\n"


@contextlib.contextmanager
def captured_stderr():
    buf = io.StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        yield buf
    finally:
        sys.stderr = old


class TestParsing(unittest.TestCase):
    def test_parse_basic(self):
        text = table([
            "| F01 | high | rec | Fix A | a.py:1 | — | a.py |",
            "| F02 | medium | net | Fix B | b.py:2 | F01 | b.py, c.py |",
        ])
        findings = parse_findings_table(text)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].id, "F01")
        self.assertEqual(findings[0].depends_on, [])
        self.assertEqual(findings[1].depends_on, ["F01"])
        self.assertEqual(findings[1].touches_files, ["b.py", "c.py"])

    def test_duplicate_id_exits_2(self):
        text = table([
            "| F01 | high | rec | Fix A | a.py:1 | — | a.py |",
            "| F01 | low | rec | Fix A again | a.py:9 | — | z.py |",
        ])
        with captured_stderr(), self.assertRaises(SystemExit) as ctx:
            parse_findings_table(text)
        self.assertEqual(ctx.exception.code, 2)

    def test_unknown_severity_exits_2(self):
        text = table([
            "| F01 | hgih | rec | Typo severity | a.py:1 | — | a.py |",
        ])
        with captured_stderr(), self.assertRaises(SystemExit) as ctx:
            parse_findings_table(text)
        self.assertEqual(ctx.exception.code, 2)

    def test_unknown_status_exits_2(self):
        text = table(
            ["| F01 | high | rec | Fix A | a.py:1 | — | a.py | shipped |"],
            header=HEADER_WITH_STATUS,
        )
        with captured_stderr(), self.assertRaises(SystemExit) as ctx:
            parse_findings_table(text)
        self.assertEqual(ctx.exception.code, 2)

    def test_status_column_optional_and_parsed(self):
        text = table(
            [
                "| F01 | high | rec | Fix A | a.py:1 | — | a.py | done |",
                "| F02 | low | rec | Fix B | b.py:1 | — | b.py | — |",
            ],
            header=HEADER_WITH_STATUS,
        )
        findings = parse_findings_table(text)
        self.assertTrue(findings[0].is_done)
        self.assertFalse(findings[1].is_done)

    def test_path_normalization(self):
        self.assertEqual(normalize_path("./foo/bar.py"), "foo/bar.py")
        self.assertEqual(normalize_path("foo\\bar.py"), "foo/bar.py")
        self.assertEqual(normalize_path("`foo.py`"), "foo.py")
        self.assertEqual(normalize_path("foo/./bar.py"), "foo/bar.py")

    def test_basename_collision_warns(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["lib/foo.py"]),
            Finding("F02", "low", "", "B", "", [], ["foo.py"]),
        ]
        with captured_stderr() as buf:
            warn_basename_collisions(findings)
        self.assertIn("WARNING", buf.getvalue())
        self.assertIn("foo.py", buf.getvalue())


class TestDag(unittest.TestCase):
    def test_file_conflict_creates_edge_severity_orientation(self):
        findings = [
            Finding("F01", "low", "", "A", "", [], ["shared.py"]),
            Finding("F02", "high", "", "B", "", [], ["shared.py"]),
        ]
        graph = build_dag(findings)
        # Higher severity (F02) goes first: F01 depends on F02.
        self.assertIn("F02", graph["F01"])
        self.assertNotIn("F01", graph["F02"])

    def test_explicit_dep_overrides_severity_orientation(self):
        # F02 (high) explicitly depends on F01 (low); they share a file.
        # The old severity heuristic would add F01->F02, creating a cycle.
        findings = [
            Finding("F01", "low", "", "A", "", [], ["shared.py"]),
            Finding("F02", "high", "", "B", "", ["F01"], ["shared.py"]),
        ]
        graph = build_dag(findings)
        self.assertIn("F01", graph["F02"])
        self.assertNotIn("F02", graph["F01"])
        self.assertEqual(detect_cycles(graph), [])

    def test_transitive_explicit_dep_overrides_orientation(self):
        # F03 (high) -> F02 (med) -> F01 (low); F03 and F01 share a file.
        findings = [
            Finding("F01", "low", "", "A", "", [], ["shared.py"]),
            Finding("F02", "medium", "", "B", "", ["F01"], ["b.py"]),
            Finding("F03", "high", "", "C", "", ["F02"], ["shared.py"]),
        ]
        order = explicit_linear_order(findings)
        self.assertLess(order["F01"], order["F03"])
        graph = build_dag(findings)
        self.assertIn("F01", graph["F03"])
        self.assertNotIn("F03", graph["F01"])
        self.assertEqual(detect_cycles(graph), [])

    def test_third_party_conflict_cannot_manufacture_cycle(self):
        # Regression: F06 (high) explicitly depends on F04 (low); F02
        # (medium) shares a file with BOTH. Pairwise severity orientation
        # would produce F02 -> F06 -> F04 -> F02. The global linear-
        # extension orientation must stay acyclic and respect F04 < F06.
        findings = [
            Finding("F02", "medium", "", "B", "", [], ["api_client.dart"]),
            Finding("F04", "low", "", "D", "", [], ["api_client.dart"]),
            Finding("F06", "high", "", "F", "", ["F04"], ["session.dart", "api_client.dart"]),
        ]
        graph = build_dag(findings)
        self.assertEqual(detect_cycles(graph), [])
        # Explicit dep respected: F06 after F04.
        self.assertIn("F04", graph["F06"])
        # F02 (medium) precedes F04 (low) — severity tie-break within the
        # first layer of the linear extension.
        self.assertIn("F02", graph["F04"])
        # And therefore F02 must also precede F06.
        self.assertIn("F02", graph["F06"])

    def test_explicit_dep_cycle_still_reported(self):
        # A genuine cycle in explicit deps must not be masked by the
        # linear-order fallback.
        findings = [
            Finding("F01", "high", "", "A", "", ["F02"], ["a.py"]),
            Finding("F02", "high", "", "B", "", ["F01"], ["b.py"]),
        ]
        graph = build_dag(findings)
        cycles = detect_cycles(graph)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(set(cycles[0]), {"F01", "F02"})

    def test_done_finding_creates_no_file_conflict_edge(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["shared.py"], status="done"),
            Finding("F02", "low", "", "B", "", [], ["shared.py"]),
        ]
        graph = build_dag(findings)
        self.assertEqual(graph["F02"], set())

    def test_cycle_detected(self):
        graph = {"F01": {"F02"}, "F02": {"F03"}, "F03": {"F01"}}
        cycles = detect_cycles(graph)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(set(cycles[0]), {"F01", "F02", "F03"})

    def test_no_cycle_in_dag(self):
        graph = {"F01": set(), "F02": {"F01"}, "F03": {"F01", "F02"}}
        self.assertEqual(detect_cycles(graph), [])

    def test_long_chain_no_recursion_error(self):
        n = 5000
        graph = {f"F{i:05d}": ({f"F{i-1:05d}"} if i > 0 else set()) for i in range(n)}
        self.assertEqual(detect_cycles(graph), [])


class TestWaves(unittest.TestCase):
    def test_independent_findings_share_wave_1(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["a.py"]),
            Finding("F02", "low", "", "B", "", [], ["b.py"]),
        ]
        graph = build_dag(findings)
        waves, deferred, done = sort_into_waves(findings, graph)
        self.assertEqual(waves, [["F01", "F02"]])
        self.assertEqual(deferred, [])
        self.assertEqual(done, [])

    def test_file_conflict_splits_waves(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["shared.py"]),
            Finding("F02", "low", "", "B", "", [], ["shared.py"]),
        ]
        graph = build_dag(findings)
        waves, _, _ = sort_into_waves(findings, graph)
        self.assertEqual(waves, [["F01"], ["F02"]])
        self.assertEqual(validate_waves(findings, waves, [], []), [])

    def test_done_excluded_and_satisfies_deps(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["a.py"], status="done"),
            Finding("F02", "medium", "", "B", "", ["F01"], ["b.py"]),
        ]
        graph = build_dag(findings)
        waves, deferred, done = sort_into_waves(findings, graph)
        self.assertEqual(done, ["F01"])
        # F02's dep on F01 is satisfied — it runs in wave 1, not blocked.
        self.assertEqual(waves, [["F02"]])
        self.assertEqual(validate_waves(findings, waves, deferred, done), [])

    def test_info_severity_deferred(self):
        findings = [
            Finding("F01", "info", "", "A", "", [], ["a.py"]),
            Finding("F02", "high", "", "B", "", [], ["b.py"]),
        ]
        graph = build_dag(findings)
        waves, deferred, _ = sort_into_waves(findings, graph)
        self.assertEqual(deferred, ["F01"])
        self.assertEqual(waves, [["F02"]])

    def test_status_deferred(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["a.py"], status="deferred"),
            Finding("F02", "high", "", "B", "", [], ["b.py"]),
        ]
        graph = build_dag(findings)
        waves, deferred, _ = sort_into_waves(findings, graph)
        self.assertEqual(deferred, ["F01"])
        self.assertEqual(waves, [["F02"]])

    def test_dep_on_deferred_warns(self):
        findings = [
            Finding("F01", "info", "", "A", "", [], ["a.py"]),
            Finding("F02", "high", "", "B", "", ["F01"], ["b.py"]),
        ]
        graph = build_dag(findings)
        with captured_stderr() as buf:
            waves, _, _ = sort_into_waves(findings, graph)
        self.assertIn("WARNING", buf.getvalue())
        self.assertIn("F02", buf.getvalue())
        self.assertEqual(waves, [["F02"]])

    def test_wave_ordering_tie_breaks(self):
        # Same wave: higher severity first, then more dependents, then
        # smaller scope, then ID.
        findings = [
            Finding("F01", "medium", "", "A", "", [], ["a.py", "a2.py"]),
            Finding("F02", "critical", "", "B", "", [], ["b.py"]),
            Finding("F03", "medium", "", "C", "", [], ["c.py"]),
        ]
        graph = build_dag(findings)
        waves, _, _ = sort_into_waves(findings, graph)
        self.assertEqual(waves, [["F02", "F03", "F01"]])

    def test_normalized_paths_conflict(self):
        # `./shared.py` and `shared.py` are the same file after
        # normalization — must not land in the same wave.
        text = table([
            "| F01 | high | rec | A | a:1 | — | ./shared.py |",
            "| F02 | low | rec | B | b:1 | — | shared.py |",
        ])
        findings = parse_findings_table(text)
        graph = build_dag(findings)
        waves, _, _ = sort_into_waves(findings, graph)
        self.assertEqual(waves, [["F01"], ["F02"]])


class TestValidation(unittest.TestCase):
    def test_shared_file_in_wave_reported(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["shared.py"]),
            Finding("F02", "low", "", "B", "", [], ["shared.py"]),
        ]
        errors = validate_waves(findings, [["F01", "F02"]], [], [])
        self.assertEqual(len(errors), 1)
        self.assertIn("shared.py", errors[0])

    def test_missing_finding_reported(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["a.py"]),
            Finding("F02", "low", "", "B", "", [], ["b.py"]),
        ]
        errors = validate_waves(findings, [["F01"]], [], [])
        self.assertEqual(len(errors), 1)
        self.assertIn("F02", errors[0])

    def test_done_counts_as_accounted_for(self):
        findings = [
            Finding("F01", "high", "", "A", "", [], ["a.py"], status="done"),
            Finding("F02", "low", "", "B", "", [], ["b.py"]),
        ]
        errors = validate_waves(findings, [["F02"]], [], ["F01"])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
