from __future__ import annotations

import tempfile
from pathlib import Path

from .session import VIEWS, Session
from .views import launch


def run(start: str = "files") -> None:
    """Own one full-screen surface, swapping between views until dismissed.

    A view runs until it exits, having optionally written a directive naming
    the next view (and an argument) to the state file. No directive means the
    surface is dismissed.
    """
    session = Session(root=Path.cwd())
    with tempfile.TemporaryDirectory(prefix="tide.") as tmp:
        state = Path(tmp) / "next"
        view, arg = start, None
        while view != "quit":
            if view not in VIEWS:
                raise SystemExit(f"tide: unknown view {view!r}")
            launch(view, arg, session, state)
            view, arg = _next(state, session)


def _next(state: Path, session: Session) -> tuple[str, str | None]:
    if not state.exists():
        return "quit", None
    view, _, arg = state.read_text().strip().partition("\t")
    state.unlink()
    arg = arg or None
    if view == "edit" and arg:
        session.file = arg
    elif view == "search" and arg:
        session.query = arg
    return view or "quit", arg
