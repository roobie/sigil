# Sigil Project Memory

## Running the CLI
Use `uv run sg` (resolves via pyproject.toml entry point `sg = "sigil.cli:main"`).

## Project Layout
```
src/sigil/
  cli.py       # argparse subcommands + dispatch + helpers
  models.py    # Bookmark, Context, Metadata, Validation dataclasses
  storage.py   # JSONL + .ctx file I/O, find_root, save_bookmarks
  context.py   # extract_context(filepath, line) → Context
  validate.py  # validate_bookmark, apply_result
  PRIMER.md    # LLM reference guide
.sigil/
  bookmarks.jsonl
  contexts/*.ctx
```

## CLI Commands
init, add, list (ls), show, delete (rm), validate, search, move, primer

## move command (added)
`sg move <id> <target>` — target forms:
- `+N` / `-N`: relative line shift
- `N`: absolute line in same file
- `file:line`: relocate to different file

Re-extracts context, resets validation.status to "valid".

## Storage Format
- JSONL: one flat dict per bookmark line (metadata only)
- .ctx files: 3-line snapshots with `>>> ` marking target line
- Atomic write: temp file + replace

## Patterns
- `_load()` → (root, sigil_dir, bookmarks)
- `_find_bookmark(bookmarks, partial_id)` → Bookmark (errors on ambiguity)
- Top-level error handler in main() catches FileNotFoundError, ValueError
