"""
FastMCP Server — GitHub PR & CI/CD Diagnostics.

Provides tools to:
    1. get_pr_failed_checks: Inspect PR check-runs and find failing CI/CD action jobs.
    2. get_failed_job_logs: Download raw CI logs and use an intelligent Log Scrubber
       to isolate the exact error traceback/failure window without token bloat.
    3. get_pr_diff: Fetch the unified PR diff so the agent can correlate error logs
       with the exact code changes that introduced the breakage.

Supports:
    - Real GitHub API over HTTPS (with GITHUB_TOKEN for private repos or rate limit avoidance).
    - Auto-detection of repository from git remote.
    - Built-in Mock Mode (e.g. pr_number=42 or fixture fallback) for zero-setup offline testing.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dotenv import load_dotenv
from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP(
    "GitHub-CI-Diagnostics",
    instructions="Provides tools to inspect failed GitHub PR checks, extract scrubbed CI failure logs, and fetch PR diffs.",
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

FIXTURES_DIR = BASE_DIR / "data" / "sample_pr"

# Common patterns to locate error root causes in massive build logs
ERROR_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE),
    re.compile(r"===+ FAILURES ===+", re.IGNORECASE),
    re.compile(r"FAILED\s+[a-zA-Z0-9_/.-]+::", re.IGNORECASE),
    re.compile(r"AssertionError:", re.IGNORECASE),
    re.compile(r"##\[error\]", re.IGNORECASE),
    re.compile(r"error\[E[0-9]+\]:", re.IGNORECASE),
    re.compile(r"npm ERR!", re.IGNORECASE),
    re.compile(r"FATAL:", re.IGNORECASE),
    re.compile(r"Process completed with exit code [1-9]", re.IGNORECASE),
]


def get_default_repo() -> str:
    """Auto-detect GitHub owner/repo from local git remote."""
    try:
        out = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True, stderr=subprocess.DEVNULL).strip()
        # Matches https://github.com/owner/repo.git or git@github.com:owner/repo.git
        m = re.search(r"github\.com[:/]([^/]+/[^/.]+)(?:\.git)?", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return os.getenv("GITHUB_REPOSITORY", "tushar-swami/ai")


def scrub_ci_log(raw_log: str, max_lines: int = 60) -> str:
    """
    Intelligent Log Scrubber:
    Locates error/traceback markers in multi-thousand-line CI logs
    and extracts only the surrounding diagnostic window.
    """
    lines = raw_log.splitlines()
    if not lines:
        return "Log is empty."

    # Scan for first significant error marker
    error_idx = -1
    for i, line in enumerate(lines):
        if any(pat.search(line) for pat in ERROR_PATTERNS):
            error_idx = i
            break

    # If error marker found, extract context window around it
    if error_idx != -1:
        start_idx = max(0, error_idx - 15)
        end_idx = min(len(lines), start_idx + max_lines)
        window = lines[start_idx:end_idx]
        header = f"=== Extracted Error Window (Lines {start_idx + 1}–{end_idx} of {len(lines)}) ==="
        return f"{header}\n\n" + "\n".join(window)

    # Fallback to tail if no standard error marker matched
    tail_lines = lines[-max_lines:]
    header = f"=== Log Tail (Last {len(tail_lines)} lines of {len(lines)}) ==="
    return f"{header}\n\n" + "\n".join(tail_lines)


def call_github_api(endpoint: str, headers: dict = None, as_json: bool = True):
    """Execute authenticated or public GitHub API request."""
    token = os.getenv("GITHUB_TOKEN")
    req_headers = {
        "User-Agent": "AI-Engineering-Agent",
        "Accept": "application/vnd.github+json",
    }
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)

    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    req = urllib.request.Request(url, headers=req_headers)

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            body = response.read().decode("utf-8", errors="replace")
            if as_json:
                return json.loads(body)
            return body
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("GitHub API 401 Unauthorized: Invalid or missing GITHUB_TOKEN.")
        elif e.code == 403:
            raise RuntimeError("GitHub API 403 Forbidden: API rate limit exceeded. Set GITHUB_TOKEN in .env.")
        elif e.code == 404:
            raise RuntimeError(f"GitHub API 404: Resource '{endpoint}' not found (verify repo and PR number).")
        raise RuntimeError(f"GitHub API HTTP {e.code}: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"GitHub network request failed: {e}")


# ── Tool 0: List Pull Requests ────────────────────────────────────────
@mcp.tool(
    name="list_prs",
    description=(
        "List Pull Requests on GitHub for a repository (defaulting to the current repository). "
        "Supports filtering by state ('open', 'closed', 'all'). "
        "Returns PR numbers, titles, authors, branches, and CI statuses."
    ),
)
def list_prs(state: str = "open", repo: str | None = None) -> str:
    """List pull requests with their title, number, author, branch, and status."""
    target_repo = (repo or "").strip() or get_default_repo()

    # Use mock fixture only for default private repo when no GITHUB_TOKEN is configured
    if not os.getenv("GITHUB_TOKEN") and target_repo == get_default_repo():
        prs_file = FIXTURES_DIR / "prs.json"
        if prs_file.exists():
            try:
                prs = json.loads(prs_file.read_text(encoding="utf-8"))
                if state != "all":
                    prs = [p for p in prs if p.get("state") == state]
                lines = [
                    f"=== Pull Requests for {target_repo} (state: {state}) ===",
                    "[Notice: 'tushar-swami/ai' is a private repository. To query live private PRs, set GITHUB_TOKEN in Day02-mcp/.env. Displaying local PRs:]\n"
                ]
                for p in prs:
                    lines.append(
                        f"• PR #{p['number']}: {p['title']}\n"
                        f"  State:   {p.get('state', 'open').upper()}\n"
                        f"  Author:  {p.get('user', 'unknown')}\n"
                        f"  Branch:  {p.get('head_branch', 'feature')} -> {p.get('base_branch', 'main')}\n"
                        f"  CI:      {p.get('ci_status', 'UNKNOWN')}\n"
                    )
                return "\n".join(lines)
            except Exception:
                pass

    # Real GitHub API Path (works for public repos or authenticated private repos)
    try:
        prs_data = call_github_api(f"/repos/{target_repo}/pulls?state={state}&per_page=10")
        if not prs_data:
            return f"No {state} pull requests found for {target_repo}."

        lines = [f"=== Pull Requests for {target_repo} (state: {state}) ==="]
        for p in prs_data:
            lines.append(
                f"• PR #{p['number']}: {p['title']}\n"
                f"  State:   {p.get('state', 'open').upper()}\n"
                f"  Author:  {p.get('user', {}).get('login', 'unknown')}\n"
                f"  Branch:  {p.get('head', {}).get('ref', '')} -> {p.get('base', {}).get('ref', 'main')}\n"
                f"  URL:     {p.get('html_url', '')}\n"
            )
        return "\n".join(lines)
    except Exception as e:
        prs_file = FIXTURES_DIR / "prs.json"
        if prs_file.exists():
            return (
                f"[Notice: Live GitHub API returned: {e}. Falling back to sample PR fixtures]\n\n"
                + list_prs(state=state, repo="tushar-swami/ai")
            )
        return f"Error listing pull requests: {e}"


# ── Tool 1: Get PR Failed Checks ──────────────────────────────────────
@mcp.tool(
    name="get_pr_failed_checks",
    description=(
        "Fetch failed CI/CD tasks, checks, and GitHub Action workflows for a specific Pull Request. "
        "Returns the list of failing job names, job IDs, and URLs needed to retrieve logs."
    ),
)
def get_pr_failed_checks(pr_number: int, repo: str | None = None) -> str:
    """Inspect PR check runs and return only failed tasks."""
    target_repo = (repo or "").strip() or get_default_repo()

    # Built-in Mock Fixture for PR #42 or offline demonstration
    if int(pr_number) == 42 or not os.getenv("GITHUB_TOKEN"):
        checks_file = FIXTURES_DIR / "checks.json"
        if checks_file.exists():
            try:
                data = json.loads(checks_file.read_text(encoding="utf-8"))
                failed = [c for c in data.get("check_runs", []) if c.get("conclusion") in ("failure", "timed_out", "action_required")]
                if not failed:
                    return f"✓ All check runs passed for PR #{pr_number} in {target_repo}."

                lines = [f"=== Failed Checks for PR #{pr_number} ({target_repo}) ==="]
                for c in failed:
                    lines.append(
                        f"• Job Name:   {c['name']}\n"
                        f"  Job ID:     {c['id']}\n"
                        f"  Conclusion: {c.get('conclusion', 'unknown').upper()}\n"
                        f"  URL:        {c.get('html_url', 'N/A')}\n"
                    )
                return "\n".join(lines)
            except Exception:
                pass

    # Real GitHub API Path
    try:
        # Step A: Get head commit SHA of the PR
        pr_data = call_github_api(f"/repos/{target_repo}/pulls/{pr_number}")
        head_sha = pr_data.get("head", {}).get("sha")
        if not head_sha:
            return f"Error: Could not determine head commit SHA for PR #{pr_number}."

        # Step B: Query Check Runs for that commit
        checks_data = call_github_api(f"/repos/{target_repo}/commits/{head_sha}/check-runs")
        check_runs = checks_data.get("check_runs", [])

        failed = [
            c for c in check_runs
            if c.get("conclusion") in ("failure", "timed_out", "action_required")
        ]

        if not failed:
            return f"✓ All {len(check_runs)} checks passed on PR #{pr_number} in {target_repo}."

        lines = [f"=== Failed Checks for PR #{pr_number} ({target_repo}) ==="]
        for c in failed:
            lines.append(
                f"• Job Name:   {c['name']}\n"
                f"  Job ID:     {c['id']}\n"
                f"  Conclusion: {c.get('conclusion', 'unknown').upper()}\n"
                f"  URL:        {c.get('html_url', 'N/A')}\n"
            )
        return "\n".join(lines)

    except Exception as e:
        # Fallback to mock fixture if repo is private and unauthenticated
        checks_file = FIXTURES_DIR / "checks.json"
        if checks_file.exists():
            return (
                f"[Notice: Live GitHub API returned: {e}. Falling back to sample PR #42 fixture]\n\n"
                + get_pr_failed_checks(pr_number=42, repo="tushar-swami/ai")
            )
        return f"Error fetching PR checks: {e}"


# ── Tool 2: Get Failed Job Logs (with Log Scrubber) ────────────────────
@mcp.tool(
    name="get_failed_job_logs",
    description=(
        "Fetch and intelligently scrub the execution logs of a failed GitHub Action job. "
        "Extracts the critical failure window and traceback lines while filtering out thousands of lines of build noise."
    ),
)
def get_failed_job_logs(job_id: int | str, repo: str | None = None, max_lines: int = 60) -> str:
    """Download job logs and return scrubbed failure traceback."""
    target_repo = (repo or "").strip() or get_default_repo()

    # Built-in Mock Fixture for job_id 987654321
    if str(job_id) in ("987654321", "42", "mock") or not os.getenv("GITHUB_TOKEN"):
        log_file = FIXTURES_DIR / "failed_test_log.txt"
        if log_file.exists():
            raw_log = log_file.read_text(encoding="utf-8", errors="replace")
            return scrub_ci_log(raw_log, max_lines=max_lines)

    # Real GitHub API Path
    try:
        raw_log = call_github_api(
            f"/repos/{target_repo}/actions/jobs/{job_id}/logs",
            as_json=False,
        )
        return scrub_ci_log(raw_log, max_lines=max_lines)

    except Exception as e:
        log_file = FIXTURES_DIR / "failed_test_log.txt"
        if log_file.exists():
            return (
                f"[Notice: Live log fetch failed: {e}. Showing sample failure log fixture]\n\n"
                + scrub_ci_log(log_file.read_text(encoding="utf-8", errors="replace"), max_lines=max_lines)
            )
        return f"Error retrieving logs for job {job_id}: {e}"


# ── Tool 3: Get PR Diff ───────────────────────────────────────────────
@mcp.tool(
    name="get_pr_diff",
    description=(
        "Fetch the unified git diff of a Pull Request to see what code changes were introduced. "
        "Allows correlating the test/CI failure with the modified source files."
    ),
)
def get_pr_diff(pr_number: int, repo: str | None = None) -> str:
    """Fetch the unified diff of the PR."""
    target_repo = (repo or "").strip() or get_default_repo()

    # Built-in Mock Fixture for PR #42
    if int(pr_number) == 42 or not os.getenv("GITHUB_TOKEN"):
        diff_file = FIXTURES_DIR / "pr_diff.patch"
        if diff_file.exists():
            return diff_file.read_text(encoding="utf-8", errors="replace")

    # Real GitHub API Path
    try:
        diff_text = call_github_api(
            f"/repos/{target_repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
            as_json=False,
        )
        if len(diff_text) > 8000:
            return diff_text[:8000] + "\n\n... [Diff truncated to first 8000 chars]"
        return diff_text

    except Exception as e:
        diff_file = FIXTURES_DIR / "pr_diff.patch"
        if diff_file.exists():
            return (
                f"[Notice: Live PR diff failed: {e}. Showing sample PR diff fixture]\n\n"
                + diff_file.read_text(encoding="utf-8", errors="replace")
            )
        return f"Error retrieving PR diff: {e}"


if __name__ == "__main__":
    mcp.run(show_banner=False)
