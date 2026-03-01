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
        description="Bookmark code locations with context-aware validation. Invoke `sg primer` for a crash course in how to use.",
    )
    parser.add_argument("--version", action="version", version=f"sigil {__version__}")

    sub = parser.add_subparsers(dest="command")

    # --- primer ---
    sub.add_parser(
        "primer",
        help="Prints the PRIMER.md (do this as part of discovery on how to use this tool)",
    )

    # --- init ---
    sub.add_parser("init", help="Initialize sigil in current directory")

    # --- add ---
    p_add = sub.add_parser("add", help="Add a bookmark")
    p_add.add_argument("location", help="file:line (e.g. src/main.py:42)")
    p_add.add_argument("-t", "--tags", help="Comma-separated tags")
    p_add.add_argument("-d", "--desc", default="", help="Description")

    # --- list ---
    p_list = sub.add_parser("list", aliases=["ls"], help="List bookmarks")
    p_list.add_argument("-t", "--tags", help="Filter by tags (comma-separated)")
    p_list.add_argument("-f", "--file", help="Filter by file pattern")
    p_list.add_argument(
        "--stale", action="store_true", help="Show only stale bookmarks"
    )
    p_list.add_argument(
        "--json", action="store_true", dest="as_json", help="Output as JSON"
    )

    # --- show ---
    p_show = sub.add_parser("show", help="Show bookmark details")
    p_show.add_argument("id", help="Bookmark ID (or partial match)")

    # --- delete ---
    p_del = sub.add_parser("delete", aliases=["rm"], help="Delete bookmark(s)")
    p_del.add_argument("id", nargs="?", help="Bookmark ID (or partial match)")
    p_del.add_argument("-t", "--tags", help="Delete all with these tags")

    # --- validate ---
    p_val = sub.add_parser("validate", help="Validate all bookmarks")
    p_val.add_argument("--fix", action="store_true", help="Auto-fix line numbers")

    # --- search ---
    p_search = sub.add_parser("search", help="Search bookmarks")
    p_search.add_argument("query", help="Search term")

    # --- move ---
    p_move = sub.add_parser("move", help="Reposition a bookmark")
    p_move.add_argument("id", help="Bookmark ID (or partial match)")
    p_move.add_argument(
        "target",
        help="New position: +N (relative), -N (relative), N (absolute), or file:line",
    )

    # --- edit ---
    p_edit = sub.add_parser("edit", help="Edit bookmark metadata in $EDITOR")
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

    # Table output
    _print_table(bookmarks)


def cmd_show(args):
    root, sigil_dir, bookmarks = _load()
    bm = _find_bookmark(bookmarks, args.id)

    # Update accessed time
    bm.metadata.accessed = now_iso()
    save_bookmarks(sigil_dir, bookmarks)

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

    results = []
    for bm in bookmarks:
        result = validate_bookmark(bm, root)
        changed = apply_result(result, fix=args.fix)
        results.append(result)

    save_bookmarks(sigil_dir, bookmarks)

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
    query = args.query.lower()

    matches = []
    for bm in bookmarks:
        searchable = " ".join(
            [
                bm.metadata.description,
                " ".join(bm.metadata.tags),
                bm.file,
                bm.context.target,
            ]
        ).lower()
        if query in searchable:
            matches.append(bm)

    if not matches:
        print(f"No bookmarks matching '{args.query}'.")
        return

    _print_table(matches)


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


if __name__ == "__main__":
    main()
