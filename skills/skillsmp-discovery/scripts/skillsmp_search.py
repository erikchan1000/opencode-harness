#!/usr/bin/env python3
"""Search SkillsMP via API (preferred) with scrape fallback."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Tuple


API_ENDPOINTS = (
    "https://skillsmp.com/api/v1/skills/ai-search",
    "https://skillsmp.com/api/v1/skills/search",
)
SCRAPE_ENDPOINT = "https://r.jina.ai/http://skillsmp.com/search"


def _http_get(url: str, headers: Dict[str, str], timeout: int) -> Tuple[int, bytes]:
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        return int(exc.code), body


def _extract_api_results(payload: Dict) -> List[Dict[str, str]]:
    items = payload.get("data", {}).get("data", [])
    results: List[Dict[str, str]] = []
    for item in items:
        skill = item.get("skill") or {}
        name = (skill.get("name") or "").strip()
        repo = ""
        github_url = (skill.get("githubUrl") or "").strip()
        if github_url.startswith("https://github.com/"):
            parts = github_url.replace("https://github.com/", "").split("/")
            if len(parts) >= 2:
                repo = f"{parts[0]}/{parts[1]}"

        results.append(
            {
                "source": "api",
                "name": name,
                "author": (skill.get("author") or "").strip(),
                "repo": repo,
                "github_url": github_url,
                "skill_url": (skill.get("skillUrl") or "").strip(),
                "description": (skill.get("description") or "").strip(),
                "stars": str(skill.get("stars") or ""),
                "updated_at": (skill.get("updatedAt") or "").strip(),
                "score": str(item.get("score") or ""),
            }
        )
    return results


def _search_api(query: str, api_key: str, limit: int, timeout: int) -> Tuple[List[Dict], List[str]]:
    warnings: List[str] = []
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {api_key}",
        "Origin": "https://skillsmp.com",
        "Referer": "https://skillsmp.com/",
        "User-Agent": "skillsmp-discovery/1.0",
    }

    for endpoint in API_ENDPOINTS:
        params = {"q": query, "page": 1, "limit": min(max(limit, 1), 100)}
        url = f"{endpoint}?{urllib.parse.urlencode(params)}"
        status, body = _http_get(url, headers, timeout)
        if status != 200:
            snippet = body.decode("utf-8", errors="replace").strip()
            if len(snippet) > 180:
                snippet = snippet[:180] + "..."
            warnings.append(f"API {endpoint} returned {status}: {snippet}")
            continue

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            warnings.append(f"API {endpoint} returned non-JSON response")
            continue

        if not payload.get("success"):
            warnings.append(f"API {endpoint} returned success=false")
            continue

        results = _extract_api_results(payload)
        if results:
            return results[:limit], warnings
        warnings.append(f"API {endpoint} returned no results")

    return [], warnings


def _parse_search_label(label: str) -> Dict[str, str]:
    compact = " ".join(label.split())
    repo_match = re.search(r'from "([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', compact)
    name_match = re.search(r"### export ([A-Za-z0-9_.-]+)", compact)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})$", compact)

    repo = repo_match.group(1) if repo_match else ""
    name = name_match.group(1) if name_match else ""
    updated_at = date_match.group(1) if date_match else ""

    description = ""
    if repo_match:
        desc_start = repo_match.end()
        desc_end = date_match.start() if date_match else len(compact)
        description = compact[desc_start:desc_end].strip(" -")

    return {
        "repo": repo,
        "name": name,
        "updated_at": updated_at,
        "description": description,
    }


def _search_scrape(query: str, limit: int, timeout: int) -> Tuple[List[Dict], List[str]]:
    warnings: List[str] = []
    url = f"{SCRAPE_ENDPOINT}?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "skillsmp-discovery/1.0"}
    status, body = _http_get(url, headers, timeout)
    if status != 200:
        snippet = body.decode("utf-8", errors="replace").strip()
        if len(snippet) > 180:
            snippet = snippet[:180] + "..."
        return [], [f"Scrape endpoint returned {status}: {snippet}"]

    text = body.decode("utf-8", errors="replace")
    pattern = re.compile(r"\[(.+?)\]\((http://skillsmp\.com/skills/[^)]+)\)", re.DOTALL)
    results: List[Dict[str, str]] = []
    seen = set()

    for match in pattern.finditer(text):
        label = match.group(1)
        skill_url = match.group(2)
        parsed = _parse_search_label(label)
        repo = parsed.get("repo", "")
        name = parsed.get("name", "")
        key = (repo, name, skill_url)

        if not repo or key in seen:
            continue
        seen.add(key)

        results.append(
            {
                "source": "scrape",
                "name": name,
                "author": repo.split("/")[0],
                "repo": repo,
                "github_url": f"https://github.com/{repo}",
                "skill_url": skill_url,
                "description": parsed.get("description", ""),
                "stars": "",
                "updated_at": parsed.get("updated_at", ""),
                "score": "",
            }
        )

        if len(results) >= limit:
            break

    if not results:
        warnings.append("No parseable results from scrape response")
    return results, warnings


def _print_text(results: List[Dict], warnings: List[str]) -> None:
    if warnings:
        for warning in warnings:
            print(f"warning: {warning}")
        print("")

    for idx, item in enumerate(results, start=1):
        source = item.get("source") or ""
        name = item.get("name") or "<unknown>"
        print(f"[{idx}] {name} ({source})")
        if item.get("repo"):
            print(f"  repo: {item['repo']}")
        if item.get("github_url"):
            print(f"  github: {item['github_url']}")
        if item.get("skill_url"):
            print(f"  skill_url: {item['skill_url']}")
        if item.get("updated_at"):
            print(f"  updated: {item['updated_at']}")
        if item.get("score"):
            print(f"  score: {item['score']}")
        if item.get("description"):
            print(f"  description: {item['description']}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Search SkillsMP for skills")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument(
        "--mode",
        choices=("auto", "api", "scrape"),
        default="auto",
        help="Search mode",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    query = args.query.strip()
    if not query:
        print("query cannot be empty", file=sys.stderr)
        return 2

    api_key = os.getenv("SKILL_MAP_API_KEY", "").strip()
    warnings: List[str] = []
    results: List[Dict] = []
    mode_used = ""

    if args.mode in ("auto", "api"):
        if not api_key and args.mode == "api":
            print("SKILL_MAP_API_KEY is required for --mode api", file=sys.stderr)
            return 2
        if api_key:
            api_results, api_warnings = _search_api(query, api_key, args.limit, args.timeout)
            warnings.extend(api_warnings)
            if api_results:
                results = api_results
                mode_used = "api"
        elif args.mode == "auto":
            warnings.append("SKILL_MAP_API_KEY not set, using scrape fallback")

    if not results and args.mode in ("auto", "scrape"):
        scrape_results, scrape_warnings = _search_scrape(query, args.limit, args.timeout)
        warnings.extend(scrape_warnings)
        if scrape_results:
            results = scrape_results
            mode_used = "scrape"

    payload = {
        "query": query,
        "mode_requested": args.mode,
        "mode_used": mode_used,
        "count": len(results),
        "warnings": warnings,
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        _print_text(results, warnings)

    return 0 if results else 4


if __name__ == "__main__":
    raise SystemExit(main())
