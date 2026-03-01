# Chronicle — 2026-03-01T23:43:28+01:00

Participants: assistant (code changes performed by the agent)

Summary
-------
Implemented machine-readable JSON output for all query-oriented subcommands of the `sigil` CLI and improved help text and examples across the CLI.

What I changed
--------------
- Added a `--json` / `--json` (dest: as_json) flag and JSON output handling to the following commands:
  - `list` (already had --json)
  - `show` (new)
  - `search` (new)
  - `validate` (new)

- Improved and expanded CLI help text:
  - Set the top-level parser to use RawDescriptionHelpFormatter and added an examples epilog.
  - Expanded help strings for subcommands (primer, init, add, list, show, delete, validate, search, move, edit) to be more descriptive and include guidance for common workflows.

Files modified
--------------
- src/sigil/cli.py

Representative commands run during the session
--------------------------------------------
- sg list --help
- sg --help
- sg list --json
- (edited src/sigil/cli.py and saved changes)

Representative code snippets / approaches
----------------------------------------
- JSON outputs are produced by calling `to_dict()` on Bookmark objects and emitting `json.dumps(..., indent=2)`.
- Validation results are serialized into dictionaries with fields: bookmark, old_status, new_status, new_line, message.

Notes and rationale
-------------------
- Adding machine-readable output makes it easier to script against `sigil` and integrate with editors/other tools.
- Keeping human-friendly table output as the default preserves the current UX for interactive use, while `--json` provides a stable API for automation.

Suggested next steps
--------------------
1. Add unit tests covering JSON output for `list`, `show`, `search`, and `validate`.
2. Consider adding a `--pretty-json` flag or environment variable to control whether JSON is compact or pretty-printed.
3. Add schema documentation for the JSON output so integrators know the field shapes and types (e.g. in PRIMER.md or a docs/ directory).

Commands to run for verification
--------------------------------
- sg list --json | jq .
- sg show <bookmark-id> --json | jq .
- sg search file:src --json | jq .
- sg validate --json | jq .

