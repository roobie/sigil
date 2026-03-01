# Sigil: LLM Reference

## What it is

Sigil (`sg`) is a CLI tool for bookmarking code locations with human-written descriptions and tags. Think of it as a curated index of "places that matter" in a codebase, annotated with intent and context that grep and IDE search can't provide.

When a `.sigil/` directory is present in a repository, it contains a navigable map of important code locations maintained by the developer(s).

## Why it matters to you

Bookmarks tell you **what the developer cares about and why**. A bookmark isn't just a file and line number — it carries a description explaining significance, tags for categorization, and surrounding code context for orientation. This is higher-signal than reading raw source because someone has already identified these locations as important.

Never edit `.sigil` files directly! Use the `sg` CLI!

## Storage format

```
.sigil/
  bookmarks.jsonl          # one JSON object per line, metadata only
  contexts/
    bm_1709123456_a3f5.ctx # raw code context, no escaping
```

### bookmarks.jsonl

Never edit `.sigil` files directly! Use the `sg` CLI!

Each line is a self-contained JSON object:

```json
{"id":"bm_1709123456_a3f5","file":"src/parser.py","line":38,"tags":["bug","parser"],"desc":"Doesn't handle escaped quotes in string literals","status":"valid","created":"2026-02-15T10:30:00+00:00","accessed":"2026-02-20T14:22:00+00:00","checked":"2026-02-26T09:15:00+00:00"}
```

Fields: `id` (unique), `file` (relative path from repo root), `line` (1-based), `tags` (list), `desc` (human description), `status` (valid|moved|stale|missing_file), `created`, `accessed`, `checked`.

### Context files (.ctx)

Never edit `.sigil` files directly! Use the `sg` CLI!

Raw source code, no escaping. The target line is marked with `>>> `:

```
    fn parse_expression(input: &str) -> Result<Expr> {
>>>     let tokens = tokenize(input)?;
        build_ast(tokens)
```

Lines above and below the `>>>` marker are surrounding context for orientation and validation.

## CLI commands

```bash
sg init                                    # initialize in current repo
sg add <file>:<line> -t tag1,tag2 -d "..." # create bookmark
sg list [-t tags] [-f file] [--stale]      # list/filter bookmarks
sg list --json                             # JSON output for programmatic use
sg show <id>                               # detailed view with context
sg delete <id>                             # remove bookmark
sg delete -t <tags>                        # bulk remove by tag
sg validate                                # check all bookmarks against source
sg validate --fix                          # auto-update shifted line numbers
sg search <terms...>                       # ranked search; all terms must match
sg search tag:<t> file:<f> <term>         # field-scoped search (tag:, file: prefixes)
sg search <terms...> -n 10                # show top N results only
sg edit <id>                               # open bookmark metadata in $EDITOR (desc + tags)
sg move <id> <target>                      # moves a bookmark using either relative,file local-absolute or absolute references

```

Partial IDs work for show/delete/edit (e.g. `sg show a3f5`).

## Search ranking

`sg search` accepts multiple terms — all must match (AND). Results are ranked by relevance:

- **4×** match in description
- **3×** match in tags
- **2×** match in file path or target line
- **1×** match in surrounding context lines

Field-scoped prefixes (`tag:foo`, `file:bar`) act as hard filters before scoring. Ties broken by recency.

## Validation statuses

- **valid**: Target line matches stored context at expected location
- **moved**: Target found at a different line (validate --fix updates the line number)
- **stale**: Target line not found in file — code was likely changed or removed
- **missing_file**: The bookmarked file no longer exists

## How to use bookmarks in your work

### When reading a codebase

Start with `sg list --json`. This gives you the developer's mental map — the places they've marked as important, buggy, fragile, or worth understanding. Use descriptions and tags to orient yourself before diving into source.

### When making changes

After modifying code, run `sg validate` to see which bookmarks were affected. If you shifted code, `sg validate --fix` will auto-update line numbers. If you fundamentally changed bookmarked code, update or remove the stale bookmarks.

### When creating bookmarks

Write descriptions as if explaining to a colleague why this location matters. Include the "why", not just the "what" — the code itself shows what's there, but only the description explains why someone should care. Good tags make bookmarks filterable: use consistent categories like `bug`, `todo`, `fragile`, `api`, `perf`, `security`.

### When maintaining bookmarks

After refactoring, run `sg validate --fix` and review any stale bookmarks. Either update them to point at the new relevant code, or delete them if the concern no longer applies. Bookmark maintenance is a good post-refactor checklist item.

Remember, stale references are worse than no references.
