# Chronicle: Adjust long-format indentation to a single TAB and update tests

- Timestamp: 2026-03-05T17:50:00+01:00
- Participants: assistant (code changes)

## Summary

Reworked the long-format printing indentation to use a single TAB character ("\t") instead of spaces. Updated tests to expect the new indentation.

Changes made:
- Modified src/sigil/cli.py: _print_long now uses indent = "\t" and keeps continuation lines indented with a tab + two spaces.
- Updated tests/tests_cli_list_long.py to match the new output (use '\t' in expected strings).

## Commands run (representative)

- Edited source and test files.

## Files modified

- Modified: src/sigil/cli.py
- Modified: tests/test_cli_list_long.py

## Suggested next steps

- Run the test suite (uv run pytest) to verify all tests pass.

---
