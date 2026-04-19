"""ADR ↔ bookmark linkage check for pre-commit.

Contract (agreed in chronicles/2026-04-19-efficacy-followup-and-adr-linkage.md):

- Each ADR's OWN ID is derived from its filename stem only — body mentions
  of other ADR-NNNN are references, not identity.
- Stricter bookmark match: description must begin with `ADR-NNNN` at a word
  boundary. Loose substring match falsely satisfied 0089 via "supersedes
  ADR-0089" in an unrelated bookmark.
- Staged content is read via `git show :<path>` — a pre-commit hook must
  validate what is being committed, not the working tree.
- Filter: Added, Modified, Renamed. Deleted ADRs are handled by a separate
  `adr-orphans` audit (reverse check).
- Opt-out: `code_anchors: none` in ADR frontmatter. `code_anchors: [ids...]`
  with non-empty list also satisfies (informational for now). Missing /
  empty / `required` → hard fail. Forces a deliberate choice per ADR.
- SIGIL_SKIP=1 bypass checked FIRST, before any git/subprocess work, and
  announced to stderr so bypasses are never silent.
- Exit codes:
    0 — all checked ADRs satisfied
    1 — user-correctable: missing linkage
    2 — internal: git failure, unparseable frontmatter, sigil list failure
- stdout: TSV of `adr_id<TAB>path` for failed ADRs (machine-readable).
- stderr: human messages, hints, bypass note.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

DEFAULT_GLOB = "docs/decisions/*.md"
ADR_STEM_ID_RE = re.compile(r"ADR-?0*(\d{1,4})", re.IGNORECASE)
# Bookmark-description pattern: must start with ADR-NNNN at a word boundary.
BOOKMARK_ADR_RE = re.compile(r"^\s*ADR-0*(\d{1,4})\b", re.IGNORECASE)

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_INTERNAL = 2


@dataclass
class Finding:
    adr_id: int
    path: str  # repo-relative
    reason: str  # "no-bookmark", "no-code-anchors"


@dataclass
class FrontmatterStatus:
    """Result of inspecting an ADR's code_anchors field."""
    opted_out: bool  # code_anchors: none
    has_anchors: bool  # code_anchors: [non-empty list]
    declared: bool  # field present at all
    parse_error: Optional[str] = None


# -------- pure helpers (unit-testable without git) --------


def adr_id_from_filename(path: str) -> Optional[int]:
    """Extract ADR's own ID from its filename stem. Returns None if no match.

    Filename-only by design: body mentions are references to OTHER ADRs and
    must not satisfy the check.
    """
    stem = Path(path).stem
    m = ADR_STEM_ID_RE.search(stem)
    return int(m.group(1)) if m else None


def parse_frontmatter_code_anchors(text: str) -> FrontmatterStatus:
    """Narrow stdlib parser. Accepts:

        code_anchors: none
        code_anchors: [a, b, c]      # non-empty list → has_anchors
        code_anchors: []             # empty → declared but neither

    No PyYAML dep (sigil is dependencies=[]). Only parses the single field we
    care about; ignores the rest of the frontmatter.
    """
    if not text.startswith("---"):
        return FrontmatterStatus(False, False, False)
    # Find end of frontmatter block
    end = text.find("\n---", 3)
    if end == -1:
        return FrontmatterStatus(False, False, False, parse_error="unterminated frontmatter")
    block = text[3:end]
    for raw in block.splitlines():
        line = raw.strip()
        if not line.lower().startswith("code_anchors:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value.lower() == "none":
            return FrontmatterStatus(True, False, True)
        if value.startswith("["):
            if not value.endswith("]"):
                return FrontmatterStatus(False, False, True, parse_error="malformed list")
            inner = value[1:-1].strip()
            items = [i.strip() for i in inner.split(",") if i.strip()]
            return FrontmatterStatus(False, len(items) > 0, True)
        # Bare value that's not "none" is not valid for our schema
        return FrontmatterStatus(False, False, True, parse_error=f"expected 'none' or list, got {value!r}")
    return FrontmatterStatus(False, False, False)


def bookmark_covered_ids(bookmarks_json: list[dict]) -> set[int]:
    """Extract ADR IDs from bookmark descriptions. Anchored at start only."""
    ids: set[int] = set()
    for bm in bookmarks_json:
        # Description may be under metadata.description or description depending
        # on schema; support both to avoid brittle coupling.
        desc = ""
        if isinstance(bm, dict):
            if "metadata" in bm and isinstance(bm["metadata"], dict):
                desc = bm["metadata"].get("description") or ""
            if not desc:
                desc = bm.get("description", "") or ""
        m = BOOKMARK_ADR_RE.match(desc)
        if m:
            ids.add(int(m.group(1)))
    return ids


# -------- git / subprocess side --------


def staged_adr_paths(glob: str) -> list[str]:
    """Return repo-relative paths of ADRs in the staged diff matching glob.

    Filter: A(dded), M(odified), R(enamed). Deleted ADRs are out of scope here
    (reverse-check via `adr-orphans`).
    """
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=AMR"],
        text=True,
    )
    paths: list[str] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        # For renames 'R100\told\tnew' — take the new path.
        path = parts[-1]
        if status.startswith("R") and len(parts) >= 3:
            path = parts[2]
        if fnmatch(path, glob):
            paths.append(path)
    return paths


def staged_file_content(path: str) -> str:
    """Read staged version via `git show :<path>` — not working tree."""
    return subprocess.check_output(["git", "show", f":{path}"], text=True)


def sigil_list_json() -> list[dict]:
    """Invoke the local `sigil` CLI to get bookmarks as JSON.

    Uses `sigil` on PATH rather than importing storage directly so the check
    honors whatever sigil version is installed — including future schema
    changes — via the --json contract.
    """
    out = subprocess.check_output(["sigil", "list", "--json"], text=True)
    return json.loads(out)


# -------- main entry point --------


def run(glob: str = DEFAULT_GLOB) -> int:
    """Returns exit code. Prints TSV findings to stdout, messages to stderr."""
    # Bypass FIRST — before any subprocess work. Announce to stderr.
    if os.environ.get("SIGIL_SKIP") == "1":
        print("sigil adr-check: SIGIL_SKIP=1 honored; linkage not enforced.", file=sys.stderr)
        return EXIT_OK

    try:
        paths = staged_adr_paths(glob)
    except subprocess.CalledProcessError as e:
        print(f"sigil adr-check: git failure: {e}", file=sys.stderr)
        return EXIT_INTERNAL
    except FileNotFoundError:
        print("sigil adr-check: git not found on PATH", file=sys.stderr)
        return EXIT_INTERNAL

    if not paths:
        return EXIT_OK  # no ADRs touched; silent pass

    try:
        bookmarks = sigil_list_json()
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"sigil adr-check: could not read bookmarks: {e}", file=sys.stderr)
        return EXIT_INTERNAL

    covered = bookmark_covered_ids(bookmarks)

    findings: list[Finding] = []
    for path in paths:
        adr_id = adr_id_from_filename(path)
        if adr_id is None:
            continue  # touched file in the glob that isn't a numbered ADR

        try:
            content = staged_file_content(path)
        except subprocess.CalledProcessError as e:
            print(f"sigil adr-check: cannot read staged {path}: {e}", file=sys.stderr)
            return EXIT_INTERNAL

        fm = parse_frontmatter_code_anchors(content)
        if fm.parse_error:
            print(f"sigil adr-check: {path}: frontmatter parse error: {fm.parse_error}", file=sys.stderr)
            return EXIT_INTERNAL

        # Pass order:
        #   1. code_anchors: none                 → opt-out, done
        #   2. field missing                       → fail ("required field" rule)
        #   3. declared (list or non-none)         → must also have a bookmark
        #      referencing ADR-NNNN. The list itself is informational in V1;
        #      future work will enforce specific bookmark IDs.
        if fm.opted_out:
            continue
        if not fm.declared:
            findings.append(Finding(adr_id, path, "no-code-anchors"))
            continue
        if adr_id not in covered:
            findings.append(Finding(adr_id, path, "no-bookmark"))

    if not findings:
        return EXIT_OK

    # stdout: machine-readable TSV
    for f in findings:
        sys.stdout.write(f"{f.adr_id}\t{f.path}\t{f.reason}\n")

    # stderr: human-readable guidance
    print("", file=sys.stderr)
    print("sigil adr-check: ADR(s) missing bookmark linkage:", file=sys.stderr)
    for f in findings:
        adr_fmt = f"ADR-{f.adr_id:04d}"
        print(f"  {adr_fmt}  ({f.path}) — {f.reason}", file=sys.stderr)
        if f.reason == "no-bookmark":
            print(
                f'    sigil add <file>:<line> -d "{adr_fmt} — <why>"',
                file=sys.stderr,
            )
        elif f.reason == "no-code-anchors":
            print(
                "    Add `code_anchors: none` or `code_anchors: [...]` to frontmatter.",
                file=sys.stderr,
            )
    print("  Bypass (discouraged): SIGIL_SKIP=1 git commit ...", file=sys.stderr)
    return EXIT_MISSING
