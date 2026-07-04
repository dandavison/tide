from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from .session import Session

Command = Callable[[str | None, Session], list[str]]


def launch(view: str, arg: str | None, session: Session, state: Path) -> None:
    """Run the tool backing `view`, inheriting the terminal.

    The tool writes the next-view directive to $TIDE_STATE before exiting; the
    dispatcher reads it once the child returns. stdout is the tty (the tools
    draw there), so the state file is the only channel that survives.
    """
    env = os.environ | {
        "TIDE_STATE": str(state),
        "TIDE_ROOT": str(session.root),
        "TIDE_QUERY": session.query,
        "TIDE_QUERY_OUT": str(state.with_name("query")),
    }
    subprocess.run(_COMMANDS[view](arg, session), cwd=session.root, env=env)


def _files(arg: str | None, session: Session) -> list[str]:
    return ["fsi", arg or str(session.root)]


def _search(arg: str | None, session: Session) -> list[str]:
    # rgi's query is a full `rg ...` command line, restored verbatim via
    # $TIDE_QUERY (set in launch()), not re-parsed as a pattern argument.
    return ["rgi"]


def _git(arg: str | None, session: Session) -> list[str]:
    return ["gitu"]


def _edit(arg: str | None, session: Session) -> list[str]:
    target = arg or session.file or ""
    path, _, line = target.partition(":")
    if not path:
        return ["micro"]
    return ["micro", *([f"+{line}"] if line else []), path]


_COMMANDS: dict[str, Command] = {
    "files": _files,
    "search": _search,
    "git": _git,
    "edit": _edit,
}
