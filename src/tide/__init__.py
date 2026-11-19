"""tide: per-project persistent browser windows in tmux.

`tide <view> <window_name> <project> <pane_path> <session>` finds-or-creates the
tmux window for (current project, view) and selects it. The binding passes the
context via tmux format expansion (`#{window_name}` etc.), so we act on exactly
the pane where the key fired — no reliance on tmux's ambiguous "current window".

Each browser view is a long-lived tmux window running the tool; the tool opens
the editor (`tui-editor`) as a child on Enter (quitting it pops back), and
switching between views is plain tmux window selection. There is no "edit"
window — editing is always a child of a browser. Summoning a view resumes it
exactly, including an active editor; pressing the view's key again pops the
editor (saving first). `--fresh` instead summons the view with the editor popped
and the files query cleared; `--open PATH` summons the files view fresh and opens
PATH in the editor there.

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

# `zsh -ic` gives the tools the login PATH; the env var makes each open the
# editor (as a child) at the selected line. fsi's fzf listens on a per-pane socket so
# that tide can clear its query. `exec` replaces the shell with the tool so
# the window's root process IS the tool: quitting it closes the window (rather
# than falling back to an interactive shell that looks like the work window).
VIEWS = {
    "files": "exec env FSI_ACTION=tui-editor FZFUI_LISTEN=/tmp/tide-$TMUX_PANE.sock fsi",
    "search": "exec env RGI_EDITOR=tui-editor rgi",
    "git": "exec env GITU_SHOW_EDITOR=tui-editor delta --gitu",
}

# The keys that save and quit each editor tui-editor may run, by process name.
QUIT_KEYS = {
    "micro": ["C-c"],
    "Emacs": ["C-x", "C-s", "C-x", "C-c"],
}


COMMANDS = (*VIEWS, "home")


def main() -> None:
    args = sys.argv[1:]
    open_path = None
    if args[:1] == ["--open"] and len(args) > 1:
        open_path, args = args[1], args[2:]
    fresh = bool(open_path)
    if args[:1] == ["--fresh"]:
        fresh, args = True, args[1:]
    if not args or args[0] not in COMMANDS or (open_path and args[0] != "files"):
        sys.exit(
            f"usage: tide [--fresh | --open <file> files] {{{'|'.join(COMMANDS)}}} <window_name> <project> <view> <path> <session>"
        )
    command = args[0]
    context = args[1:6]
    if len(context) < 5:  # convenience for manual invocation from inside a pane
        context = _tmux(
            "display-message",
            "-p",
            "#{window_name}\t#{@project}\t#{@view}\t#{pane_current_path}\t#{session_name}",
        ).split("\t")
    name, project, current_view, path, session = context
    store_key = project or name
    # `home` always goes to the work window; a view key toggles back if you are
    # already in that view (unless the editor is active, in which case it pops
    # back to the browser tool).
    if command == "home":
        _select_main(store_key, session)
    elif command == current_view:
        window = _find_window(store_key, current_view, session)
        if window and _pop_editor(window):
            if command == "files":
                _clear_query(window)
            return
        _select_main(store_key, session)
    else:
        window = summon(command, store_key, path, session, fresh)
        if open_path:
            _open_in_editor(window, open_path)


def summon(view: str, store_key: str, path: str, session: str, fresh: bool) -> str:
    existing = _find_window(store_key, view, session)
    if existing:
        if fresh:
            _pop_editor(existing)
            if view == "files":
                _clear_query(existing)
        _tmux("select-window", "-t", existing)
        return existing

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
    return window


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


def _pop_editor(window: str) -> bool:
    """If an editor is running as a child in window, save and quit it."""
    processes = _processes(window)
    for name, keys in QUIT_KEYS.items():
        if name in processes:
            _tmux("send-keys", "-t", window, *keys)
            return True
    return False


def _clear_query(window: str) -> None:
    """Clear the search query in fzf so the browser is ready for a fresh search.

    fzf queues the action while the editor is running and applies it when it exits.
    """
    _post_fzf_action(window, "clear-query")


def _open_in_editor(window: str, file: str) -> None:
    """Open file in the editor as a child of the files view, as Enter in fsi does."""
    cwd = _tmux("display-message", "-p", "-t", window, "#{pane_start_path}")
    _post_fzf_action(
        window, f"execute:tui-editor {shlex.quote(os.path.relpath(file, cwd))}"
    )


def _post_fzf_action(window: str, action: str) -> None:
    pane = _tmux("display-message", "-p", "-t", window, "#{pane_id}")
    socket = f"/tmp/tide-{pane}.sock"
    _wait_for(socket)
    subprocess.run(
        ["curl", "-sf", "--unix-socket", socket, "-XPOST", "localhost", "-d", action],
        check=True,
        timeout=5,
    )


def _wait_for(socket: str) -> None:
    """Wait for fzf in a just-created files window to start listening."""
    deadline = time.monotonic() + 5
    while not os.path.exists(socket) and time.monotonic() < deadline:
        time.sleep(0.05)


def _processes(window: str) -> set[str]:
    """The names of the processes running on the window's pane tty."""
    try:
        tty = _tmux("display-message", "-p", "-t", window, "#{pane_tty}")
        if not tty:
            return set()
        out = subprocess.run(
            ["ps", "-t", tty, "-o", "comm="],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return {os.path.basename(line.strip()) for line in out.splitlines()}
    except Exception:
        return set()
