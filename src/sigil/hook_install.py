"""Install/manage the sigil pre-commit hook in a git repo.

Design:
- Idempotent via a managed block between markers. Re-running install never
  duplicates lines.
- Preserves any pre-existing user content in .git/hooks/pre-commit outside
  the managed block.
- Creates the file with `#!/bin/sh` if it doesn't exist.
- chmod +x after writing.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Optional

BEGIN_MARKER = "# >>> sigil managed (do not edit between markers)"
END_MARKER = "# <<< sigil managed"

MANAGED_BODY = """\
# Installed by `sigil install-hooks`. Remove markers to uninstall.
# SIGIL_SKIP=1 bypasses both steps.
if [ "${SIGIL_SKIP:-0}" != "1" ]; then
  if command -v sigil >/dev/null 2>&1; then
    sigil validate --fix || exit $?
    sigil adr-check || exit $?
  fi
fi
"""


def _build_block() -> str:
    return f"{BEGIN_MARKER}\n{MANAGED_BODY}{END_MARKER}\n"


def _hook_path(repo_root: Path) -> Path:
    return repo_root / ".git" / "hooks" / "pre-commit"


def install(repo_root: Path) -> tuple[Path, str]:
    """Idempotently install the managed block into .git/hooks/pre-commit.

    Returns (path, action) where action is 'created' | 'updated' | 'unchanged'.
    """
    if not (repo_root / ".git").exists():
        raise FileNotFoundError(f"Not a git repo (no .git at {repo_root})")

    hook = _hook_path(repo_root)
    hook.parent.mkdir(parents=True, exist_ok=True)
    block = _build_block()

    if not hook.exists():
        hook.write_text(f"#!/bin/sh\n{block}", encoding="utf-8")
        _chmod_x(hook)
        return hook, "created"

    existing = hook.read_text(encoding="utf-8")
    new = _replace_or_append(existing, block)
    if new == existing:
        _chmod_x(hook)
        return hook, "unchanged"
    hook.write_text(new, encoding="utf-8")
    _chmod_x(hook)
    return hook, "updated"


def uninstall(repo_root: Path) -> tuple[Path, str]:
    """Remove the managed block. Returns (path, action)."""
    hook = _hook_path(repo_root)
    if not hook.exists():
        return hook, "absent"
    existing = hook.read_text(encoding="utf-8")
    stripped = _strip_block(existing)
    if stripped == existing:
        return hook, "unchanged"
    hook.write_text(stripped, encoding="utf-8")
    return hook, "removed"


def _replace_or_append(existing: str, block: str) -> str:
    """Replace existing managed block in `existing`, or append if absent."""
    start = existing.find(BEGIN_MARKER)
    if start == -1:
        # Append with blank line separator, preserving existing content.
        sep = "" if existing.endswith("\n") else "\n"
        return existing + sep + "\n" + block
    end = existing.find(END_MARKER, start)
    if end == -1:
        # Malformed — append rather than mangle user content.
        return existing + "\n" + block
    end += len(END_MARKER)
    # Consume trailing newline of the old block if present, so replacement
    # doesn't accumulate blank lines across re-runs.
    if end < len(existing) and existing[end] == "\n":
        end += 1
    return existing[:start] + block + existing[end:]


def _strip_block(existing: str) -> str:
    start = existing.find(BEGIN_MARKER)
    if start == -1:
        return existing
    end = existing.find(END_MARKER, start)
    if end == -1:
        return existing
    end += len(END_MARKER)
    if end < len(existing) and existing[end] == "\n":
        end += 1
    return existing[:start] + existing[end:]


def _chmod_x(path: Path) -> None:
    """Ensure the hook file is executable."""
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass
