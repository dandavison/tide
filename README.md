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

| Chord   | View       | Mnemonic                    |
|---------|------------|-----------------------------|
| `Alt-f` | files      | **f**iles (index, home key) |
| `Alt-j` | search     | index, home key             |
| `Alt-d` | git        | **d**iff                    |
| `Alt-k` | edit       | resume last buffer          |
| `Ctrl-c`| dismiss    | (micro: `Save,Quit`)        |

## Protocol

The dispatcher creates a state file and passes its path as `$TIDE_STATE`. A
view, before exiting, writes the next directive there:

```
<view>              switch to view          e.g. search
<view>\t<arg>       switch, with argument   e.g. edit\tsrc/tide/views.py:42
                    (empty / absent = dismiss the surface)
```

Also exported: `$TIDE_ROOT` (project root), `$TIDE_QUERY` (last search text, so
`Alt-j` from files carries the typed text into rgi). stdout belongs to the
tool's TUI, so the state file is the only channel that survives a view exit.

Wiring each tool to emit directives is per-tool and incremental; the engine is
ready the moment a tool writes to `$TIDE_STATE`.

## tmux summon

The same `Alt-{f,j,d,k}` chords work from outside: each opens the full-screen
popup straight into its view, so the muscle memory is identical whether tide is
open or not.

```tmux
bind -n M-f display-popup -E -w 100% -h 100% 'tide files'
bind -n M-j display-popup -E -w 100% -h 100% 'tide search'
bind -n M-d display-popup -E -w 100% -h 100% 'tide git'
bind -n M-k display-popup -E -w 100% -h 100% 'tide edit'
```

Confirmed: root-table (`-n`) bindings do **not** fire while a popup is focused —
the popup owns input. So the outside chords open the surface and the inside
chords (below) switch views, with no conflict and no guard needed.

## Run

```
uv run tide            # start in files
uv run tide search
```
