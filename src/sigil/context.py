"""Extract context lines from source files."""

from pathlib import Path
from .models import Context


def extract_context(filepath: Path, line_number: int) -> Context:
    """Extract target line and surrounding context from a file.

    Args:
        filepath: Path to the source file
        line_number: 1-based line number to bookmark

    Returns:
        Context with before, target, and after lines

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If line number is out of range
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    lines = filepath.read_text(encoding="utf-8").splitlines()

    if line_number < 1 or line_number > len(lines):
        raise ValueError(
            f"Line {line_number} out of range (file has {len(lines)} lines)"
        )

    idx = line_number - 1  # convert to 0-based

    before = lines[idx - 1] if idx > 0 else ""
    target = lines[idx]
    after = lines[idx + 1] if idx < len(lines) - 1 else ""

    return Context(before=before, target=target, after=after)


def read_file_lines(filepath: Path) -> list[str]:
    """Read all lines from a file. Returns empty list if file doesn't exist."""
    if not filepath.exists():
        return []
    return filepath.read_text(encoding="utf-8").splitlines()
