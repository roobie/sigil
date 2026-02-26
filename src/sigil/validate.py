"""Validation logic for sigil bookmarks."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .context import read_file_lines
from .models import Bookmark, now_iso


@dataclass
class ValidationResult:
    bookmark: Bookmark
    old_status: str
    new_status: str  # valid, moved, stale, missing_file
    new_line: Optional[int] = None  # if moved, where it moved to
    message: str = ""


def validate_bookmark(bookmark: Bookmark, root: Path) -> ValidationResult:
    """Validate a single bookmark against its source file.

    Strategy:
    1. Check exact line match
    2. Search nearby (±10 lines)
    3. Search entire file
    4. Mark as stale if not found
    """
    filepath = root / bookmark.file
    old_status = bookmark.validation.status

    if not filepath.exists():
        return ValidationResult(
            bookmark=bookmark,
            old_status=old_status,
            new_status="missing_file",
            message=f"File not found: {bookmark.file}",
        )

    lines = read_file_lines(filepath)
    if not lines:
        return ValidationResult(
            bookmark=bookmark,
            old_status=old_status,
            new_status="stale",
            message="File is empty",
        )

    target = bookmark.context.target

    # 1. Exact position match
    idx = bookmark.line - 1
    if 0 <= idx < len(lines) and lines[idx] == target:
        return ValidationResult(
            bookmark=bookmark,
            old_status=old_status,
            new_status="valid",
            new_line=bookmark.line,
            message="Exact match at original line",
        )

    # 2. Nearby search (±10 lines)
    search_radius = 10
    start = max(0, idx - search_radius)
    end = min(len(lines), idx + search_radius + 1)

    for i in range(start, end):
        if lines[i] == target:
            # Bonus: check surrounding context too
            if _context_matches(lines, i, bookmark):
                return ValidationResult(
                    bookmark=bookmark,
                    old_status=old_status,
                    new_status="valid",
                    new_line=i + 1,
                    message=f"Found nearby (moved from line {bookmark.line} to {i + 1})",
                )

    # 3. File-wide search
    matches = [i for i, line in enumerate(lines) if line == target]

    if len(matches) == 1:
        new_line = matches[0] + 1
        return ValidationResult(
            bookmark=bookmark,
            old_status=old_status,
            new_status="moved",
            new_line=new_line,
            message=f"Found at line {new_line} (moved from {bookmark.line})",
        )
    elif len(matches) > 1:
        # Multiple matches — try context to disambiguate
        for i in matches:
            if _context_matches(lines, i, bookmark):
                new_line = i + 1
                return ValidationResult(
                    bookmark=bookmark,
                    old_status=old_status,
                    new_status="moved",
                    new_line=new_line,
                    message=f"Found at line {new_line} (disambiguated by context)",
                )
        # Can't disambiguate — report as stale with hint
        match_lines = [m + 1 for m in matches]
        return ValidationResult(
            bookmark=bookmark,
            old_status=old_status,
            new_status="stale",
            message=f"Multiple matches at lines {match_lines}, context doesn't match",
        )

    # 4. Not found anywhere
    return ValidationResult(
        bookmark=bookmark,
        old_status=old_status,
        new_status="stale",
        message="Target line not found in file",
    )


def apply_result(result: ValidationResult, fix: bool = False) -> bool:
    """Apply a validation result to the bookmark. Returns True if bookmark was modified."""
    bm = result.bookmark
    changed = False

    bm.validation.status = result.new_status
    bm.validation.last_checked = now_iso()

    if fix and result.new_line and result.new_line != bm.line:
        bm.line = result.new_line
        changed = True

    if result.new_status != result.old_status:
        changed = True

    return changed


def _context_matches(lines: list[str], idx: int, bookmark: Bookmark) -> bool:
    """Check if surrounding context matches the bookmark's stored context."""
    matches = 0
    total = 0

    if bookmark.context.before:
        total += 1
        if idx > 0 and lines[idx - 1] == bookmark.context.before:
            matches += 1

    if bookmark.context.after:
        total += 1
        if idx < len(lines) - 1 and lines[idx + 1] == bookmark.context.after:
            matches += 1

    # If we have context to compare, require at least one match
    return total == 0 or matches > 0
