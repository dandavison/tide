"""tide: per-project persistent browser windows in tmux.

`tide <view> <window_name> <project> <pane_path> <session>` finds-or-creates the
tmux window for (current project, view) and selects it. The binding passes the
context via tmux format expansion (`#{window_name}` etc.), so we act on exactly
the pane where the key fired — no reliance on tmux's ambiguous "current window".

Each browser view is a long-lived tmux window running the tool; the tool opens
micro as a child on Enter (Ctrl-C pops back), and switching between views is
plain tmux window selection. There is no "edit" window — editing is always a
child of a browser. Summoning a view always ensures the root browser tool is
foregrounded, automatically saving and popping micro (via Ctrl-C) if active.

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
import time

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
    "git": "exec env GITU_SHOW_EDITOR=micro delta --gitu",
}


COMMANDS = (*VIEWS, "home")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(
            f"usage: tide {{{'|'.join(COMMANDS)}}} <window_name> <project> <view> <path> <session>"
        )
    command = sys.argv[1]
    context = sys.argv[2:7]
    if len(context) < 5:  # convenience for manual invocation from inside a pane
        context = _tmux(
            "display-message",
            "-p",
            "#{window_name}\t#{@project}\t#{@view}\t#{pane_current_path}\t#{session_name}",
        ).split("\t")
    name, project, current_view, path, session = context
    store_key = project or name
    # `home` always goes to the work window; a view key toggles back if you are
    # already in that view (unless micro is active, in which case it pops back
    # to the browser tool).
    if command == "home":
        _select_main(store_key, session)
    elif command == current_view:
        window = _find_window(store_key, current_view, session)
        if window and _pop_micro(window):
            if command == "files":
                _clear_query(window, wait_for_micro=True)
            return
        _select_main(store_key, session)
    else:
        summon(command, store_key, path, session)


def summon(view: str, store_key: str, path: str, session: str) -> None:
    existing = _find_window(store_key, view, session)
    if existing:
        popped = _pop_micro(existing)
        if view == "files":
            _clear_query(existing, wait_for_micro=popped)
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


def _pop_micro(window: str) -> bool:
    """If micro is running as a child in window, pop back to the browser tool."""
    if not _has_process(window, "micro"):
        return False
    _tmux("send-keys", "-t", window, "C-c")
    return True


def _clear_query(window: str, *, wait_for_micro: bool = False) -> None:
    """Clear the search query in fzf so the browser is ready for a fresh search."""
    if wait_for_micro:
        for _ in range(20):
            if not _has_process(window, "micro"):
                break
            time.sleep(0.005)
    _tmux("send-keys", "-t", window, "C-e", "C-u")


def _has_process(window: str, name: str) -> bool:
    """Check whether a process named `name` is running on the window's pane tty."""
    try:
        tty = _tmux("display-message", "-p", "-t", window, "#{pane_tty}")
        if not tty:
            return False
        out = subprocess.run(
            ["ps", "-t", tty, "-o", "comm="],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return any(os.path.basename(line.strip()) == name for line in out.splitlines())
    except Exception:
        return False
