#!/bin/bash
# Inject sigil bookmark context at session start.
# Degrades gracefully: no .sigil/ → no output → no context injected.

SIGIL_DIR=".sigil"
BOOKMARKS="$SIGIL_DIR/bookmarks.jsonl"

# Silent exit if no sigil data
[ -f "$BOOKMARKS" ] || exit 0

COUNT=$(wc -l < "$BOOKMARKS" 2>/dev/null || echo 0)
[ "$COUNT" -eq 0 ] && exit 0

# Buffer the payload so we can both emit it to stdout (→ Claude's context)
# AND measure its size for telemetry (ADR-0001).
OUTPUT=$(
  echo "SIGIL BOOKMARKS ($COUNT bookmarks in this repo):"
  echo "Use 'sigil list', 'sigil show <id>', 'sigil search <query>' to explore."
  echo "Tags: $(jq -r '.tags[]?' "$BOOKMARKS" 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')"
  echo "---"
  # Compact summary: one line per bookmark (tag, file, description)
  jq -r '[.tags[0] // "untagged", .file, .line, .desc] | "\(.[0]) | \(.[1]):\(.[2]) | \(.[3])"' "$BOOKMARKS" 2>/dev/null
)
printf '%s\n' "$OUTPUT"

# Telemetry append (ADR-0001). Must never block the hook — wrapped so any
# failure (missing jq, disk full, readonly state dir) silently no-ops.
{
  BYTES=$(printf '%s' "$OUTPUT" | wc -c | tr -d ' ')
  EVENTS_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/sigil"
  mkdir -p "$EVENTS_DIR" 2>/dev/null
  jq -cn \
    --arg ts "$(date -u +%FT%TZ)" \
    --arg repo "$(basename "$PWD")" \
    --arg repo_root "$PWD" \
    --argjson bookmarks "$COUNT" \
    --argjson bytes "$BYTES" \
    '{v:1, ts:$ts, kind:"hook-inject", cmd:"hook-inject", exit:0, dur_ms:0, argv_hash:"-", source:"hook", repo:$repo, repo_root:$repo_root, bookmarks:$bookmarks, bytes:$bytes}' \
    >> "$EVENTS_DIR/events.jsonl" 2>/dev/null
} || true
