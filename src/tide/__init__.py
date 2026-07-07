"""tide: per-project persistent browser windows in tmux.

`tide <view> <window_name> <project> <pane_path> <session>` finds-or-creates the
tmux window for (current project, view) and selects it. The binding passes the
context via tmux format expansion (`#{window_name}` etc.), so we act on exactly
the pane where the key fired — no reliance on tmux's ambiguous "current window".

Each browser view is a long-lived tmux window running the tool; the tool opens
micro as a child on Enter (Ctrl-C pops back), and switching between views is
plain tmux window selection. There is no "edit" window — editing is always a
child of a browser.

Windows are tagged `@project = <store_key>` (wormhole's generic key, so wormhole
reaps them on project close) and `@view`. The owning project is the current
window's `@project`, falling back to its name (wormhole names the main project
window after the store_key).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys

# The tmux server runs with a minimal PATH; ensure we can find tmux. We stay on
# the right server via $TMUX, inherited from the run-shell that invoked us.
os.environ["PATH"] = os.pathsep.join(
    [
        os.path.expanduser("~/bin"),
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        os.environ.get("PATH", ""),
    ]
)

# `zsh -ic` gives the tools the login PATH; the env var makes each open micro
# (as a child) at the selected line. `exec` replaces the shell with the tool so
# the window's root process IS the tool: quitting it closes the window (rather
# than falling back to an interactive shell that looks like the work window).
VIEWS = {
    "files": "exec env FSI_ACTION=micro fsi",
    "search": "exec env RGI_EDITOR=micro rgi",
    "git": "exec env GITU_SHOW_EDITOR=micro gitu",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in VIEWS:
        sys.exit(
            f"usage: tide {{{'|'.join(VIEWS)}}} <window_name> <project> <view> <path> <session>"
        )
    view = sys.argv[1]
    context = sys.argv[2:7]
    if len(context) < 5:  # convenience for manual invocation from inside a pane
        context = _tmux(
            "display-message",
            "-p",
            "#{window_name}\t#{@project}\t#{@view}\t#{pane_current_path}\t#{session_name}",
        ).split("\t")
    name, project, current_view, path, session = context
    store_key = project or name
    if current_view == view:
        # Pressing the current view's key toggles back to the work window.
        _select_main(store_key, session)
    else:
        summon(view, store_key, path, session)


def summon(view: str, store_key: str, path: str, session: str) -> None:
    existing = _find_window(store_key, view, session)
    if existing:
        _tmux("select-window", "-t", existing)
        return

    launch = f"SKIP_XOLMIS=1 zsh -ic {shlex.quote(VIEWS[view])}"
    window = _tmux(
        "new-window",
        "-t",
        f"{session}:",
        "-P",
        "-F",
        "#{window_id}",
        "-n",
        f"{store_key}:{view}",
        "-c",
        path,
        launch,
    )
    _tmux("set-option", "-w", "-t", window, "@project", store_key)
    _tmux("set-option", "-w", "-t", window, "@view", view)
    _tmux("select-window", "-t", window)


def _select_main(store_key: str, session: str) -> None:
    """Select the main project window (wormhole names it after the store_key)."""
    listing = _tmux("list-windows", "-t", session, "-F", "#{window_id}\t#{window_name}")
    for line in listing.splitlines():
        window, name = (line.split("\t") + [""])[:2]
        if name == store_key:
            _tmux("select-window", "-t", window)
            return


def _find_window(store_key: str, view: str, session: str) -> str | None:
    listing = _tmux(
        "list-windows", "-t", session, "-F", "#{window_id}\t#{@project}\t#{@view}"
    )
    for line in listing.splitlines():
        window, project, window_view = (line.split("\t") + ["", ""])[:3]
        if project == store_key and window_view == view:
            return window
    return None


def _tmux(*args: str) -> str:
    return subprocess.run(
        ["tmux", *args], capture_output=True, text=True, check=True
    ).stdout.strip()
