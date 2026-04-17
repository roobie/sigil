#!/bin/bash
# Inject sigil bookmark context at session start.
# Degrades gracefully: no .sigil/ → no output → no context injected.

SIGIL_DIR=".sigil"
BOOKMARKS="$SIGIL_DIR/bookmarks.jsonl"

# Silent exit if no sigil data
[ -f "$BOOKMARKS" ] || exit 0

COUNT=$(wc -l < "$BOOKMARKS" 2>/dev/null || echo 0)
[ "$COUNT" -eq 0 ] && exit 0

echo "SIGIL BOOKMARKS ($COUNT bookmarks in this repo):"
echo "Use 'sigil list', 'sigil show <id>', 'sigil search <query>' to explore."
echo "Tags: $(jq -r '.tags[]?' "$BOOKMARKS" 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')"
echo "---"
# Compact summary: one line per bookmark (tag, file, description)
jq -r '[.tags[0] // "untagged", .file, .line, .desc] | "\(.[0]) | \(.[1]):\(.[2]) | \(.[3])"' "$BOOKMARKS" 2>/dev/null
