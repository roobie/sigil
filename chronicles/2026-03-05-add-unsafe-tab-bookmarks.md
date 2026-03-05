# Chronicle: Add bookmarks for --unsafe handling and TAB indent

- Timestamp: 2026-03-05T17:56:00+01:00
- Participants: assistant (added bookmarks via sg), user

## Summary

Added two bookmarks to the repository pointing to:
1. The unsafe dedupe handling in the validate command (when `--fix` and `--unsafe` are used).
2. The long-format indentation site where the indent is a single TAB character (`\t`).

These bookmarks will make it easier to find and reference the new behavior and formatting decision.

## Commands run

- Started session with a bookmark listing:
  - sg list

- Added bookmark to unsafe dedupe handling (src/sigil/cli.py:385):
  - sg add src/sigil/cli.py:385 -t unsafe,validate -d "dedupe: unsafe trimming when --fix --unsafe"
  - Output: Added bookmark 868_e971 → src/sigil/cli.py:385

- Added bookmark to TAB indent site (src/sigil/cli.py:725):
  - sg add src/sigil/cli.py:725 -t ui,format -d "long-format indent uses a TAB char"
  - Output: Added bookmark 872_007d → src/sigil/cli.py:725

## Files mutated

- .sigil/bookmarks.jsonl (updated with new bookmark entries)
- .sigil/contexts/bm_1772728868_e971.ctx (created)
- .sigil/contexts/bm_1772728872_007d.ctx (created)

## Representative command outputs

- sg list (before): (trimmed output)
  - Listed existing bookmarks.

- sg add src/sigil/cli.py:385 ...
  - Added bookmark 868_e971 → src/sigil/cli.py:385
    Tags: unsafe, validate
    Desc: dedupe: unsafe trimming when --fix --unsafe
    Context: if getattr(args, "fix", False) and getattr(args, "unsafe", False):

- sg add src/sigil/cli.py:725 ...
  - Added bookmark 872_007d → src/sigil/cli.py:725
    Tags: ui, format
    Desc: long-format indent uses a TAB char
    Context: indent = "\t"

## Suggested next steps

- Commit the .sigil datastore if you want these bookmarks tracked in Git (they are currently untracked). Decide whether .sigil should be part of the repository and, if so, add and commit the files.
- If you prefer non-destructive workflows, add a dry-run option or a confirmation prompt for the `--unsafe` behavior.

---

This chronicle records the stateful changes made by the agent during this session.
