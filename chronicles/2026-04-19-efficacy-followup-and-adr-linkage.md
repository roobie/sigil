---
type: standard
date: 2026-04-19
session_goal: "Assess sigil efficacy across real Claude Code transcripts and design automation + ADR linkage enforcement"
files_touched: []
modules_changed: []
dependencies:
  added: []
  removed: []
  updated: []
duration: "~30m (design conversation, no code)"
status: in-progress
---

# Session Chronicle: Sigil Efficacy Follow-up + ADR Linkage Enforcement

## Quick Summary
Measured sigil usage across ~4,900 Claude Code session transcripts to decide whether the tool is earning its keep. Found that the session-start injection is doing almost all the real work; interactive commands (`search`/`show`) are rarely used and that's probably fine. Then designed two automation follow-ups: (1) a pre-commit drift-healer using the already-shipped `validate --fix`, and (2) a new `adr-check` command that forces every new/changed ADR to either own a sigil bookmark or explicitly opt out via frontmatter. Pre-commit hook is already landed by BR; `adr-check` + `install-hooks` are the remaining work.

---

## What We Built/Changed
Design-only session — no code committed here. Prior to this conversation BR added a pre-commit hook wiring `sigil validate --fix`.

## Key Decisions & Rationale

**Decision:** Efficacy is measured via Bash-invocation counts and injection counts across `~/.claude/projects/**/*.jsonl`, not via tool-internal telemetry (yet).
**Rationale:** Zero build cost; transcripts already contain enough signal to falsify the "nobody uses sigil" hypothesis.
**Result:** Across ~4,900 sessions, 54 `add`, 14 `list`, 5 `search`, 1 `show`, 1 `move`, 1 `validate` — plus ~209 sessions that received an injected bookmark summary. The injection channel is the real product surface; interactive commands are a minor read path. That reframes the "low consultation rate" as expected, not as a failure.

**Decision:** Automate drift healing via **pre-commit**, not via a systemd timer.
**Rationale:** Git-hook fires exactly when code moves, so bookmarks heal synchronously; no auto-commits inside arbitrary working trees; no "stale up to a week" window. BR already added this.
**Alternatives considered:** Weekly systemd --user timer walking `~/devel/*/.sigil/`. Rejected as primary because of dirty-tree risks and auto-amend sharp edges; still fine as a later safety net if merges from branches miss the pre-commit.

**Decision:** Force ADR↔bookmark linkage via a **pre-commit check**, not via a Claude Code hook or a soft rule in CLAUDE.md.
**Rationale:** Same pattern as ADR 002 (mnemex PreToolUse gate) in PA — mechanical enforcement beats exhortation, and pre-commit covers all commit paths (Claude, BR's hand edits, external contributors). A Claude-only hook would leave human edits ungated.
**Alternatives considered:**
- Claude Code PostToolUse hook on Write/Edit matching `docs/decisions/*.md`. Rejected: doesn't cover non-Claude edits.
- CLAUDE.md soft rule ("always add a bookmark when authoring an ADR"). Rejected: BR's track record with soft rules is that they slip; mnemex-gate ADR 002 exists precisely because of this.

**Decision:** Opt-out mechanism is **frontmatter declaration**, not env-var bypass alone.
**Rationale:** Some ADRs are policy/infra (e.g., "use nanovault for secrets") with no code line to point at. A `code_anchors: none` field in the ADR frontmatter forces a one-time deliberate choice that stays greppable forever. `SIGIL_SKIP=1` remains available as the emergency valve, matching the "always have a bypass" convention from the mnemex gate.

## Next Steps

- [ ] Implement `sigil adr-check` subcommand.
  - Scan staged diff (`git diff --cached --name-status`) with filter `AMR` (add/modify/rename) against `docs/decisions/**/*.md` (configurable glob). Rename must re-validate linkage. Deletes (`D`) are deferred to `adr-orphans` — name the gap, don't block on it.
  - For each touched ADR, extract the ADR's OWN ID from the **filename stem only** (not the body). Body mentions of `ADR-NNNN` are references to other ADRs and MUST NOT satisfy the check.
  - Read staged content via `git show :<path>`, not the working tree — a pre-commit hook must validate what's being committed, not what's on disk.
  - For each ID: pass if any bookmark description matches `^ADR-NNNN\b` (stricter than a loose substring — prevents "supersedes ADR-0089" in an unrelated bookmark from falsely satisfying 0089), OR the ADR frontmatter declares `code_anchors: none`.
  - **Check `SIGIL_SKIP=1` first**, before any git/subprocess work, and echo to stderr that skip was honored.
  - Exit codes: `0` pass, `1` missing linkage (user-correctable), `2` internal error (unparseable frontmatter, `sigil list --json` failure, git command failed). Do not conflate.
  - All human messaging to stderr; stdout reserved for machine-readable output (TSV of `adr_id<TAB>path` on failure) so `adr-orphans` can consume it later without reparsing.
  - Frontmatter parsing: **no PyYAML dep**. Sigil is stdlib-only (`dependencies = []`). Parse the `---`-fenced block with a narrow stdlib reader that accepts `code_anchors: none` or `code_anchors: [id, id, ...]`. Reject unparseable frontmatter with exit code 2.
  - Pin a test on the `sigil list --json` field name (`description`) so upstream schema drift is caught here, not in production.
- [ ] Scaffold `sigil install-hooks` (does not exist yet — confirmed via `grep`).
  - Write `.git/hooks/pre-commit` with a managed block between markers (e.g. `# >>> sigil managed` / `# <<< sigil managed`) so re-running is idempotent and doesn't duplicate lines.
  - Install both the existing `validate --fix` step and the new `adr-check` step.
- [ ] Add `code_anchors:` to the ADR template. **Required field, no implicit default.** Valid values: `none` (explicit opt-out) OR a non-empty list (e.g. `[bookmark-id, ...]` — initially informational, enforced later). Missing/empty → hard fail. This removes the "opt-out is all-or-nothing" ambiguity up front rather than deferring.
- [ ] Update README.md with the new workflow: "Authoring an ADR means also owning its bookmark."
- [ ] (Optional) Add `sigil adr-orphans` to list ADRs with no bookmark and no opt-out — a one-shot audit across any repo that adopts the pattern. Also handles the deferred `D` (delete) case: flag live bookmarks pointing at deleted ADRs.

## Unresolved Issues

- **ADR rename/split handling.** If ADR-0089 becomes 0089a/0089b, existing bookmarks still reference `ADR-0089`. Proposal: `adr-check` accepts the old ID if the renamed ADR's frontmatter declares `supersedes: [0089]` or `superseded_by: [...]`. Needs the ADR template to formalize these fields first.
- **Multi-ADR bookmarks.** Some cognex bookmarks already say `ADR-0070/0071 — …` or `ADR-0041/0064 — …`. With the stricter `^ADR-NNNN\b` anchoring, only the leading ID satisfies the check. Either (a) accept this as a forcing function to split multi-ADR bookmarks, or (b) relax the anchor to `(^|\s)ADR-NNNN\b`. Defer decision to first real case.
- **Cross-repo ADRs.** BR's ADRs mostly live per-repo, but some live in PA (`pa/docs/decisions/`). The check is repo-local; that's fine for now, but worth noting if sigil ever adopts cross-repo awareness.
- **Zombie bookmarks after ADR delete.** `D`-filtered diffs are skipped by `adr-check` (it can't validate what no longer exists on disk). Picked up by `adr-orphans` as a reverse check. Named here so the gap isn't silent.

---

<!-- STANDARD CHRONICLE: Stop here. Deep-dive sections below are optional. -->

---

## Technical Deep Dive

### Efficacy measurement method (reproducible)

All Claude Code transcripts live at `~/.claude/projects/<slug>/<session-uuid>/*.jsonl` with subagent traces under `subagents/`. Approx file count: 4,905.

**Count actual Bash invocations of sigil subcommands:**
```bash
grep -r -h -oE '"command":"[^"]*sigil [a-z]+' ~/.claude/projects/ 2>/dev/null \
  | grep -oE 'sigil [a-z]+' | sort | uniq -c | sort -rn
```

**Count sessions that received the injected summary:**
```bash
grep -r -l -i "sigil bookmarks" ~/.claude/projects/ 2>/dev/null | wc -l
```

Numbers from 2026-04-19:
| subcommand | invocations |
|---|---|
| `sigil add` | 54 |
| `sigil list` | 14 |
| `sigil search` | 5 |
| `sigil show` | 1 |
| `sigil move` | 1 |
| `sigil validate` | 1 |

Sessions with injected summary: ~209.

### Why the low `show` count isn't a failure

Every bookmark description in cognex follows the `ADR-NNNN — one-liner` convention. That means the injected summary already delivers the real payload (the ADR pointer + the "why" one-liner). `sigil show <id>` would only add the exact `file:line`, which Claude typically doesn't need to open — it uses the file path from the summary and Reads directly. So consultation == "reads the summary" not "runs a subcommand," and the summary is working as designed.

### Why pre-commit > systemd timer for drift

Dirty trees + auto-amend = lost work. A pre-commit hook runs at a known-clean moment (right before a commit), so `validate --fix` can write changes into the index without stomping anything. A weekly timer walking `~/devel/*/.sigil/` would either skip dirty repos (silent gaps) or auto-commit inside them (unsafe). Pre-commit keeps bookmarks perfect during active work; a cron is only useful as a last-line sweep.

### adr-check sketch (Python-flavored pseudocode)

```python
# sigil adr-check  — runs from pre-commit
import re, subprocess, sys, yaml
from pathlib import Path

ADR_GLOB = "docs/decisions/**/*.md"
ADR_ID_RE = re.compile(r"ADR[- ]?(\d{3,4})", re.IGNORECASE)

def staged_adr_files():
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"]
    ).decode().splitlines()
    return [f for f in out if Path(f).match(ADR_GLOB)]

def adr_opts_out(adr_path: Path) -> bool:
    txt = adr_path.read_text()
    if not txt.startswith("---"):
        return False
    _, fm, _ = txt.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    return meta.get("code_anchors") == "none"

def ids_in_adr(adr_path: Path) -> set[int]:
    ids = set()
    stem = adr_path.stem
    m = ADR_ID_RE.search(stem)
    if m: ids.add(int(m.group(1)))
    for m in ADR_ID_RE.finditer(adr_path.read_text()):
        ids.add(int(m.group(1)))
    return ids

def bookmark_ids() -> set[int]:
    # call sigil's own list --json to avoid coupling to bookmark storage format
    import json
    data = json.loads(subprocess.check_output(["sigil", "list", "--json"]))
    ids = set()
    for bm in data:
        for m in ADR_ID_RE.finditer(bm.get("description", "")):
            ids.add(int(m.group(1)))
    return ids

def main():
    if "1" == __import__("os").environ.get("SIGIL_SKIP", ""):
        return 0
    missing = []
    covered = bookmark_ids()
    for f in staged_adr_files():
        p = Path(f)
        if adr_opts_out(p):
            continue
        for aid in ids_in_adr(p):
            if aid not in covered:
                missing.append((aid, f))
    if not missing:
        return 0
    print("Sigil: ADR(s) without a bookmark:", file=sys.stderr)
    for aid, f in missing:
        print(f"  ADR-{aid:04d}  ({f})", file=sys.stderr)
        print(f'    sigil add <file>:<line> -d "ADR-{aid:04d} — <why>"', file=sys.stderr)
    print("  Or declare `code_anchors: none` in the ADR frontmatter.", file=sys.stderr)
    print("  Bypass: SIGIL_SKIP=1 git commit ...", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main())
```

### Alternatives explored

**Approach:** Claude Code PostToolUse hook on Write/Edit to `docs/decisions/*.md`.
**Why we didn't use it:** Covers only Claude's edits; leaves BR's own edits ungated. The whole point of the enforcement is to catch the human path too.
**When it might be relevant:** If Claude starts authoring most ADRs unattended, a Claude-specific hook could layer *on top of* pre-commit for faster feedback mid-edit.

**Approach:** Annotate ADRs with explicit `bookmark_ids: [993_1471, …]` fields and enforce bidirectional linkage.
**Why we didn't use it (yet):** Sigil IDs are short, non-semantic (`993_1471`), and drift if bookmarks are recreated. The current loose coupling (ADR-NNNN text in bookmark description, ADR-NNNN filename in ADR) is enough for the check and tolerates renames.
**When it might be relevant:** If a sigil subcommand gains "rename ID" or the ADR template grows richer linkage sections.

### Testing strategy
- Unit: feed `adr-check` a fixture repo with (a) covered ADR, (b) uncovered ADR, (c) opted-out ADR, (d) multi-ID bookmark. Assert exit codes.
- Integration: install the hook in sigil's own repo and try to commit a new ADR without a bookmark — expect block.
- Smoke test after rollout: run `sigil adr-orphans` in cognex; expected result is zero orphans because BR's existing bookmarks already follow the `ADR-NNNN — …` convention consistently.

### Learning & insights
- The transcript grep is a surprisingly strong efficacy probe because Claude Code persists every Bash invocation verbatim — no custom instrumentation required.
- The `ADR-NNNN — why-one-liner` bookmark description convention BR already uses is the linchpin: it makes the injected summary self-sufficient AND makes text-based linkage enforcement trivial. Worth codifying as a required pattern in the README.
- The mnemex-gate pattern (ADR 002 in PA) is generalizable: "soft rule that keeps slipping → mechanical hook, never stronger wording." This is the second application.

### References & resources
- PA ADR 002 — Mnemex PreToolUse gate (precedent for mechanical enforcement): `~/devel/pa/docs/decisions/002-mnemex-pretool-gate.md`
- Sigil `validate --fix`: already shipped, confirmed working on 10 drifted bookmarks in cognex.
- Cognex as the reference ADR-linked corpus: 64 bookmarks, most with `ADR-NNNN — …` descriptions.

---

## Context for Next Session

**Pick up from:** implement `sigil adr-check` as a subcommand and wire it into the existing pre-commit hook alongside `validate --fix`. Draft is in the Deep Dive above.

**Do first:** check whether sigil already has an `install-hooks` subcommand. If yes, extend it. If no, scaffold it so pre-commit install is one command across all BR's .sigil repos (currently 10).

**Then:** update the ADR template (in whichever repo holds the canonical template — probably per-repo) to include `code_anchors:` with an explanatory comment.

**Validation:** after rollout, re-run the efficacy grep in a month. Expected new signal: `adr-check` invocations showing up in transcripts (likely blocked-then-retry flows), and new `sigil add` spikes correlated with ADR commits.
