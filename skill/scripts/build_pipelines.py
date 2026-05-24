#!/usr/bin/env python3
"""build_pipelines.py — Deterministic DAG builder for harness pipelines.

Reads a findings.md table and produces a pipelines.md wave plan.
Replaces the LLM-based planner with a reliable, deterministic script.

Usage:
    python build_pipelines.py --findings harness/findings.md --output harness/pipelines.md

Exit codes:
    0 — success
    1 — validation error (cycle, missing data, shared files in wave)
    2 — parse error (findings.md format issue)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass
class Finding:
    id: str
    severity: str
    area: str
    title: str
    file_line: str
    depends_on: list[str] = field(default_factory=list)
    touches_files: list[str] = field(default_factory=list)

    @property
    def severity_rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity.lower(), 99)


# ---------------------------------------------------------------------------
# Parse findings.md
# ---------------------------------------------------------------------------

def parse_findings_table(text: str) -> list[Finding]:
    """Parse a markdown table from findings.md into Finding objects.

    Expected columns (order-insensitive, matched by header name):
        ID | Severity | Area | Title | File:Line | Depends on | Touches files
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Find the header row (contains "ID" and "Severity")
    header_idx = None
    for i, line in enumerate(lines):
        if re.search(r"\bID\b", line, re.IGNORECASE) and re.search(
            r"\bSeverity\b", line, re.IGNORECASE
        ):
            header_idx = i
            break

    if header_idx is None:
        print("ERROR: Could not find a table header with 'ID' and 'Severity' columns.", file=sys.stderr)
        sys.exit(2)

    headers = [h.strip().lower() for h in lines[header_idx].strip("|").split("|")]

    # Map header names to column indices
    col_map: dict[str, int] = {}
    for target, patterns in {
        "id": [r"^id$"],
        "severity": [r"^severity$", r"^sev$"],
        "area": [r"^area$"],
        "title": [r"^title$"],
        "file_line": [r"^file[:\s]*line$", r"^file_line$"],
        "depends_on": [r"^depends[\s_]*on$"],
        "touches_files": [r"^touches[\s_]*files$"],
    }.items():
        for j, h in enumerate(headers):
            if any(re.match(p, h) for p in patterns):
                col_map[target] = j
                break

    required = {"id", "severity", "title", "depends_on", "touches_files"}
    missing = required - col_map.keys()
    if missing:
        print(f"ERROR: Missing required columns: {missing}", file=sys.stderr)
        print(f"  Found columns: {headers}", file=sys.stderr)
        sys.exit(2)

    # Skip the separator row (e.g. |---|---|...)
    data_start = header_idx + 1
    if data_start < len(lines) and re.match(r"^\|?[\s\-:|]+\|?$", lines[data_start]):
        data_start += 1

    findings: list[Finding] = []
    for line in lines[data_start:]:
        if not line.startswith("|") and "|" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))

        def cell(key: str) -> str:
            idx = col_map.get(key)
            if idx is None or idx >= len(cells):
                return ""
            return cells[idx].strip()

        fid = cell("id").strip()
        if not fid or not re.match(r"^F\d+", fid):
            continue  # skip non-finding rows

        deps_raw = cell("depends_on")
        deps = [d.strip() for d in re.findall(r"F\d+", deps_raw)] if deps_raw and deps_raw != "—" else []

        files_raw = cell("touches_files")
        files = [f.strip().strip("`") for f in files_raw.split(",") if f.strip() and f.strip() != "—"]

        findings.append(
            Finding(
                id=fid,
                severity=cell("severity"),
                area=cell("area"),
                title=cell("title"),
                file_line=cell("file_line"),
                depends_on=deps,
                touches_files=files,
            )
        )

    if not findings:
        print("ERROR: No findings parsed from the table.", file=sys.stderr)
        sys.exit(2)

    return findings


# ---------------------------------------------------------------------------
# Build dependency DAG
# ---------------------------------------------------------------------------

def build_dag(findings: list[Finding]) -> dict[str, set[str]]:
    """Build a dependency graph: result[F_j] = set of F_i that F_j depends on.

    Edges come from two sources:
    1. Explicit `Depends on` declarations.
    2. File-conflict overlaps in `Touches files`.
    """
    by_id = {f.id: f for f in findings}
    graph: dict[str, set[str]] = {f.id: set() for f in findings}

    # Explicit dependencies
    for f in findings:
        for dep in f.depends_on:
            if dep in by_id:
                graph[f.id].add(dep)
            else:
                print(f"WARNING: {f.id} depends on {dep}, which is not in findings. Ignoring.", file=sys.stderr)

    # File-conflict dependencies (lower-severity finding depends on higher)
    ids = [f.id for f in findings]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            fi, fj = by_id[ids[i]], by_id[ids[j]]
            shared = set(fi.touches_files) & set(fj.touches_files)
            if shared:
                # Higher severity (lower rank) goes first; on tie, lower ID goes first
                if (fi.severity_rank, fi.id) <= (fj.severity_rank, fj.id):
                    graph[fj.id].add(fi.id)
                else:
                    graph[fi.id].add(fj.id)

    return graph


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles in the dependency graph. Returns list of cycles found."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    parent: dict[str, str | None] = {node: None for node in graph}
    cycles: list[list[str]] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in graph.get(u, set()):
            if v not in color:
                continue
            if color[v] == GRAY:
                # Back edge — reconstruct cycle
                cycle = [v, u]
                cur = u
                while cur != v:
                    cur = parent.get(cur)  # type: ignore[assignment]
                    if cur is None or cur == v:
                        break
                    cycle.append(cur)
                cycle.reverse()
                cycles.append(cycle)
            elif color[v] == WHITE:
                parent[v] = u
                dfs(v)
        color[u] = BLACK

    for node in graph:
        if color[node] == WHITE:
            dfs(node)

    return cycles


# ---------------------------------------------------------------------------
# Topological sort into waves
# ---------------------------------------------------------------------------

def sort_into_waves(
    findings: list[Finding],
    graph: dict[str, set[str]],
) -> tuple[list[list[str]], list[str]]:
    """Topologically sort findings into waves.

    Returns (waves, deferred) where:
    - waves: list of lists, each inner list is a set of finding IDs that can
      run in parallel.
    - deferred: finding IDs with severity below 'low' (info-only), excluded
      from execution.
    """
    by_id = {f.id: f for f in findings}

    # Separate deferred (info-only) findings
    deferred = [f.id for f in findings if f.severity.lower() == "info"]
    active_ids = {f.id for f in findings if f.id not in deferred}

    # Count dependents for tie-breaking
    dependent_count: dict[str, int] = defaultdict(int)
    for fid, deps in graph.items():
        for dep in deps:
            dependent_count[dep] += 1

    remaining = set(active_ids)
    placed: set[str] = set()
    waves: list[list[str]] = []

    while remaining:
        # Find all findings whose dependencies are fully placed
        ready = []
        for fid in remaining:
            deps = graph.get(fid, set())
            active_deps = deps & active_ids
            if active_deps <= placed:
                ready.append(fid)

        if not ready:
            # Everything remaining has unresolved deps — should not happen
            # if cycle detection passed, but handle gracefully
            print(f"ERROR: Cannot schedule remaining findings: {remaining}", file=sys.stderr)
            print("  This usually means a dependency cycle was missed.", file=sys.stderr)
            sys.exit(1)

        # Sort within the wave by priority:
        # 1. Higher severity (lower rank) first
        # 2. More dependents first
        # 3. Smaller scope (fewer touches_files) first
        # 4. ID as final tie-break
        ready.sort(
            key=lambda fid: (
                by_id[fid].severity_rank,
                -dependent_count.get(fid, 0),
                len(by_id[fid].touches_files),
                fid,
            )
        )

        waves.append(ready)
        placed.update(ready)
        remaining -= set(ready)

    return waves, deferred


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_waves(
    findings: list[Finding],
    waves: list[list[str]],
    deferred: list[str],
) -> list[str]:
    """Validate the wave plan. Returns list of error messages."""
    by_id = {f.id: f for f in findings}
    errors: list[str] = []

    # Check no shared files within a wave
    for i, wave in enumerate(waves, 1):
        files_seen: dict[str, str] = {}  # file -> first finding ID
        for fid in wave:
            for fpath in by_id[fid].touches_files:
                if fpath in files_seen:
                    errors.append(
                        f"Wave {i}: {fid} and {files_seen[fpath]} both touch `{fpath}`"
                    )
                else:
                    files_seen[fpath] = fid

    # Check all findings are accounted for
    all_placed = set()
    for wave in waves:
        all_placed.update(wave)
    all_placed.update(deferred)
    all_ids = {f.id for f in findings}
    missing = all_ids - all_placed
    if missing:
        errors.append(f"Findings not in any wave or deferred: {missing}")

    return errors


# ---------------------------------------------------------------------------
# Render pipelines.md
# ---------------------------------------------------------------------------

def render_pipelines(
    findings: list[Finding],
    waves: list[list[str]],
    deferred: list[str],
    graph: dict[str, set[str]],
    objective_title: str = "<objective>",
) -> str:
    """Render the pipelines.md output."""
    by_id = {f.id: f for f in findings}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    total = len(findings)
    wave_count = len(waves)
    max_par = max(len(w) for w in waves) if waves else 0

    lines = [
        f"# Pipelines — {objective_title}",
        "",
        f"Generated by build_pipelines.py at {now}.",
        "",
        "## Summary",
        "",
        f"- Total findings: {total}",
        f"- Waves: {wave_count}",
        f"- Max parallelism: {max_par} (size of widest wave)",
        f"- Critical-path length: {wave_count} waves",
        f"- Deferred: {len(deferred)}",
        "",
    ]

    # Track which wave each finding is placed in (for annotation)
    placed_wave: dict[str, int] = {}
    for i, wave in enumerate(waves, 1):
        for fid in wave:
            placed_wave[fid] = i

    for i, wave in enumerate(waves, 1):
        label = "parallel" if len(wave) > 1 else "sequential"
        lines.append(f"## Wave {i} ({label} — {len(wave)} finding{'s' if len(wave) != 1 else ''})")
        lines.append("")

        for fid in wave:
            f = by_id[fid]
            lines.append(f"- **{fid}** — {f.title}")
            lines.append(f"  - severity: {f.severity}")

            # Show dependencies
            deps = graph.get(fid, set())
            explicit_deps = set(f.depends_on)
            file_conflict_deps = deps - explicit_deps

            if explicit_deps:
                lines.append(f"  - depends on: {', '.join(sorted(explicit_deps))}")

            # Show touches files
            touches = ", ".join(f"`{p}`" for p in f.touches_files) if f.touches_files else "n/a"
            lines.append(f"  - touches: {touches}")

            # Annotate non-semantic deferrals (file conflicts that pushed this to a later wave)
            if file_conflict_deps:
                for dep_id in sorted(file_conflict_deps):
                    dep_wave = placed_wave.get(dep_id, 0)
                    shared = set(f.touches_files) & set(by_id[dep_id].touches_files)
                    if shared:
                        shared_str = ", ".join(f"`{s}`" for s in shared)
                        lines.append(
                            f"  - ⚠ shares {shared_str} with {dep_id} in wave {dep_wave}; "
                            f"deferred to avoid file-conflict race"
                        )

        lines.append("")

    if deferred:
        lines.append("## Deferred / out of budget")
        lines.append("")
        for fid in deferred:
            f = by_id[fid]
            lines.append(f"- **{fid}** — {f.title} — sev={f.severity}; backlog.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a dependency-aware wave plan from findings.md."
    )
    parser.add_argument(
        "--findings",
        required=True,
        help="Path to findings.md",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write pipelines.md",
    )
    parser.add_argument(
        "--title",
        default="<objective>",
        help="Short title for the pipelines header (default: '<objective>')",
    )
    args = parser.parse_args()

    findings_path = Path(args.findings)
    if not findings_path.exists():
        print(f"ERROR: {findings_path} does not exist.", file=sys.stderr)
        sys.exit(2)

    text = findings_path.read_text()
    findings = parse_findings_table(text)
    print(f"Parsed {len(findings)} findings from {findings_path}")

    # Build DAG
    graph = build_dag(findings)

    # Cycle detection
    cycles = detect_cycles(graph)
    if cycles:
        print("ERROR: Dependency cycles detected:", file=sys.stderr)
        for cycle in cycles:
            print(f"  {' → '.join(cycle)} → {cycle[0]}", file=sys.stderr)
        print("Fix the `Depends on` or `Touches files` in findings.md.", file=sys.stderr)
        sys.exit(1)

    # Sort into waves
    waves, deferred = sort_into_waves(findings, graph)

    # Validate
    errors = validate_waves(findings, waves, deferred)
    if errors:
        print("ERROR: Wave plan validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Render
    output = render_pipelines(findings, waves, deferred, graph, objective_title=args.title)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output)

    print(f"Wrote {output_path}")
    print(f"  Waves: {len(waves)}, Max parallelism: {max(len(w) for w in waves) if waves else 0}")
    for i, wave in enumerate(waves, 1):
        ids = ", ".join(wave)
        print(f"  Wave {i}: {ids}")
    if deferred:
        print(f"  Deferred: {', '.join(deferred)}")


if __name__ == "__main__":
    main()
