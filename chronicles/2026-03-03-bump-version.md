# 2026-03-03 — Bump version to 0.4.3 and commit

- Timestamp: 2026-03-03T17:39:00+01:00
- Participants: jani (developer), sigil-agent (me)

Summary
-------
Bumped the package version in pyproject.toml from 0.4.2 to 0.4.3 and committed the change along with the previously added --long output implementation, tests, and chronicle entry.

Commands run
------------
- Edited pyproject.toml to set version = "0.4.3"
- git add pyproject.toml src/sigil/cli.py tests/test_cli_list_long.py chronicles/2026-03-03-add-long-flag.md
- git commit -m "cli(list): add --long output; tests; bump version to 0.4.3"

Files changed/added
------------------
- Modified: pyproject.toml (version bump)
- Modified: src/sigil/cli.py (added --long flag and _print_long)
- Added: tests/test_cli_list_long.py
- Added: chronicles/2026-03-03-add-long-flag.md

Commit
------
Commit message: "cli(list): add --long output; tests; bump version to 0.4.3"
Files in commit:
- chronicles/2026-03-03-add-long-flag.md
- pyproject.toml
- src/sigil/cli.py
- tests/test_cli_list_long.py

Notes
-----
This chronicle documents the version bump and commit. The code and tests were added in the same commit for conciseness; if you prefer a separate version-only commit I can split it.
