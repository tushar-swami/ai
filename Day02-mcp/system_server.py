"""
FastMCP Server — System & Utility Tools.

Provides file inspection, date/time, security utilities, and knowledge base search.
Runs as an independent child process communicating via JSON-RPC 2.0 over standard I/O (stdio).
"""

from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
import re
import secrets
import string
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP(
    "System-Tools",
    instructions="Provides local file operations, time/date queries, security tools, and knowledge search.",
)

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

# Character sets for password generation
LOWER_CHARS = string.ascii_lowercase
UPPER_CHARS = string.ascii_uppercase
DIGIT_CHARS = string.digits
SPECIAL_CHARS = "!@#$%^&*-_=+"
ALPHANUMERIC_CHARS = LOWER_CHARS + UPPER_CHARS + DIGIT_CHARS
ALL_CHARS = ALPHANUMERIC_CHARS + SPECIAL_CHARS

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't",
    "it", "its", "itself", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
}


# ── 1. Datetime Tool ──────────────────────────────────────────────────
@mcp.tool(
    name="get_current_datetime",
    description="Fetch current date, time, or full datetime. format_type can be 'time', 'date', or 'all'.",
)
def get_current_datetime(format_type: str = "all", timezone_str: str = "local") -> str:
    """Fetch current date, time, or full timestamp."""
    try:
        now = (
            datetime.now().astimezone()
            if timezone_str.lower() in ("local", "system", "")
            else datetime.now(ZoneInfo(timezone_str))
        )
    except ZoneInfoNotFoundError:
        now = datetime.now().astimezone()

    if format_type == "time":
        return now.strftime("%H:%M:%S")
    if format_type == "date":
        return now.strftime("%d-%m-%Y")
    return now.strftime("%d-%m-%Y %H:%M:%S")


# ── 2. Dice Tool ──────────────────────────────────────────────────────
@mcp.tool(
    name="roll_dice",
    description="Roll an N-sided die and return the resulting integer.",
)
def roll_dice(sides: int = 6) -> int:
    """Roll an N-sided die."""
    sides = max(2, int(sides)) if sides else 6
    return secrets.randbelow(sides) + 1


# ── 3. Password Generator Tool ────────────────────────────────────────
@mcp.tool(
    name="generate_password",
    description="Generate a cryptographically secure random password.",
)
def generate_password(length: int = 12, include_special: bool = True) -> str:
    """Generate a cryptographically secure random password."""
    try:
        length = max(4, int(length))
    except (ValueError, TypeError):
        length = 12

    chars = ALL_CHARS if include_special else ALPHANUMERIC_CHARS
    pwd = [
        secrets.choice(LOWER_CHARS),
        secrets.choice(UPPER_CHARS),
        secrets.choice(DIGIT_CHARS),
    ]
    if include_special:
        pwd.append(secrets.choice(SPECIAL_CHARS))

    pwd.extend(secrets.choice(chars) for _ in range(length - len(pwd)))
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


# ── 4. File List Tool ─────────────────────────────────────────────────
@mcp.tool(
    name="list_files",
    description="List all available text files in the knowledge base and data directories.",
)
def list_files(directory: str = "all") -> str:
    """List available files with line counts across knowledge/ and data/ directories."""
    directory = (directory or "all").lower().strip()
    sections: list[str] = []

    if directory in ("all", "knowledge") and KNOWLEDGE_DIR.exists():
        k_files = sorted([f for f in KNOWLEDGE_DIR.iterdir() if f.is_file() and not f.name.startswith(".")])
        if k_files:
            lines = ["📂 Knowledge Base Files (knowledge/):"]
            for f in k_files:
                try:
                    count = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                    lines.append(f"  • {f.name} ({count} lines)")
                except Exception:
                    lines.append(f"  • {f.name}")
            sections.append("\n".join(lines))

    if directory in ("all", "data") and DATA_DIR.exists():
        d_files = sorted([f for f in DATA_DIR.iterdir() if f.is_file() and not f.name.startswith(".")])
        if d_files:
            lines = ["📁 Data Files (data/):"]
            for f in d_files:
                try:
                    count = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                    lines.append(f"  • {f.name} ({count} lines)")
                except Exception:
                    lines.append(f"  • {f.name}")
            sections.append("\n".join(lines))

    if not sections:
        return "No files found in the specified directory."

    return "\n\n".join(sections)


# ── 5. File Read Tool ─────────────────────────────────────────────────
@mcp.tool(
    name="read_file",
    description="Read the text content of a local file from knowledge/ or data/ (e.g. 'japan.txt', 'test.txt').",
)
def read_file(file_path: str, max_chars: int = 10000) -> str:
    """Read file content safely within the workspace."""
    cleaned = str(file_path).strip().lower() if file_path else ""
    if not cleaned or cleaned in ("list", "all", "ls", "dir", "files"):
        return f"Here are the available files:\n\n{list_files()}"

    input_path = Path(file_path.strip())
    candidates: list[Path] = []
    if input_path.is_absolute():
        candidates.append(input_path)
    else:
        candidates.append(KNOWLEDGE_DIR / input_path)
        candidates.append(DATA_DIR / input_path)
        candidates.append(BASE_DIR / input_path)
        candidates.append(WORKSPACE_ROOT / input_path)
        candidates.append(Path.cwd() / input_path)

    resolved_path: Path | None = None
    for candidate in candidates:
        if candidate.is_file():
            resolved_path = candidate.resolve()
            break

    if not resolved_path:
        return f"Error: File '{file_path}' not found."

    # Workspace boundary check
    try:
        resolved_path.relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        return f"Error: Access denied. File '{file_path}' is outside authorized workspace."

    try:
        content = resolved_path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            return content[:max_chars] + f"\n\n[Warning: Truncated to first {max_chars} chars.]"
        return content
    except Exception as e:
        return f"Error reading file '{file_path}': {e}"


# ── 6. Knowledge Base Search Tool (Pure-Python BM25) ──────────────────
@mcp.tool(
    name="search_knowledge",
    description="Search indexed knowledge files (Japan, snow leopard, Marie Curie, alien life, deep ocean).",
)
def search_knowledge(query: str, top_k: int = 3) -> str:
    """Search knowledge documents using lightweight BM25 scoring."""
    if not query or not query.strip():
        return "Error: No search query provided."

    try:
        top_k = max(1, min(10, int(top_k)))
    except (ValueError, TypeError):
        top_k = 3

    if not KNOWLEDGE_DIR.exists():
        return "Error: knowledge/ directory does not exist."

    # Tokenize
    query_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_]+\b", query) if w.lower() not in STOPWORDS]
    if not query_tokens:
        return "No valid search keywords found in query."

    # Load and chunk documents
    chunks = []
    for f in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            step = 10
            for start in range(0, len(lines), step):
                chunk_lines = lines[start:start + 15]
                text = "\n".join(chunk_lines).strip()
                if text:
                    tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_]+\b", text) if w.lower() not in STOPWORDS]
                    chunks.append({
                        "file": f.name,
                        "line_start": start + 1,
                        "line_end": min(len(lines), start + 15),
                        "text": text,
                        "tokens": tokens,
                    })
        except Exception:
            continue

    if not chunks:
        return "No documents available in knowledge database."

    # BM25 Scoring
    N = len(chunks)
    avgdl = sum(len(c["tokens"]) for c in chunks) / max(1, N)
    k1, b = 1.5, 0.75

    scores = []
    for c in chunks:
        doc_len = len(c["tokens"])
        tf = Counter(c["tokens"])
        score = 0.0
        for token in query_tokens:
            if token in tf:
                df = sum(1 for ch in chunks if token in ch["tokens"])
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                freq = tf[token]
                num = freq * (k1 + 1.0)
                denom = freq + k1 * (1.0 - b + b * (doc_len / avgdl))
                score += idf * (num / denom)
        if score > 0.0:
            scores.append((score, c))

    scores.sort(key=lambda x: x[0], reverse=True)
    top_matches = scores[:top_k]

    if not top_matches:
        return f"No relevant excerpts found for query: '{query}'."

    results = [f"=== Top {len(top_matches)} Knowledge Base Matches ==="]
    for rank, (score, c) in enumerate(top_matches, 1):
        results.append(
            f"\n[Match {rank} | Score: {score:.3f}] Source: {c['file']} (Lines {c['line_start']}-{c['line_end']})\n{c['text']}"
        )

    return "\n".join(results)


# ── 7. Task & Incident History Tools (Persistent Operational Memory) ──────────
@mcp.tool(
    name="list_past_tasks",
    description=(
        "List previously executed DevOps tasks, diagnostic investigations, and remediation actions "
        "from the persistent operational task journal (SQLite ledger). "
        "Supports filtering by domain ('kubernetes', 'github', 'system') and limit."
    ),
)
def list_past_tasks(limit: int = 5, domain: str | None = None) -> str:
    """List recent tasks in an agent-friendly, token-efficient format."""
    try:
        from task_journal import task_journal
        tasks = task_journal.list_recent_tasks(limit=limit, domain=domain)
        if not tasks:
            return "No previous tasks recorded in the operational journal."

        lines = [f"=== Operational Task Journal ({len(tasks)} recent entries) ==="]
        for t in tasks:
            lines.append(task_journal.format_agent_card(t))
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error retrieving task journal: {e}"


@mcp.tool(
    name="search_past_tasks",
    description=(
        "Search the persistent task journal for past incidents, error tracebacks, pod names, PR numbers, "
        "or resolutions using hybrid lexical (SQLite FTS5) and semantic vector search."
    ),
)
def search_past_tasks(query: str, limit: int = 5) -> str:
    """Hybrid search across task history by keyword, pod name, or conceptual description."""
    try:
        from task_journal import task_journal
        clean_q = (query or "").strip()
        if not clean_q:
            return "Error: Search query cannot be empty."

        results = task_journal.search_tasks(clean_q, limit=limit)
        if not results:
            return f"No past tasks found matching '{clean_q}'."

        lines = [f"=== Past Task Matches for: '{clean_q}' ({len(results)} found) ==="]
        for t in results:
            lines.append(task_journal.format_agent_card(t))
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching task journal: {e}"


@mcp.tool(
    name="get_past_task_details",
    description=(
        "Retrieve full verbatim diagnostic logs, manifest diffs, and git commits "
        "for a specific past task ID (e.g. 'k8s-20261005-201430')."
    ),
)
def get_past_task_details(task_id: str) -> str:
    """Retrieve full details and unpruned diagnostic logs for a past task."""
    try:
        from task_journal import task_journal
        tid = (task_id or "").strip()
        if not tid:
            return "Error: 'task_id' is required."

        task = task_journal.get_task_by_id(tid)
        if not task:
            return f"No task found with ID '{tid}'."

        card = task_journal.format_agent_card(task)
        details = task.get("details", {})
        details_formatted = json.dumps(details, indent=2, ensure_ascii=False) if details else "{}"

        return (
            f"=== Full Details for Task: {tid} ===\n\n"
            f"{card}\n\n"
            f"**Query**: {task.get('user_query')}\n"
            f"**Detailed Diagnostic & Remediation Artifacts**:\n"
            f"```json\n{details_formatted}\n```"
        )
    except Exception as e:
        return f"Error retrieving task details: {e}"


if __name__ == "__main__":
    mcp.run(show_banner=False)
