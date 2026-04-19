"""Local append-only event log for sigil invocations.

Design contract (see docs/decisions/0001-event-log.md):
- One JSONL file under $XDG_STATE_HOME/sigil/events.jsonl.
- One line per CLI invocation (plus hook-inject events written externally).
- Stdlib only. No framework. No remote telemetry.
- Telemetry failure must never crash the CLI — all I/O wrapped + swallowed.
- argv_hash captures invocation *shape* (subcommand + flag names), never values.
  This prevents descriptions / paths / tag strings from leaking into the log.
- Rotation: stat-before-open, rollover at 10 MB to events.jsonl.1 (one backup).
- Line size cap: 4 KB (PIPE_BUF) so concurrent appends stay atomic.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1
ROTATE_BYTES = 10 * 1024 * 1024  # 10 MB
LINE_CAP = 4096  # PIPE_BUF on Linux; keeps concurrent writes atomic
# argv flags whose VALUES carry user content and must never be hashed in.
# Only flag names survive; the following token is replaced by "<v>".
_VALUE_FLAGS = {"-d", "--desc", "--description", "-t", "--tags", "-m", "--message"}


def state_dir() -> Path:
    """XDG state dir for sigil. Honors $XDG_STATE_HOME; falls back to ~/.local/state."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "sigil"


def log_path() -> Path:
    return state_dir() / "events.jsonl"


def argv_skeleton_hash(argv: list[str]) -> str:
    """SHA-256 of the argv *skeleton* — subcommand + flag names only.

    Values after user-content flags (-d, --desc, -t, --tags, ...) are replaced
    with '<v>'. Positional args (file paths, line specs, IDs) are replaced with
    '<p>'. Result: 'same shape of call' correlates across repos without ever
    capturing user-typed content.
    """
    skel: list[str] = []
    i = 0
    # Drop argv[0] (program name)
    args = argv[1:] if argv else []
    while i < len(args):
        tok = args[i]
        if tok.startswith("-"):
            # --flag=value → keep flag, drop value
            if "=" in tok:
                tok = tok.split("=", 1)[0]
            skel.append(tok)
            if tok in _VALUE_FLAGS and i + 1 < len(args):
                skel.append("<v>")
                i += 2
                continue
        else:
            skel.append("<p>")
        i += 1
    return hashlib.sha256("\0".join(skel).encode("utf-8")).hexdigest()[:16]


# Per-process bag of extras that commands can populate for the final log line.
_extras: dict[str, Any] = {}


def add_extra(key: str, value: Any) -> None:
    """Called by cmd_* functions to attach command-specific fields to the event."""
    _extras[key] = value


def _consume_extras() -> dict[str, Any]:
    out = dict(_extras)
    _extras.clear()
    return out


def _maybe_rotate(p: Path) -> None:
    """Rotate if size ≥ ROTATE_BYTES. One backup only (.1), overwritten."""
    try:
        if p.exists() and p.stat().st_size >= ROTATE_BYTES:
            backup = p.with_suffix(p.suffix + ".1")
            os.replace(p, backup)
    except OSError:
        pass  # rotation failure must not block logging


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_fields(repo_root: Optional[Path]) -> dict[str, str]:
    if repo_root is None:
        return {}
    return {"repo": repo_root.name, "repo_root": str(repo_root)}


def write_event(
    cmd: str,
    exit_code: int,
    dur_ms: int,
    argv: list[str],
    repo_root: Optional[Path] = None,
    kind: str = "cli",
    source: Optional[str] = None,
    extras: Optional[dict[str, Any]] = None,
) -> None:
    """Append one event line. Never raises — all failures swallowed."""
    try:
        evt: dict[str, Any] = {
            "v": SCHEMA_VERSION,
            "ts": _now_iso(),
            "kind": kind,
            "cmd": cmd,
            "exit": exit_code,
            "dur_ms": dur_ms,
            "argv_hash": argv_skeleton_hash(argv),
            "source": source or os.environ.get("SIGIL_INVOCATION", "user"),
        }
        evt.update(_repo_fields(repo_root))
        if extras:
            evt.update(extras)

        line = json.dumps(evt, ensure_ascii=False, separators=(",", ":"))
        if len(line.encode("utf-8")) > LINE_CAP:
            # Drop extras and mark truncated rather than risk interleaving
            evt_small = {k: v for k, v in evt.items() if k not in (extras or {})}
            evt_small["truncated"] = True
            line = json.dumps(evt_small, ensure_ascii=False, separators=(",", ":"))

        p = log_path()
        _maybe_rotate(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # Telemetry is never allowed to crash the CLI.
        pass


def read_events(since_days: Optional[int] = None) -> list[dict[str, Any]]:
    """Read events. Malformed lines skipped. Returns [] on missing file."""
    p = log_path()
    if not p.exists():
        return []
    cutoff = None
    if since_days is not None:
        cutoff = time.time() - since_days * 86400
    out: list[dict[str, Any]] = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cutoff is not None:
                    ts = evt.get("ts", "")
                    try:
                        ets = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                            tzinfo=timezone.utc
                        ).timestamp()
                        if ets < cutoff:
                            continue
                    except ValueError:
                        continue
                out.append(evt)
    except OSError:
        return []
    return out


class Timer:
    """Context manager returning elapsed ms via .ms after exit."""

    def __enter__(self) -> "Timer":
        self._t0 = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.ms = int((time.perf_counter() - self._t0) * 1000)
