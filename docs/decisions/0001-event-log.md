---
id: ADR-0001
title: Local append-only event log for sigil invocations
status: accepted
date: 2026-04-19
code_anchors: [src/sigil/eventlog.py, src/sigil/cli.py]
---

# ADR-0001 — Local event log (`~/.local/state/sigil/events.jsonl`)

## Context

Sigil efficacy was previously inferable only by grepping Claude Code session
transcripts for `sigil <subcommand>` Bash invocations. That proved the tool
is used and that the SessionStart injection is the dominant surface — but
it can't answer repo-level questions ("which projects actually run
`validate --fix`?", "how big is the injected summary per repo?", "how often
does drift heal?"), and it's unavailable outside Claude Code entirely.

The design debate landed on: log each invocation locally, stdlib-only, with
a narrow privacy surface. This ADR captures *why* — because the "what" is
mechanical and the "why" is what a future reader will question.

## Decision

One append-only JSONL file at `$XDG_STATE_HOME/sigil/events.jsonl`
(defaulting to `~/.local/state/sigil/`). One line per CLI invocation;
one line per SessionStart hook injection (written by the hook script
itself). Schema carries `v: 1` for future migrations.

**Every event line carries, at minimum:**
`v, ts (UTC ISO-8601), kind ("cli"|"hook-inject"), cmd, exit, dur_ms,
argv_hash, source ("user"|"hook"), repo, repo_root`.

Per-command extras (`bookmarks_total`, `moved`, `fixed`, `bytes`, …) are
added via `eventlog.add_extra(...)` inside command functions and merged
into the line by the dispatcher wrapper.

Queries via a new `sigil stats [--since N] [--json]` subcommand.

## What `argv_hash` does and does NOT capture

**Does:** a 16-char SHA-256 prefix of the argv *skeleton* — subcommand,
flag names (long and short), and structural markers `<v>` (value after a
content-bearing flag) and `<p>` (positional arg).

**Does not:** any user-typed value. Values after `-d/--desc`, `-t/--tags`,
`-m/--message` are replaced by `<v>`. All positionals (file paths, line
specs, bookmark IDs) are replaced by `<p>`. `--flag=value` is stripped
before hashing.

Consequence: **the hash is correlatable** ("same call shape") across repos
and sessions, and **structurally incapable** of leaking a description,
a secret accidentally typed into `-d`, or a file path.

Descriptions already live in `.sigil/bookmarks.jsonl` — that is their
durable home. Duplicating them into a telemetry log gains nothing and
adds a leak vector.

## Rotation, atomicity, failure semantics

- **Rotation:** stat-before-open; if ≥ 10 MB, rename to `events.jsonl.1`
  (one backup, overwritten on next rotation). No multi-file sequence, no
  gzip — keeps the "tiny tool" character and debugging trivial (`cat`,
  `jq`).
- **Line atomicity:** events are ~200 B; well under `PIPE_BUF` (4 KB on
  Linux), so a single `write()` is atomic and concurrent `sigil`
  invocations won't interleave. A hard line cap of 4 KB is enforced; if
  a line would exceed it, extras are dropped and the line is marked
  `truncated: true` rather than risk a partial write.
- **Telemetry is never allowed to crash the CLI.** Every I/O path inside
  `eventlog.py` is wrapped in `try/except: pass`. Disk full, readonly
  mount, permission error, rotation failure — all degrade to "no log line
  written," never to a user-facing traceback.

## Alternatives considered

**OpenTelemetry / structlog / framework-based logging.** Rejected: adds
install weight and hidden dependency surface; overkill for a single-user
CLI whose signal is counted in hundreds-per-day, not millions-per-second.
Sigil has `dependencies = []` in `pyproject.toml` and that invariant is
worth defending.

**Remote telemetry (opt-in phone-home).** Rejected: the whole value of
the log is correlating local behavior. Shipping data off-host adds a
privacy surface with no corresponding gain and sidesteps any anxiety
about "this CLI is reporting my usage to a server."

**Log full argv verbatim.** Rejected: descriptions typed via `-d` may
contain sensitive content ("remove the TODO about the admin password");
file paths can reveal project structure. `argv_hash` gets the
correlation benefit at zero leak cost. If ever needed for debugging,
adding a `--trace` flag that logs verbatim only for the current
invocation is a cheap future move.

**Logging the bookmark store itself (bookmarks.jsonl) as events.**
Rejected: `bookmarks.jsonl` is data (the product); `events.jsonl` is
operational telemetry. Conflating them would break `sigil list` /
`sigil stats` as cleanly separated views.

**Separate files for CLI vs hook-inject events.** Rejected: the primary
analysis is correlational ("summary injected at T, then `sigil show` at
T+2min"). Split files fragment the join. One file with a `kind` field.

**`user` / `hostname` field on every line.** Rejected: single-user
machine assumption; adds drift if the log ever gets copied between
hosts. Out.

## Distinguishing user vs hook invocations

The SessionStart hook script sets `SIGIL_INVOCATION=hook` in its env.
The CLI reads that into the `source` field (default `"user"`). Without
this distinction, the hook's `sigil list` calls would drown the
user-initiated signal — exactly the noise-floor problem that prompted
this work in the first place.

## Consequences

**Enables:**
- `sigil stats` — first-class, no transcript grep required.
- Per-repo efficacy visibility (which projects actually use `validate
  --fix`, which have heavy hook-inject traffic).
- Post-hoc correlation of injection events with subsequent interactive
  calls.

**Constrains:**
- Adds one file to the user's state dir. Documented in README.
- `sigil stats` depends on the schema; future schema changes MUST bump
  `v` and `stats` must branch (not silently miscount old rows).
- The dispatcher wrapper adds ~5 ms per invocation (measured in smoke
  test as 0 ms — below resolution). Acceptable.

**Deferred:**
- `sigil log rotate` subcommand (manual rotation). Auto-rotate at
  startup is sufficient for now.
- `--trace` for verbatim-argv logging during debugging.

## References

- Chronicle: `chronicles/2026-04-19-efficacy-followup-and-adr-linkage.md`
  — the design conversation that motivated this.
- Related ADR-pattern precedent: `pa/docs/decisions/002-mnemex-pretool-gate.md`
  (mechanical enforcement over soft rules) — different concern, same
  philosophy (prefer small mechanical artifact over framework).
