# 2026-03-03 — Add --long output for `sg list`

- Timestamp: 2026-03-03T17:24:54+01:00
- Participants: jani (developer), sigil-agent (me)

Summary
-------
Implemented a new `--long` flag for `sg list` that renders bookmarks as a compact definition-list rather than a table. This preserves full descriptions (including multiline), avoids truncation/column alignment issues, and prints an anchor line showing the bookmarked context.

Commands run
------------
- sg list (initial inspection)
- uv run sg list --long (user reported invocation; confirmed output)
- /home/jani/.local/share/uv/tools/sigil/bin/python3 -c 'import sys,os; sys.path.insert(0, os.path.join(os.getcwd(), "src")); from sigil.cli import main; main()' list --long (manual invocation used during development)
- .venv/bin/pytest -q (run tests)

Files added/modified
--------------------
- Modified: src/sigil/cli.py
  - Added new CLI flag: `--long` (dest: as_long)
  - Dispatches to new helper `_print_long(bookmarks)` when enabled
  - Implemented `_print_long` which prints each bookmark as:

    <short-id>  <file>:<line>
            [tag1,tag2] Description first line
            <two-space-indented>continuation lines...
            → <anchor line>

  - Kept table output as the default when `--long` not provided.

- Added: tests/test_cli_list_long.py
  - Unit tests covering basic and multiline-description cases for `_print_long`.

Test results
------------
- Ran tests with: .venv/bin/pytest -q
- Outcome: 2 passed, 0 failed

Notes / decisions
-----------------
- I chose to implement `_print_long` as a separate helper to keep the existing table logic intact.
- The long style intentionally prints full description lines (no truncation) and preserves multiline descriptions with extra indentation for continuation lines.
- Short IDs are used (Bookmark.short_id) to keep output compact.

Suggested next steps
--------------------
- Consider adding an integration test that shells out to `sg list --long` to validate end-to-end formatting under packaging (optional).
- Update README or PR notes to document the new `--long` flag and example output.
- Optionally add a `--wide` or configurable column widths for table output if users prefer expanded table behavior.

Chronicle created by sigil-agent.
