# tide

A single terminal surface that summons four full-screen views — **files**,
**search**, **git**, **edit** — one at a time. Built for alacritty + tmux,
one window per project, zoomed.

Not a monolith: a thin dispatcher over existing tools
([fsi](https://github.com/dandavison/fzfui), rgi, gitu, micro). The dispatcher
owns the screen and runs exactly one tool at a time; each tool, on a switch
chord, exits after naming the next view.

## Model

- Summoned as a full-screen tmux popup over the current pane. The work pane
  (server, logs, tests) keeps running underneath, undisturbed.
- Always exactly one view, full screen. Switching swaps the whole surface —
  never a split, never a stack.
- micro is stateless: each edit opens a fresh micro; there is no resident
  editor to remote-control.

## Transitions

One chord set, honored inside every view. `Alt` so it never collides with
typing text or a search query:

Held on the right-hand home row, so you can keep `Alt` down and walk across
`j k l ;`:

| Chord   | View       |
|---------|------------|
| `Alt-j` | files      |
| `Alt-k` | search     |
| `Alt-l` | git        |
| `Alt-;` | edit (resumes last file) |
| `Esc` / `Ctrl-c` | dismiss (back to the work pane) |

## Protocol

The dispatcher creates a state file and passes its path as `$TIDE_STATE`. A
view, before exiting, writes the next directive there:

```
<view>              switch to view          e.g. search
<view>\t<arg>       switch, with argument   e.g. edit\tsrc/tide/views.py:42
                    (empty / absent = dismiss the surface)
```

Also exported: `$TIDE_ROOT` (project root) and `$TIDE_QUERY` (last search text).
A view may report its own query back by writing it to `$TIDE_QUERY_OUT` on exit
(rgi does this), so re-summoning search resumes it. stdout belongs to the tool's
TUI, so these files are the only channel that survives a view exit.

Session state (last file, last query) is persisted per project root under
`$XDG_STATE_HOME/tide/`, so dismissing and re-summoning resumes where you were.

## tmux summon

The same `Alt-{j,k,l,;}` chords work from outside: each opens the full-screen
popup straight into its view, so the muscle memory is identical whether tide is
open or not. Launched via interactive zsh because the tmux server's PATH is
minimal.

```tmux
bind -n M-j display-popup -E -d "#{pane_current_path}" -w 100% -h 100% "SKIP_XOLMIS=1 zsh -ic 'tide files'"
bind -n M-k display-popup -E -d "#{pane_current_path}" -w 100% -h 100% "SKIP_XOLMIS=1 zsh -ic 'tide search'"
bind -n M-l display-popup -E -d "#{pane_current_path}" -w 100% -h 100% "SKIP_XOLMIS=1 zsh -ic 'tide git'"
bind -n M-\; display-popup -E -d "#{pane_current_path}" -w 100% -h 100% "SKIP_XOLMIS=1 zsh -ic 'tide edit'"
```

Confirmed: root-table (`-n`) bindings do **not** fire while a popup is focused —
the popup owns input. So the outside chords open the surface and the inside
chords (below) switch views, with no conflict and no guard needed.

## Run

```
uv run tide            # start in files
uv run tide search
```
