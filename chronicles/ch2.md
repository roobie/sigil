# Chronicle: From Spec to Working MVP

## Starting Point

Arrived with a thorough design spec — the product of an earlier conversation that had gone through the full vision → reality check → scope cut cycle. The spec called for a Rust CLI tool called `codemark` with JSON storage, context-based validation, and a VS Code extension. Timeline estimated at 6-8 weeks.

## Motivations Clarified

Three reasons to build this, in order of honesty:

1. **Personal use** — genuine belief in the tool's value for navigating large codebases
2. **LLM integration** — bookmarks as a curated index for LLMs to consume, and LLMs as capable bookmark maintainers (update after refactors, flag semantic staleness)
3. **Dev clout** — the LLM angle is a better Show HN hook than "bookmarks for code"

The LLM motivation reframed some design priorities: rich human-written descriptions become more important (they're knowledge artifacts, not just labels), and the storage format needs to be LLM-friendly.

## Language Decision

Chose Python prototype over Rust-from-day-one. Reasoning: get to real usage fast, nail the UX, keep the data format stable so the Rust rewrite inherits a proven design. Intermediate Rust experience means the rewrite won't be painful once the tool's shape is clear.

## First Implementation

Built the core in pure stdlib Python — zero dependencies:

- Data model (Bookmark, Context, Metadata, Validation)
- Storage layer (read/write to JSON)
- Context extraction from source files
- Validation with three tiers: exact match → nearby search (±10 lines) → file-wide search → stale
- CLI commands: init, add, list, show, delete, validate (with --fix), search
- Tag filtering, file filtering, partial ID matching, JSON output

Tested on a realistic project with parser and cache modules. Validated that bookmarks track correctly when code shifts, and go stale when code is deleted.

## Storage Format Revision

The original spec called for a single `bookmarks.json` file. Two problems surfaced:

1. **JSON escaping noise** — code stored in JSON values creates multiple escaping layers (quotes inside strings inside JSON strings). Ugly to read, worse in diffs.
2. **Git diff unfriendliness** — a single JSON array means structural changes (adding/removing bookmarks) can touch many lines.

Considered a custom triple-pipe delimited format (`|||field=value`), but rejected it: multiline values are awkward, nested structure is hard, and LLMs are natively fluent in JSON but would need to learn a custom format.

Landed on a **split approach**:

- **bookmarks.jsonl** — one JSON object per line, metadata only (no code content). Adding a bookmark appends one line. Clean diffs.
- **contexts/\<id\>.ctx** — raw source code with `>>>` marking the target line. Zero escaping. Human-readable. Can be selectively included when sending bookmarks to an LLM.

This gives the best of both worlds: structured metadata in a format everything can parse, and code content stored as actual code.

## Ergonomics Fix

The `python -m codemark` invocation requires CWD to be the package's parent directory. Added a standalone launcher script (`cm`) that resolves its own location to find the package. Works from any directory. Three install options: symlink on PATH, shell alias, or pip install.

## LLM Primer

Wrote a compact reference document designed to be dropped into system prompts or included alongside a codebase. Covers: what codemark is, the storage format, all CLI commands, validation statuses, and — critically — instructions for how an LLM should use bookmarks when reading, modifying, or maintaining a codebase.

## Current State

A working MVP with six files and zero dependencies:

```
codemark/
  __init__.py    # version
  __main__.py    # python -m codemark
  cli.py         # argument parsing + command dispatch
  models.py      # Bookmark, Context, Metadata, Validation dataclasses
  storage.py     # JSONL + .ctx file I/O
  context.py     # source file line extraction
  validate.py    # three-tier context matching
cm               # standalone launcher script
pyproject.toml   # for pip install
```

Commands working: `init`, `add`, `list` (with --tags, --file, --stale, --json), `show`, `delete` (by ID or tag), `validate` (with --fix), `search`.

## What's Next

Not yet built, roughly in priority order:

- **goto** command (open in $EDITOR)
- **Interactive fuzzy finder** (the "wow" feature)
- **LLM workflow testing** — pipe `codemark list --json` plus relevant `.ctx` files to a model with a diff, see how well it maintains bookmarks
- **Git hook integration** — auto-validate on commit or checkout
- **Rust rewrite** — once the Python prototype has been used on a real codebase long enough to stabilize the design
