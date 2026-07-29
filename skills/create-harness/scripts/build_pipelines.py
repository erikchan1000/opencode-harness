#!/usr/bin/env python3
"""build_pipelines.py — Deterministic DAG builder for harness pipelines.

Reads a findings.md table and produces a pipelines.md wave plan.
Replaces the LLM-based planner with a reliable, deterministic script.

Usage:
    python build_pipelines.py --findings plan/findings.md --output plan/pipelines.md

Exit codes:
    0 — success
    1 — validation error (cycle, missing data, shared files in wave)
    2 — parse error (findings.md format issue)
"""

from __future__ import annotations

import argparse
import posixpath
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

# Status column is optional. When present, every row must use one of these.
# "done" rows are excluded from scheduling but satisfy dependencies.
# "deferred" rows join the deferred section alongside info-severity findings.
ACTIVE_STATUSES = {"", "todo", "pending", "in_progress", "in-progress", "blocked"}
DONE_STATUSES = {"done"}
DEFERRED_STATUSES = {"deferred"}
KNOWN_STATUSES = ACTIVE_STATUSES | DONE_STATUSES | DEFERRED_STATUSES

# Cell values that mean "empty" in the findings table.
EMPTY_CELL_VALUES = {"", "—", "-", "–", "n/a", "none"}


@dataclass
class Finding:
    id: str
    severity: str
    area: str
    title: str
    file_line: str
    depends_on: list[str] = field(default_factory=list)
    touches_files: list[str] = field(default_factory=list)
    status: str = ""

    @property
    def severity_rank(self) -> int:
        # Severity is validated at parse time; unknown values never reach here.
        return SEVERITY_ORDER[self.severity.lower()]

    @property
    def is_done(self) -> bool:
        return self.status.lower() in DONE_STATUSES

    @property
    def is_status_deferred(self) -> bool:
        return self.status.lower() in DEFERRED_STATUSES


def normalize_path(p: str) -> str:
    """Normalize a touches-files path for comparison.

    Converts backslashes to forward slashes, collapses `.` segments, and
    strips a leading `./`. Does NOT resolve against the filesystem — the
    script must stay deterministic and runnable from anywhere.
    """
    p = p.strip().strip("`").replace("\\", "/")
    if not p:
        return p
    p = posixpath.normpath(p)
    if p.startswith("./"):
        p = p[2:]
    return p


# ---------------------------------------------------------------------------
# Parse findings.md
# ---------------------------------------------------------------------------

def parse_findings_table(text: str) -> list[Finding]:
    """Parse a markdown table from findings.md into Finding objects.

    Expected columns (order-insensitive, matched by header name):
        ID | Severity | Area | Title | File:Line | Depends on | Touches files
    Optional column:
        Status  (todo | pending | in_progress | blocked | done | deferred)
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
        "status": [r"^status$"],
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
    seen_ids: set[str] = set()
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
            value = cells[idx].strip()
            return "" if value.lower() in EMPTY_CELL_VALUES else value

        fid = cell("id").strip()
        if not fid or not re.match(r"^[A-Z]+\d+", fid):
            continue  # skip non-finding rows

        if fid in seen_ids:
            print(f"ERROR: Duplicate finding ID {fid} in findings table.", file=sys.stderr)
            sys.exit(2)
        seen_ids.add(fid)

        severity = cell("severity")
        if severity.lower() not in SEVERITY_ORDER:
            print(
                f"ERROR: {fid} has unknown severity '{severity}'. "
                f"Expected one of: {', '.join(SEVERITY_ORDER)}.",
                file=sys.stderr,
            )
            sys.exit(2)

        status = cell("status")
        if status.lower() not in KNOWN_STATUSES:
            print(
                f"ERROR: {fid} has unknown status '{status}'. "
                f"Expected one of: {', '.join(sorted(s for s in KNOWN_STATUSES if s))} (or empty).",
                file=sys.stderr,
            )
            sys.exit(2)

        deps_raw = cell("depends_on")
        deps = [d.strip() for d in re.findall(r"[A-Z]+\d+", deps_raw)] if deps_raw else []

        files_raw = cell("touches_files")
        files = [
            normalize_path(f)
            for f in files_raw.split(",")
            if f.strip() and f.strip().lower() not in EMPTY_CELL_VALUES
        ]

        findings.append(
            Finding(
                id=fid,
                severity=severity,
                area=cell("area"),
                title=cell("title"),
                file_line=cell("file_line"),
                depends_on=deps,
                touches_files=files,
                status=status,
            )
        )

    if not findings:
        print("ERROR: No findings parsed from the table.", file=sys.stderr)
        sys.exit(2)

    return findings


def warn_basename_collisions(findings: list[Finding]) -> None:
    """Warn when two findings touch files with the same basename but
    different paths — a common symptom of research agents naming the same
    file inconsistently (e.g. `foo.dart` vs `lib/src/foo.dart`), which
    would silently defeat file-conflict detection.
    """
    by_basename: dict[str, set[str]] = defaultdict(set)
    owners: dict[str, set[str]] = defaultdict(set)
    for f in findings:
        for p in f.touches_files:
            base = posixpath.basename(p)
            by_basename[base].add(p)
            owners[base].add(f.id)

    for base, paths in sorted(by_basename.items()):
        if len(paths) > 1 and len(owners[base]) > 1:
            print(
                f"WARNING: Findings {', '.join(sorted(owners[base]))} touch files "
                f"with the same basename '{base}' under different paths "
                f"({', '.join(sorted(paths))}). If these are the same file, "
                f"normalize the paths in findings.md — otherwise the "
                f"file-conflict check will miss the overlap.",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Build dependency DAG
# ---------------------------------------------------------------------------

def explicit_linear_order(findings: list[Finding]) -> dict[str, int]:
    """Compute a linear extension of the EXPLICIT `Depends on` DAG.

    Returns a position index per finding ID. File-conflict edges are
    oriented by this single global order — a total order can never create
    a cycle, and because it is a linear extension of the explicit DAG,
    conflict edges can never contradict a declared dependency (directly
    OR through intermediate findings). Pairwise severity orientation is
    not enough: F06(high)→F04(low) explicit plus a third finding
    F02(medium) sharing files with both would yield F02→F06→F04→F02.

    Within each layer of available findings the tie-break is higher
    severity first, then ID — preserving the old heuristic for
    independent pairs.

    If the explicit dependencies themselves contain a cycle, the
    remaining findings are appended deterministically; the cycle is a
    genuine findings.md bug and is reported by detect_cycles on the full
    graph.
    """
    by_id = {f.id: f for f in findings}
    deps = {f.id: {d for d in f.depends_on if d in by_id} for f in findings}
    order: dict[str, int] = {}
    remaining = set(by_id)
    while remaining:
        ready = [fid for fid in remaining if deps[fid] <= order.keys()]
        if not ready:
            # Explicit-dep cycle. Append the rest deterministically;
            # detect_cycles will surface the error to the user.
            ready = list(remaining)
        ready.sort(key=lambda fid: (by_id[fid].severity_rank, fid))
        for fid in ready:
            order[fid] = len(order)
        remaining -= set(ready)
    return order


def build_dag(findings: list[Finding]) -> dict[str, set[str]]:
    """Build a dependency graph: result[F_j] = set of F_i that F_j depends on.

    Edges come from two sources:
    1. Explicit `Depends on` declarations.
    2. File-conflict overlaps in `Touches files`, oriented by a single
       global linear extension of the explicit DAG (see
       explicit_linear_order) so conflict edges can never manufacture a
       cycle or contradict a declared dependency.

    Findings already marked done are excluded from file-conflict edges
    (their diffs have landed; there is nothing left to race against).
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

    order = explicit_linear_order(findings)

    # File-conflict dependencies
    ids = [f.id for f in findings]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            fi, fj = by_id[ids[i]], by_id[ids[j]]
            if fi.is_done or fj.is_done:
                continue
            shared = set(fi.touches_files) & set(fj.touches_files)
            if not shared:
                continue
            if order[fi.id] < order[fj.id]:
                graph[fj.id].add(fi.id)
            else:
                graph[fi.id].add(fj.id)

    return graph


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles in the dependency graph. Returns list of cycles found.

    Each reported cycle is the actual path (in dependency order) from the
    first revisited node back to itself.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    cycles: list[list[str]] = []
    path: list[str] = []

    # Iterative DFS so long dependency chains cannot hit the recursion limit.
    for root in graph:
        if color[root] != WHITE:
            continue
        stack: list[tuple[str, "iter"]] = [(root, iter(sorted(graph.get(root, set()))))]
        color[root] = GRAY
        path.append(root)
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                if child not in color:
                    continue
                if color[child] == GRAY:
                    # Back edge — the cycle is the path slice from child to node.
                    idx = path.index(child)
                    cycles.append(path[idx:])
                elif color[child] == WHITE:
                    color[child] = GRAY
                    path.append(child)
                    stack.append((child, iter(sorted(graph.get(child, set())))))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                path.pop()
                stack.pop()

    return cycles


# ---------------------------------------------------------------------------
# Topological sort into waves
# ---------------------------------------------------------------------------

def sort_into_waves(
    findings: list[Finding],
    graph: dict[str, set[str]],
) -> tuple[list[list[str]], list[str], list[str]]:
    """Topologically sort findings into waves.

    Returns (waves, deferred, done) where:
    - waves: list of lists, each inner list is a set of finding IDs that can
      run in parallel.
    - deferred: finding IDs excluded from execution (info severity, or
      status=deferred).
    - done: finding IDs already completed (status=done). They are excluded
      from waves but SATISFY dependencies of active findings.
    """
    by_id = {f.id: f for f in findings}

    done = [f.id for f in findings if f.is_done]
    done_set = set(done)

    deferred = [
        f.id
        for f in findings
        if f.id not in done_set
        and (f.severity.lower() == "info" or f.is_status_deferred)
    ]
    deferred_set = set(deferred)

    active_ids = {f.id for f in findings if f.id not in done_set and f.id not in deferred_set}

    # An active finding depending on a deferred finding will run with that
    # dependency unmet — surface it instead of silently proceeding.
    for fid in sorted(active_ids):
        unmet = graph.get(fid, set()) & deferred_set
        if unmet:
            print(
                f"WARNING: {fid} depends on deferred finding(s) "
                f"{', '.join(sorted(unmet))}; it will run with that dependency unmet.",
                file=sys.stderr,
            )

    # Count dependents for tie-breaking
    dependent_count: dict[str, int] = defaultdict(int)
    for fid, deps in graph.items():
        for dep in deps:
            dependent_count[dep] += 1

    remaining = set(active_ids)
    placed: set[str] = set()
    waves: list[list[str]] = []

    while remaining:
        # Find all findings whose active dependencies are fully placed.
        # Dependencies on done findings are already satisfied; dependencies
        # on deferred findings are ignored (warned above).
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

    return waves, deferred, done


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_waves(
    findings: list[Finding],
    waves: list[list[str]],
    deferred: list[str],
    done: list[str],
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
    all_placed.update(done)
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
    done: list[str],
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
        f"- Already done: {len(done)}",
        f"- Deferred: {len(deferred)}",
        "",
    ]

    # Track which wave each finding is placed in (for annotation)
    placed_wave: dict[str, int] = {}
    for i, wave in enumerate(waves, 1):
        for fid in wave:
            placed_wave[fid] = i

    for i, wave in enumerate(waves, 1):
        label = "parallel" if len(wave) > 1 else "single finding"
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

    if done:
        lines.append("## Already completed (excluded from waves)")
        lines.append("")
        for fid in done:
            f = by_id[fid]
            lines.append(f"- **{fid}** — {f.title} — status=done; dependencies on it are satisfied.")
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

    if args.title == "<objective>":
        print("WARNING: --title not provided; pipelines.md header will contain the literal placeholder '<objective>'.", file=sys.stderr)

    findings_path = Path(args.findings)
    if not findings_path.exists():
        print(f"ERROR: {findings_path} does not exist.", file=sys.stderr)
        sys.exit(2)

    text = findings_path.read_text()
    findings = parse_findings_table(text)
    print(f"Parsed {len(findings)} findings from {findings_path}")

    warn_basename_collisions(findings)

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
    waves, deferred, done = sort_into_waves(findings, graph)

    # Validate
    errors = validate_waves(findings, waves, deferred, done)
    if errors:
        print("ERROR: Wave plan validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Render
    output = render_pipelines(findings, waves, deferred, done, graph, objective_title=args.title)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output)

    print(f"Wrote {output_path}")
    print(f"  Waves: {len(waves)}, Max parallelism: {max(len(w) for w in waves) if waves else 0}")
    for i, wave in enumerate(waves, 1):
        ids = ", ".join(wave)
        print(f"  Wave {i}: {ids}")
    if done:
        print(f"  Already done: {', '.join(done)}")
    if deferred:
        print(f"  Deferred: {', '.join(deferred)}")


if __name__ == "__main__":
    main()
