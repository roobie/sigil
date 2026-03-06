timestamp: 2026-03-06T01:35:06Z
participants: [assistant]

summary: |
  Added several bookmarks documenting test assumptions and CLI behaviors that
  previously caused confusion or flakiness. These bookmarks highlight why tests
  set EDITOR in CI, where validation behaviours are asserted in tests, and call
  out CLI helpers (move/edit) so maintainers can find the implementation quickly.

commands_run:
  - sg add tests/test_more.py:344 -t tests,editor,flaky -d "test_cmd_add_show_delete_move_edit_list: ensures cmd_edit does not block; test sets EDITOR/VISUAL to 'true' to avoid launching an interactive editor (historical pytest hang)."
  - sg add tests/test_more.py:163 -t tests,validation,spec -d "test_validate_various_cases: documents expected validation behaviour (missing_file, stale, exact, nearby, moved, multi-match disambiguation)."
  - sg add tests/test_more.py:119 -t tests,storage -d "test_context_file_io_and_jsonl_roundtrip: verifies JSONL + .ctx roundtrip and orphan cleanup."
  - sg add tests/test_cli_more.py:15 -t tests,primer,init -d "test_cmd_primer_and_init: ensures PRIMER.md output and that sg init creates .sigil/."
  - sg add tests/test_cli_more.py:82 -t tests,validate,json -d "test_cmd_validate_json_output: verifies cmd_validate --json machine-readable output and 'new_status' field."
  - sg add src/sigil/cli.py:526 -t cli,move -d "cmd_move: handles relative (+N/-N), absolute, and file:line targets; updates context and validation."
  - sg add src/sigil/cli.py:579 -t cli,edit -d "cmd_edit: opens $EDITOR on a temp file, parses tags/desc on save; set EDITOR in CI/tests to avoid blocking."

files_added:
  - .sigil/contexts/bm_1772760905_afbd.ctx
  - .sigil/contexts/bm_1772760905_c33d.ctx
  - .sigil/contexts/bm_1772760906_ed43.ctx
  - .sigil/contexts/bm_1772760906_240d.ctx
  - .sigil/contexts/bm_1772760906_94e1.ctx
  - .sigil/contexts/bm_1772760906_2484.ctx
  - .sigil/contexts/bm_1772760906_a9df.ctx

files_modified:
  - .sigil/bookmarks.jsonl

notes: |
  - These bookmarks are lightweight documentation points intended to help
    future contributors quickly find rationale for test setup and CLI behaviour.

next_steps:
  - Push the commit (if not already pushed) and run 'sg validate' to ensure
    the new bookmarks resolve correctly in other environments.
