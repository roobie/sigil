"""JSONL + context file storage for sigil bookmarks.

Storage layout:
  .sigil/
    bookmarks.jsonl          # one JSON object per line (metadata only)
    contexts/
      bm_1709123456_a3f5.ctx # raw context lines, no escaping
"""

import json
import os
from pathlib import Path
from typing import Optional

from .models import Bookmark, Context, Metadata, Validation

SIGIL_DIR = ".sigil"
BOOKMARKS_FILE = "bookmarks.jsonl"
CONTEXTS_DIR = "contexts"

# Context file uses >>> to mark the target line
CONTEXT_TARGET_MARKER = ">>> "


def find_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from start directory to find a .sigil/ or .git/ directory."""
    current = (start or Path.cwd()).resolve()

    # First pass: look for .sigil/
    check = current
    while True:
        if (check / SIGIL_DIR).is_dir():
            return check
        if check.parent == check:
            break
        check = check.parent

    # Fallback: look for .git/
    check = current
    while True:
        if (check / ".git").exists():
            return check
        if check.parent == check:
            break
        check = check.parent

    return None


def ensure_storage(root: Path) -> Path:
    """Ensure .sigil directory structure exists. Returns path to .sigil/."""
    sigil_dir = root / SIGIL_DIR
    sigil_dir.mkdir(exist_ok=True)
    (sigil_dir / CONTEXTS_DIR).mkdir(exist_ok=True)

    bookmarks_path = sigil_dir / BOOKMARKS_FILE
    if not bookmarks_path.exists():
        bookmarks_path.write_text("", encoding="utf-8")

    return sigil_dir


def load_bookmarks(sigil_dir: Path) -> list[Bookmark]:
    """Load all bookmarks from JSONL + context files."""
    bookmarks_path = sigil_dir / BOOKMARKS_FILE
    contexts_dir = sigil_dir / CONTEXTS_DIR

    bookmarks = []
    for line in bookmarks_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        context = _load_context(contexts_dir, data["id"])
        bookmarks.append(_from_jsonl(data, context))

    return bookmarks


def save_bookmarks(sigil_dir: Path, bookmarks: list[Bookmark]) -> None:
    """Save all bookmarks to JSONL + context files."""
    bookmarks_path = sigil_dir / BOOKMARKS_FILE
    contexts_dir = sigil_dir / CONTEXTS_DIR

    # Write JSONL (atomic-ish)
    lines = [json.dumps(_to_jsonl(bm), separators=(",", ":")) for bm in bookmarks]
    tmp = bookmarks_path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    tmp.replace(bookmarks_path)

    # Write context files
    existing_ctx = set(p.stem for p in contexts_dir.glob("*.ctx"))
    current_ids = set()

    for bm in bookmarks:
        current_ids.add(bm.id)
        _save_context(contexts_dir, bm.id, bm.context)

    # Clean up orphaned context files
    for orphan_id in existing_ctx - current_ids:
        (contexts_dir / f"{orphan_id}.ctx").unlink(missing_ok=True)


def get_relative_path(filepath: Path, root: Path) -> str:
    """Get path relative to repository root."""
    try:
        return str(filepath.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(filepath.resolve())


# --- Context file I/O ---


def _save_context(contexts_dir: Path, bookmark_id: str, context: Context) -> None:
    """Write a .ctx file with raw context lines."""
    lines = []
    if context.before:
        lines.append(f"    {context.before}")
    lines.append(f"{CONTEXT_TARGET_MARKER}{context.target}")
    if context.after:
        lines.append(f"    {context.after}")
    (contexts_dir / f"{bookmark_id}.ctx").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_context(contexts_dir: Path, bookmark_id: str) -> Context:
    """Read a .ctx file back into a Context object."""
    ctx_path = contexts_dir / f"{bookmark_id}.ctx"
    if not ctx_path.exists():
        return Context(before="", target="", after="")

    before = ""
    target = ""
    after = ""

    lines = ctx_path.read_text(encoding="utf-8").splitlines()
    target_idx = None

    for i, line in enumerate(lines):
        if line.startswith(CONTEXT_TARGET_MARKER):
            target = line[len(CONTEXT_TARGET_MARKER) :]
            target_idx = i
            break

    if target_idx is not None:
        if target_idx > 0:
            before = lines[target_idx - 1].removeprefix("    ")
        if target_idx < len(lines) - 1:
            after = lines[target_idx + 1].removeprefix("    ")

    return Context(before=before, target=target, after=after)


# --- JSONL serialization (metadata only, no code content) ---


def _to_jsonl(bm: Bookmark) -> dict:
    """Bookmark -> flat dict for one JSONL line."""
    return {
        "id": bm.id,
        "file": bm.file,
        "line": bm.line,
        "tags": bm.metadata.tags,
        "desc": bm.metadata.description,
        "status": bm.validation.status,
        "created": bm.metadata.created,
        "accessed": bm.metadata.accessed,
        "checked": bm.validation.last_checked,
    }


def _from_jsonl(data: dict, context: Context) -> Bookmark:
    """JSONL dict + Context -> Bookmark."""
    return Bookmark(
        id=data["id"],
        file=data["file"],
        line=data["line"],
        context=context,
        metadata=Metadata(
            tags=data.get("tags", []),
            description=data.get("desc", ""),
            created=data.get("created", ""),
            accessed=data.get("accessed", ""),
        ),
        validation=Validation(
            status=data.get("status", "unknown"),
            last_checked=data.get("checked", ""),
        ),
    )
