"""
File tools — file reading and inspection utilities.
"""

from pathlib import Path
import sys

from tools.registry import tool

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DAY01_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = DAY01_DIR / "data"
KNOWLEDGE_DIR = DAY01_DIR / "knowledge"


@tool(
    description="Read the text content of a local file from knowledge/ or data/ (e.g. 'japan.txt', 'snow_leopard.txt', 'alien_life.txt', 'test.txt').",
    parameters={
        "file_path": {
            "type": "string",
            "description": "The name or path of the file to read (e.g., 'japan.txt', 'snow_leopard.txt', 'alien_life.txt', 'test.txt').",
        },
    },
)
def read_file(file_path: str, max_chars: int = 10000) -> str:
    """
    Read text contents of a file within the workspace safely.

    Args:
        file_path: Relative or absolute path or filename.
        max_chars: Maximum characters to read (defaults to 10,000 to protect context).

    Returns:
        str: File content or an error message if not found or inaccessible.
    """
    if not file_path or not str(file_path).strip():
        return "Error: No file path provided."

    input_path = Path(file_path.strip())

    # Build candidate locations to search
    candidates: list[Path] = []
    if input_path.is_absolute():
        candidates.append(input_path)
    else:
        # Check knowledge and data directories first, then Day01, workspace root, and cwd
        candidates.append(KNOWLEDGE_DIR / input_path)
        candidates.append(DATA_DIR / input_path)
        candidates.append(DAY01_DIR / input_path)
        candidates.append(WORKSPACE_ROOT / input_path)
        candidates.append(Path.cwd() / input_path)

    resolved_path: Path | None = None
    for candidate in candidates:
        if candidate.is_file():
            resolved_path = candidate.resolve()
            break

    # If file wasn't found, return helpful diagnostic with available files
    if not resolved_path:
        avail: list[str] = []
        if KNOWLEDGE_DIR.exists():
            k_files = [f.name for f in KNOWLEDGE_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]
            if k_files:
                avail.append(f"knowledge/: {', '.join(sorted(k_files))}")
        if DATA_DIR.exists():
            d_files = [f.name for f in DATA_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]
            if d_files:
                avail.append(f"data/: {', '.join(sorted(d_files))}")
        suggestions = f" Available files -> {' | '.join(avail)}" if avail else ""
        return f"Error: File '{file_path}' not found.{suggestions}"

    # Security check: must reside inside authorized workspace
    try:
        resolved_path.relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        return f"Error: Access denied. File '{file_path}' is outside the authorized workspace."

    try:
        content = resolved_path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            return (
                content[:max_chars]
                + f"\n\n[Warning: Content truncated. Showing first {max_chars} of {len(content)} characters.]"
            )
        return content
    except Exception as e:
        return f"Error reading file '{file_path}': {e}"


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "test.txt"
    print(f"Reading '{target}':\n")
    print(read_file(target))
