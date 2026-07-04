from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VIEWS = ("files", "search", "git", "edit")


@dataclass
class Session:
    """State threaded across view switches within one tide invocation."""

    root: Path
    query: str = ""
    file: str | None = None
