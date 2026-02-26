"""Data models for sigil bookmarks."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import hashlib
import time


@dataclass
class Context:
    before: str  # line above target
    target: str  # the bookmarked line
    after: str   # line below target

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Context":
        return cls(**data)


@dataclass
class Metadata:
    tags: list[str] = field(default_factory=list)
    description: str = ""
    created: str = ""
    accessed: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Metadata":
        return cls(**data)


@dataclass
class Validation:
    status: str = "valid"  # valid, moved, stale, unknown
    last_checked: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Validation":
        return cls(**data)


@dataclass
class Bookmark:
    id: str
    file: str
    line: int
    context: Context
    metadata: Metadata = field(default_factory=Metadata)
    validation: Validation = field(default_factory=Validation)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file": self.file,
            "line": self.line,
            "context": self.context.to_dict(),
            "metadata": self.metadata.to_dict(),
            "validation": self.validation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Bookmark":
        return cls(
            id=data["id"],
            file=data["file"],
            line=data["line"],
            context=Context.from_dict(data["context"]),
            metadata=Metadata.from_dict(data["metadata"]),
            validation=Validation.from_dict(data["validation"]),
        )

    @property
    def short_id(self) -> str:
        """Last 8 chars of ID for display."""
        return self.id[-8:]


def generate_id() -> str:
    """Generate a bookmark ID: bm_{timestamp}_{hash}."""
    ts = int(time.time())
    rand = hashlib.sha256(f"{ts}{time.monotonic_ns()}".encode()).hexdigest()[:4]
    return f"bm_{ts}_{rand}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
