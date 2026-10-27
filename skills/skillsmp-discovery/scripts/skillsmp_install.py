#!/usr/bin/env python3
"""Install a skill from a GitHub repo into OpenCode global skills."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple


GITHUB_API = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"


def _normalize_name(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9-]+", "-", lowered)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned


def _api_get_json(url: str, headers: Dict[str, str], timeout: int) -> Dict:
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _api_get_text(url: str, headers: Dict[str, str], timeout: int) -> str:
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return body


def _raw_get_bytes(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url=url, headers={"User-Agent": "skillsmp-discovery/1.0"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_frontmatter_name(content: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", content, re.DOTALL)
    if not match:
        return ""
    frontmatter = match.group(1)
    name_match = re.search(r"^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$", frontmatter, re.MULTILINE)
    return name_match.group(1).strip() if name_match else ""


def _split_repo(repo: str) -> Tuple[str, str]:
    parts = repo.strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("repo must be in owner/repo format")
    return parts[0], parts[1]


def _build_auth_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "skillsmp-discovery/1.0",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_repo_metadata(owner: str, repo: str, headers: Dict[str, str], timeout: int) -> Dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    return _api_get_json(url, headers, timeout)


def _fetch_repo_tree(owner: str, repo: str, ref: str, headers: Dict[str, str], timeout: int) -> List[Dict]:
    quoted_ref = urllib.parse.quote(ref, safe="")
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{quoted_ref}?recursive=1"
    payload = _api_get_json(url, headers, timeout)
    return payload.get("tree", [])


def _select_skill(
    owner: str,
    repo: str,
    ref: str,
    tree: List[Dict],
    skill_name: str,
    headers: Dict[str, str],
    timeout: int,
) -> Dict:
    skill_md_entries = [entry for entry in tree if entry.get("type") == "blob" and entry.get("path", "").endswith("SKILL.md")]
    if not skill_md_entries:
        raise RuntimeError("No SKILL.md files found in repository")

    candidates: List[Dict] = []
    requested = _normalize_name(skill_name) if skill_name else ""

    for entry in skill_md_entries:
        path = entry["path"]
        raw_url = f"{RAW_BASE}/{owner}/{repo}/{ref}/{path}"
        content = _api_get_text(raw_url, {}, timeout)
        fm_name = _parse_frontmatter_name(content)
        dir_name = os.path.basename(os.path.dirname(path))
        normalized_fm_name = _normalize_name(fm_name) if fm_name else ""
        normalized_dir_name = _normalize_name(dir_name)

        item = {
            "path": path,
            "frontmatter_name": fm_name,
            "directory_name": dir_name,
            "normalized_fm_name": normalized_fm_name,
            "normalized_dir_name": normalized_dir_name,
        }

        if not requested:
            candidates.append(item)
            continue

        if requested in {normalized_fm_name, normalized_dir_name}:
            candidates.append(item)

    if requested and not candidates:
        available = []
        for entry in skill_md_entries:
            path = entry["path"]
            available.append(os.path.basename(os.path.dirname(path)))
        listed = ", ".join(sorted(set(available)))
        raise RuntimeError(f"No matching skill found for '{skill_name}'. Available directories: {listed}")

    if not requested and len(candidates) > 1:
        options = []
        for item in candidates:
            display = item["frontmatter_name"] or item["directory_name"]
            options.append(f"- {display} ({item['path']})")
        joined = "\n".join(options)
        raise RuntimeError(
            "Repository contains multiple skills. Re-run with --skill-name.\n"
            f"Candidates:\n{joined}"
        )

    if len(candidates) > 1:
        exact = [c for c in candidates if c["normalized_fm_name"] == requested]
        if len(exact) == 1:
            return exact[0]
        raise RuntimeError("Multiple matching skills found. Use a more specific --skill-name")

    return candidates[0]


def _collect_skill_files(tree: List[Dict], skill_root: str) -> List[str]:
    prefix = f"{skill_root}/" if skill_root else ""
    files: List[str] = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        if path == skill_root or path.startswith(prefix):
            files.append(path)
    return sorted(files)


def _write_skill_files(
    owner: str,
    repo: str,
    ref: str,
    skill_root: str,
    files: List[str],
    destination: str,
    timeout: int,
) -> None:
    os.makedirs(destination, exist_ok=True)
    prefix = f"{skill_root}/" if skill_root else ""

    for path in files:
        rel_path = path[len(prefix) :] if prefix and path.startswith(prefix) else os.path.basename(path)
        out_path = os.path.join(destination, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        raw_url = f"{RAW_BASE}/{owner}/{repo}/{ref}/{path}"
        content = _raw_get_bytes(raw_url, timeout)
        with open(out_path, "wb") as fh:
            fh.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a skill from GitHub into OpenCode")
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/repo format")
    parser.add_argument("--skill-name", default="", help="Skill name to install (required if repo has many)")
    parser.add_argument("--ref", default="", help="Branch, tag, or commit SHA (defaults to repo default branch)")
    # The opencode dir is the deliberate default: it is the staging area that
    # `install.sh --claude` fans out from. omp users pass --target-dir, since
    # omp's installer does not sweep this directory.
    parser.add_argument(
        "--target-dir",
        default=os.path.expanduser("~/.config/opencode/skills"),
        help="Target skills directory",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing destination")
    parser.add_argument("--dry-run", action="store_true", help="Preview selection without writing files")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    try:
        owner, repo = _split_repo(args.repo)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    headers = _build_auth_headers()

    try:
        metadata = _fetch_repo_metadata(owner, repo, headers, args.timeout)
    except urllib.error.HTTPError as exc:
        print(f"Failed to read repository metadata: HTTP {exc.code}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Failed to read repository metadata: {exc}", file=sys.stderr)
        return 1

    ref = args.ref.strip() or metadata.get("default_branch") or "main"

    try:
        tree = _fetch_repo_tree(owner, repo, ref, headers, args.timeout)
    except urllib.error.HTTPError as exc:
        print(f"Failed to read repository tree: HTTP {exc.code}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Failed to read repository tree: {exc}", file=sys.stderr)
        return 1

    try:
        selected = _select_skill(owner, repo, ref, tree, args.skill_name, headers, args.timeout)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    skill_root = os.path.dirname(selected["path"])
    files = _collect_skill_files(tree, skill_root)
    if not files:
        print("No files found for selected skill", file=sys.stderr)
        return 1

    destination_name = _normalize_name(selected.get("frontmatter_name") or selected.get("directory_name") or "")
    if not destination_name:
        destination_name = _normalize_name(os.path.basename(skill_root)) or "imported-skill"

    target_dir = os.path.abspath(os.path.expanduser(args.target_dir))
    destination = os.path.join(target_dir, destination_name)

    output = {
        "repo": f"{owner}/{repo}",
        "ref": ref,
        "selected_path": selected["path"],
        "selected_name": selected.get("frontmatter_name") or selected.get("directory_name"),
        "skill_root": skill_root,
        "files": len(files),
        "destination": destination,
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run:
        if args.json:
            print(json.dumps(output, ensure_ascii=True, indent=2))
        else:
            print(f"repo: {output['repo']} @ {output['ref']}")
            print(f"skill: {output['selected_name']}")
            print(f"skill_root: {output['skill_root']}")
            print(f"files: {output['files']}")
            print(f"destination: {output['destination']}")
        return 0

    if os.path.exists(destination):
        if args.overwrite:
            shutil.rmtree(destination)
        else:
            print(f"Destination already exists: {destination} (use --overwrite)", file=sys.stderr)
            return 2

    try:
        _write_skill_files(owner, repo, ref, skill_root, files, destination, args.timeout)
    except Exception as exc:
        print(f"Failed while writing files: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(output, ensure_ascii=True, indent=2))
    else:
        print(f"Installed {output['selected_name']} from {output['repo']} @ {output['ref']}")
        print(f"Destination: {output['destination']}")
        print(f"Files: {output['files']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
