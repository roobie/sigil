"""CLI interface for sigil."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__
from .models import Bookmark, Context, Metadata, Validation, generate_id, now_iso
from .context import extract_context
from .storage import (
    find_root,
    ensure_storage,
    load_bookmarks,
    save_bookmarks,
    get_relative_path,
)
from .validate import validate_bookmark, apply_result


def main():
    parser = argparse.ArgumentParser(
        prog="sigil",
        description=(
            "Bookmark code locations with context-aware validation. "
            "Invoke `sg primer` for a crash course in how to use this tool."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  sg init                                Initialize sigil in this repo\n"
            "  sg add src/main.py:42 -t bug,perf -d \"check this loop\"\n"
            "  sg list --json                          Output all bookmarks as JSON\n"
            "  sg list -t cli,feature                  Show bookmarks with those tags\n"
            "  sg show bm_123456                       Show full details for a bookmark\n"
            "  sg show bm_123456 --json               Show bookmark as JSON (machine-readable)\n"
            "  sg search file:src tag:cli handler      Search bookmarks scoped to file and tag\n"
            "  sg validate --fix                       Validate and optionally fix line numbers\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"sigil {__version__}")

    sub = parser.add_subparsers(dest="command")

    # --- primer ---
    sub.add_parser(
        "primer",
        help=(
            "Prints the PRIMER.md (do this as part of discovery on how to use this tool). "
            "Run this first when onboarding to a repository that uses sigil."
        ),
    )

    # --- init ---
    sub.add_parser(
        "init",
        help=(
            "Initialize sigil in current directory. Creates a .sigil/ directory and starter files."
        ),
    )

    # --- add ---
    p_add = sub.add_parser(
        "add",
        help=(
            "Add a bookmark. Location must be file:line (example: src/main.py:42). "
            "Use -t/--tags to attach comma-separated tags and -d/--desc for a short description."
        ),
    )
    p_add.add_argument("location", help="file:line (e.g. src/main.py:42)")
    p_add.add_argument("-t", "--tags", help="Comma-separated tags")
    p_add.add_argument("-d", "--desc", default="", help="Description")

    # --- list ---
    p_list = sub.add_parser(
        "list",
        aliases=["ls"],
        help=(
            "List bookmarks. By default prints a human-friendly table. Use --json to output machine-readable JSON."
        ),
    )
    p_list.add_argument("-t", "--tags", help="Filter by tags (comma-separated)")
    p_list.add_argument("-f", "--file", help="Filter by file pattern")
    p_list.add_argument(
        "--stale", action="store_true", help="Show only stale bookmarks"
    )
    p_list.add_argument(
        "--json", action="store_true", dest="as_json", help="Output as JSON"
    )
    p_list.add_argument(
        "--long", action="store_true", dest="as_long", help="Long definition-list style output"
    )

    # --- show ---
    p_show = sub.add_parser(
        "show",
        help=(
            "Show bookmark details. Specify the full or partial bookmark ID. "
            "With --json outputs a structured JSON object (useful for scripts)."
        ),
    )
    p_show.add_argument("id", help="Bookmark ID (or partial match)")
    p_show.add_argument(
        "--json", action="store_true", dest="as_json", help="Output this bookmark as JSON"
    )

    # --- delete ---
    p_del = sub.add_parser(
        "delete",
        aliases=["rm"],
        help=(
            "Delete a bookmark by ID or remove all bookmarks that match --tags. "
            "Be careful: deletions are immediate."
        ),
    )
    p_del.add_argument("id", nargs="?", help="Bookmark ID (or partial match)")
    p_del.add_argument("-t", "--tags", help="Delete all with these tags")

    # --- validate ---
    p_val = sub.add_parser(
        "validate",
        help=(
            "Validate all bookmarks against their source files. Reports status per bookmark. "
            "Use --fix to automatically update line numbers when a target has moved. Use --json for a machine-readable report."
        ),
    )
    p_val.add_argument("--fix", action="store_true", help="Auto-fix line numbers")
    p_val.add_argument(
        "--unsafe", action="store_true",
        help=(
            "When used with --fix, perform unsafe fixes such as trimming duplicate bookmarks. "
            "This will delete bookmark entries and cannot be undone."
        ),
    )
    p_val.add_argument(
        "--json", action="store_true", dest="as_json", help="Output validation results as JSON"
    )

    # --- search ---
    p_search = sub.add_parser(
        "search",
        help=(
            "Search bookmarks. Supply one or more search terms; all must match. "
            "Prefix a term with tag: or file: to scope the search. Use --json to emit results as JSON."
        ),
    )
    p_search.add_argument("query", nargs="+", help="Search terms (all must match); prefix with tag: or file: to scope")
    p_search.add_argument("-n", "--limit", type=int, default=0, metavar="N", help="Show top N results")
    p_search.add_argument(
        "--json", action="store_true", dest="as_json", help="Output search results as JSON"
    )

    # --- move ---
    p_move = sub.add_parser(
        "move",
        help=(
            "Reposition a bookmark within the list or move it to a new file/line. "
            "Target formats: +N, -N (relative), N (absolute line), or file:line."
        ),
    )
    p_move.add_argument("id", help="Bookmark ID (or partial match)")
    p_move.add_argument(
        "target",
        help="New position: +N (relative), -N (relative), N (absolute), or file:line",
    )

    # --- edit ---
    p_edit = sub.add_parser(
        "edit",
        help=(
            "Edit bookmark metadata in $EDITOR. Opens a temp file where you can update tags and description. "
            "Lines starting with # are ignored. Save and close to apply changes."
        ),
    )
    p_edit.add_argument("id", help="Bookmark ID (or partial match)")

    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    if not args.command:
        parser.print_help()
        return

    # Dispatch
    commands = {
        "init": cmd_init,
        "add": cmd_add,
        "list": cmd_list,
        "ls": cmd_list,
        "show": cmd_show,
        "delete": cmd_delete,
        "rm": cmd_delete,
        "validate": cmd_validate,
        "search": cmd_search,
        "move": cmd_move,
        "edit": cmd_edit,
        "primer": cmd_primer,
    }

    fn = commands.get(args.command)
    if fn:
        try:
            fn(args)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


# ---------- Commands ----------
#


def cmd_primer(args):
    script_dir = Path(__file__).resolve().parent
    with open(script_dir / "PRIMER.md", encoding="utf-8") as f:
        primer = f.read()
    print(primer)


def cmd_init(args):
    root = Path.cwd()
    sigil_dir = ensure_storage(root)
    print(f"Initialized sigil in {sigil_dir}")


def cmd_add(args):
    root, sigil_dir, bookmarks = _load()

    # Parse file:line
    if ":" not in args.location:
        print(
            "Error: Location must be file:line (e.g. src/main.py:42)", file=sys.stderr
        )
        sys.exit(1)

    parts = args.location.rsplit(":", 1)
    filepath = Path(parts[0])
    try:
        line = int(parts[1])
    except ValueError:
        print(f"Error: Invalid line number: {parts[1]}", file=sys.stderr)
        sys.exit(1)

    # Resolve filepath relative to root
    if not filepath.is_absolute():
        filepath = Path.cwd() / filepath

    rel_path = get_relative_path(filepath, root)
    context = extract_context(filepath, line)

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    now = now_iso()

    bookmark = Bookmark(
        id=generate_id(),
        file=rel_path,
        line=line,
        context=context,
        metadata=Metadata(
            tags=tags,
            description=args.desc,
            created=now,
            accessed=now,
        ),
        validation=Validation(
            status="valid",
            last_checked=now,
        ),
    )

    bookmarks.append(bookmark)
    save_bookmarks(sigil_dir, bookmarks)

    print(f"Added bookmark {bookmark.short_id} → {rel_path}:{line}")
    if tags:
        print(f"  Tags: {', '.join(tags)}")
    if args.desc:
        print(f"  Desc: {args.desc}")
    print(f"  Context: {context.target.strip()}")


def cmd_list(args):
    root, sigil_dir, bookmarks = _load()

    # Filter
    if args.tags:
        filter_tags = set(t.strip() for t in args.tags.split(","))
        bookmarks = [b for b in bookmarks if filter_tags & set(b.metadata.tags)]

    if args.file:
        pattern = args.file
        bookmarks = [b for b in bookmarks if pattern in b.file]

    if args.stale:
        bookmarks = [
            b for b in bookmarks if b.validation.status in ("stale", "missing_file")
        ]

    if not bookmarks:
        print("No bookmarks found.")
        return

    if args.as_json:
        import json

        print(json.dumps([b.to_dict() for b in bookmarks], indent=2))
        return

    if getattr(args, "as_long", False):
        _print_long(bookmarks)
        return

    # Table output
    _print_table(bookmarks)


def cmd_show(args):
    root, sigil_dir, bookmarks = _load()
    bm = _find_bookmark(bookmarks, args.id)

    # Update accessed time
    bm.metadata.accessed = now_iso()
    save_bookmarks(sigil_dir, bookmarks)

    if getattr(args, "as_json", False):
        import json

        print(json.dumps(bm.to_dict(), indent=2))
        return

    print(f"Bookmark: {bm.id}")
    print(f"File: {bm.file}:{bm.line}")
    print(f"Tags: {', '.join(bm.metadata.tags) if bm.metadata.tags else '(none)'}")
    print(f"Description: {bm.metadata.description or '(none)'}")
    print(f"Created: {bm.metadata.created}")
    print(f"Last accessed: {bm.metadata.accessed}")
    print(f"Status: {bm.validation.status} (checked {bm.validation.last_checked})")
    print()
    print("Context:")
    if bm.context.before:
        print(f"  {bm.line - 1:>4} │ {bm.context.before}")
    print(f"→ {bm.line:>4} │ {bm.context.target}")
    if bm.context.after:
        print(f"  {bm.line + 1:>4} │ {bm.context.after}")


def cmd_delete(args):
    root, sigil_dir, bookmarks = _load()

    if args.id:
        bm = _find_bookmark(bookmarks, args.id)
        bookmarks.remove(bm)
        save_bookmarks(sigil_dir, bookmarks)
        print(f"Deleted bookmark {bm.short_id} ({bm.file}:{bm.line})")

    elif args.tags:
        filter_tags = set(t.strip() for t in args.tags.split(","))
        to_delete = [b for b in bookmarks if filter_tags & set(b.metadata.tags)]
        if not to_delete:
            print("No bookmarks match those tags.")
            return
        print(f"Deleting {len(to_delete)} bookmark(s):")
        for bm in to_delete:
            print(f"  {bm.short_id} → {bm.file}:{bm.line}")
            bookmarks.remove(bm)
        save_bookmarks(sigil_dir, bookmarks)

    else:
        print("Error: Specify a bookmark ID or --tags to delete.", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args):
    root, sigil_dir, bookmarks = _load()

    if not bookmarks:
        print("No bookmarks to validate.")
        return

    # Unsafe dedupe mode: when both --fix and --unsafe are supplied, just trim duplicates.
    if getattr(args, "fix", False) and getattr(args, "unsafe", False):
        new_bookmarks, removed = _trim_duplicates(bookmarks)
        if not removed:
            print("No duplicate bookmarks found.")
            return
        save_bookmarks(sigil_dir, new_bookmarks)
        print(f"Removed {len(removed)} duplicate bookmark(s):")
        for bm in removed:
            print(f"  {bm.short_id} → {bm.file}:{bm.line}")
        return

    results = []
    for bm in bookmarks:
        result = validate_bookmark(bm, root)
        changed = apply_result(result, fix=args.fix)
        results.append(result)

    save_bookmarks(sigil_dir, bookmarks)

    if getattr(args, "as_json", False):
        import json

        serial = []
        for r in results:
            serial.append(
                {
                    "bookmark": r.bookmark.to_dict(),
                    "old_status": r.old_status,
                    "new_status": r.new_status,
                    "new_line": r.new_line,
                    "message": r.message,
                }
            )
        print(json.dumps(serial, indent=2))
        return

    # Summary
    by_status = {}
    for r in results:
        by_status.setdefault(r.new_status, []).append(r)

    print(f"Validated {len(results)} bookmark(s):\n")

    status_order = ["valid", "moved", "stale", "missing_file"]
    status_icons = {"valid": "✓", "moved": "→", "stale": "?", "missing_file": "✗"}

    for status in status_order:
        group = by_status.get(status, [])
        if not group:
            continue
        icon = status_icons[status]
        print(f"  {icon} {status}: {len(group)}")
        for r in group:
            if r.message and r.new_status != "valid":
                print(
                    f"    {r.bookmark.short_id} {r.bookmark.file}:{r.bookmark.line} — {r.message}"
                )
            elif r.new_status != "valid":
                print(f"    {r.bookmark.short_id} {r.bookmark.file}:{r.bookmark.line}")

    if args.fix:
        fixed = [r for r in results if r.new_line and r.new_line != r.bookmark.line]
        if fixed:
            print(f"\n  Fixed {len(fixed)} bookmark line number(s).")


def cmd_search(args):
    root, sigil_dir, bookmarks = _load()

    # Split query into field-scoped and free terms
    free_terms = []
    tag_terms = []
    file_terms = []
    for token in args.query:
        t = token.lower()
        if t.startswith("tag:"):
            tag_terms.append(t[4:])
        elif t.startswith("file:"):
            file_terms.append(t[5:])
        else:
            free_terms.append(t)

    # Score weights: desc=4, tags=3, file=2, target line=2, context=1
    scored = []
    for bm in bookmarks:
        desc = bm.metadata.description.lower()
        tags_str = " ".join(bm.metadata.tags).lower()
        file = bm.file.lower()
        target = bm.context.target.lower()
        before = bm.context.before.lower()
        after = bm.context.after.lower()

        # Field-scoped filters: all must match (hard filter, not scored)
        if tag_terms and not all(t in tags_str for t in tag_terms):
            continue
        if file_terms and not all(t in file for t in file_terms):
            continue

        # Free terms: all must appear somewhere (hard AND filter)
        all_text = f"{desc} {tags_str} {file} {target} {before} {after}"
        if not all(t in all_text for t in free_terms):
            continue

        # Score by field weight
        score = 0
        for t in free_terms:
            score += 4 * desc.count(t)
            score += 3 * tags_str.count(t)
            score += 2 * file.count(t)
            score += 2 * target.count(t)
            score += 1 * before.count(t)
            score += 1 * after.count(t)

        # Recency tiebreaker: seconds since epoch embedded in ID (bm_TIMESTAMP_hash)
        try:
            timestamp = int(bm.id.split("_")[1])
        except (IndexError, ValueError):
            timestamp = 0

        scored.append((score, timestamp, bm))

    if not scored:
        query_str = " ".join(args.query)
        print(f"No bookmarks matching '{query_str}'.")
        return

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    results = [bm for _, _, bm in scored]
    if args.limit:
        results = results[: args.limit]

    if getattr(args, "as_json", False):
        import json

        print(json.dumps([b.to_dict() for b in results], indent=2))
        return

    _print_table(results)


def cmd_move(args):
    root, sigil_dir, bookmarks = _load()
    bm = _find_bookmark(bookmarks, args.id)
    target = args.target

    # Determine new file and line
    if target.startswith(("+", "-")) and target[1:].isdigit():
        # Relative: +N or -N
        delta = int(target)
        new_file = bm.file
        new_line = bm.line + delta
    elif ":" in target:
        # File relocation: file:line
        parts = target.rsplit(":", 1)
        filepath = Path(parts[0])
        try:
            new_line = int(parts[1])
        except ValueError:
            print(f"Error: Invalid line in target '{target}'", file=sys.stderr)
            sys.exit(1)
        if not filepath.is_absolute():
            filepath = Path.cwd() / filepath
        new_file = get_relative_path(filepath, root)
    else:
        # Absolute line in same file
        try:
            new_line = int(target)
        except ValueError:
            print(f"Error: Cannot parse target '{target}'", file=sys.stderr)
            sys.exit(1)
        new_file = bm.file

    if new_line < 1:
        print(f"Error: Line number must be >= 1 (got {new_line})", file=sys.stderr)
        sys.exit(1)

    actual_path = (
        root / new_file if not Path(new_file).is_absolute() else Path(new_file)
    )
    new_context = extract_context(actual_path, new_line)

    old_location = f"{bm.file}:{bm.line}"
    bm.file = new_file
    bm.line = new_line
    bm.context = new_context
    bm.validation.status = "valid"
    bm.validation.last_checked = now_iso()

    save_bookmarks(sigil_dir, bookmarks)
    print(f"Moved {bm.short_id}: {old_location} → {new_file}:{new_line}")
    print(f"  Context: {new_context.target.strip()}")


def cmd_edit(args):
    root, sigil_dir, bookmarks = _load()
    bm = _find_bookmark(bookmarks, args.id)

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"

    content = (
        f"# Sigil bookmark: {bm.id}\n"
        f"# {bm.file}:{bm.line}\n"
        f"# Lines starting with # are ignored.\n"
        f"\n"
        f"tags: {', '.join(bm.metadata.tags)}\n"
        f"\n"
        f"desc:\n"
        f"{bm.metadata.description}\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sigil", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path, encoding="utf-8") as f:
            lines = f.readlines()
    finally:
        os.unlink(tmp_path)

    new_desc = bm.metadata.description
    new_tags = bm.metadata.tags

    in_desc = False
    desc_lines: list[str] = []
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.lstrip().startswith("#"):
            continue
        if stripped.startswith("tags:"):
            raw = stripped[len("tags:"):].strip()
            new_tags = [t.strip() for t in raw.split(",") if t.strip()]
        elif stripped == "desc:":
            in_desc = True
        elif in_desc:
            desc_lines.append(stripped)

    if in_desc:
        new_desc = "\n".join(desc_lines).strip()

    if new_desc == bm.metadata.description and new_tags == bm.metadata.tags:
        print("No changes.")
        return

    bm.metadata.description = new_desc
    bm.metadata.tags = new_tags
    bm.metadata.accessed = now_iso()
    save_bookmarks(sigil_dir, bookmarks)
    print(f"Updated bookmark {bm.short_id}")


# ---------- Helpers ----------


def _load() -> tuple:
    """Find root, ensure storage, load bookmarks. Returns (root, sigil_dir, bookmarks)."""
    root = find_root()
    if root is None:
        print(
            "Error: Not in a sigil project. Run 'sigil init' first, "
            "or navigate to a directory with .sigil/ or .git/",
            file=sys.stderr,
        )
        sys.exit(1)

    sigil_dir = ensure_storage(root)
    bookmarks = load_bookmarks(sigil_dir)
    return root, sigil_dir, bookmarks


def _find_bookmark(bookmarks: list[Bookmark], partial_id: str) -> Bookmark:
    """Find a bookmark by full or partial ID match."""
    matches = [b for b in bookmarks if partial_id in b.id]
    if len(matches) == 0:
        print(f"Error: No bookmark matching '{partial_id}'.", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Error: Ambiguous ID '{partial_id}'. Matches:", file=sys.stderr)
        for m in matches:
            print(f"  {m.id}", file=sys.stderr)
        sys.exit(1)
    return matches[0]


def _print_table(bookmarks: list[Bookmark]):
    """Print bookmarks as a formatted table."""
    # Calculate column widths
    rows = []
    for bm in bookmarks:
        desc = bm.metadata.description
        if len(desc) > 45:
            desc = desc[:42] + "..."
        rows.append(
            (
                bm.short_id,
                bm.file,
                str(bm.line),
                ",".join(bm.metadata.tags) if bm.metadata.tags else "",
                desc,
                bm.validation.status,
            )
        )

    headers = ("ID", "FILE", "LINE", "TAGS", "DESCRIPTION", "STATUS")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    # Cap widths for readability
    widths[1] = min(widths[1], 35)  # FILE
    widths[3] = min(widths[3], 20)  # TAGS
    widths[4] = min(widths[4], 45)  # DESCRIPTION

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("─" * w for w in widths)))
    for row in rows:
        truncated = tuple(
            val[: widths[i]] if len(val) > widths[i] else val
            for i, val in enumerate(row)
        )
        print(fmt.format(*truncated))


def _print_long(bookmarks: list[Bookmark]):
    """Print bookmarks in a compact definition-list style.

    Format per bookmark:
    |  <short-id>  <file>:<line>
    |    [tag1,tag2] Description first line
    |    → <anchor line>

    This avoids table alignment and truncation; descriptions are
    printed full (multiline preserved and indented).
    """
    indent = "\t"
    for bm in bookmarks:
        tags = ",".join(bm.metadata.tags) if bm.metadata.tags else ""
        tag_display = f"[{tags}]" if tags else ""
        desc = bm.metadata.description or ""
        desc_lines = desc.splitlines() or [""]

        # Header: id and location
        print(f"{bm.short_id}  {bm.file}:{bm.line}")

        # Description with optional tags on the first line
        if desc_lines:
            first = desc_lines[0]
            if tag_display:
                print(f"{indent}{tag_display} {first}")
            else:
                print(f"{indent}{first}")
            for line in desc_lines[1:]:
                print(f"{indent}  {line}")
        else:
            if tag_display:
                print(f"{indent}{tag_display}")

        # Anchor (show only the first line of the target context)
        target = (bm.context.target or "").splitlines()[0].strip()
        if target:
            print(f"{indent}→ {target}")

        # Blank line between entries for readability
        print()


# ---------- Duplicate trimming (unsafe) ----------

def _trim_duplicates(bookmarks: list[Bookmark]) -> tuple[list[Bookmark], list[Bookmark]]:
    """Trim duplicate bookmarks.

    Duplicates are considered bookmarks with the same (file, context.target).
    The function keeps the newest / bottom-most occurrence and removes earlier ones.

    Returns (new_bookmarks, removed_bookmarks).
    """
    seen: set[tuple[str, str]] = set()
    new_rev: list[Bookmark] = []
    removed_rev: list[Bookmark] = []

    # Iterate from bottom to top so the first occurrence we see is the newest
    for bm in reversed(bookmarks):
        key = (bm.file, (bm.context.target or "").strip())
        if key in seen:
            removed_rev.append(bm)
        else:
            seen.add(key)
            new_rev.append(bm)

    # Reconstruct original order (top -> bottom) for kept bookmarks
    new_bookmarks = list(reversed(new_rev))
    removed_bookmarks = list(reversed(removed_rev))
    return new_bookmarks, removed_bookmarks


if __name__ == "__main__":
    main()
