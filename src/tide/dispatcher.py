from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .session import VIEWS, Session
from .views import launch


def run(start: str = "files") -> None:
    """Own one full-screen surface, swapping between views until dismissed.

    Session state (last file, last query) is persisted per project root and
    restored on launch, so dismissing and re-summoning resumes where you were.
    """
    session = Session(root=Path.cwd())
    store = _store_path(session.root)
    _restore(session, store)
    with tempfile.TemporaryDirectory(prefix="tide.") as tmp:
        state = Path(tmp) / "next"
        view, arg = start, None
        while view != "quit":
            if view not in VIEWS:
                raise SystemExit(f"tide: unknown view {view!r}")
            launch(view, arg, session, state)
            _capture_query(session, state)
            view, arg = _next(state, session)
            _persist(session, store)


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


def _capture_query(session: Session, state: Path) -> None:
    """Pick up the query a view (rgi) reported via $TIDE_QUERY_OUT on exit."""
    out = state.with_name("query")
    if out.exists():
        session.query = out.read_text().strip()
        out.unlink()


def _store_path(root: Path) -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    directory = Path(base) / "tide"
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(str(root).encode(), usedforsecurity=False).hexdigest()[:16]
    return directory / f"{key}.json"


def _restore(session: Session, store: Path) -> None:
    try:
        data = json.loads(store.read_text())
    except (OSError, ValueError):
        return
    session.file = data.get("file") or None
    session.query = data.get("query") or ""


def _persist(session: Session, store: Path) -> None:
    store.write_text(json.dumps({"file": session.file, "query": session.query}))
