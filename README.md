# tide

Per-project persistent browser windows in tmux, over your existing tools
([fsi](https://github.com/dandavison/fzfui), rgi, gitu, micro). Built for
alacritty + tmux with wormhole managing one window per project.

## Model

- **files**, **search**, **git** are long-lived tmux windows, one per project,
  each running the respective tool (fsi / rgi / gitu). `Alt-{j,k,l}` find-or-
  create-and-select the window for the current project. Persistent: switching
  away leaves the tool running; switching back resumes it exactly. Pressing the
  key for the view you're already in returns to the main (work) window.
- **edit** is not a window. Each browser opens micro as a **child** on Enter
  (`RET` on a hunk in gitu); `Ctrl-C` (micro `Save,Quit`) pops back to the
  browser you launched from. The editor is wired purely via env vars —
  `FSI_ACTION=micro`, `RGI_EDITOR=micro`, `GITU_SHOW_EDITOR=micro` — so the
  tools stay unmodified and standalone.
- Switching between views is plain tmux window selection, so no dispatcher, no
  IPC, and every view keeps full state (fzf query, scroll, cursor).

## wormhole integration

tide tags each window it creates with tmux window options `@project =
<store_key>` (wormhole's generic per-project key) and `@view`. wormhole's only
knowledge of these windows is additive and tide-agnostic:

- `close(project)` also kills windows whose `@project` matches the store_key.
- `open(project)` sets `@project` on the main window for consistency.

wormhole's name-based logic (`window_names`, `is_active`, `project_directories`)
is untouched: tide window names (`<store_key>:<view>`) never equal a store_key
(`:` is illegal in git refs) and contain no space, and their `cwd` collapses
into the project's existing ring entry.

## tmux binds

Context is passed by the binding (tmux expands `#{...}` for the pane where the
key fired), so tide acts on exactly that pane and never guesses the "current"
window:

```tmux
bind -n M-j run-shell -b "$HOME/.local/bin/tide files  '#{window_name}' '#{@project}' '#{@view}' '#{pane_current_path}' '#{session_name}'"
bind -n M-k run-shell -b "$HOME/.local/bin/tide search '#{window_name}' '#{@project}' '#{@view}' '#{pane_current_path}' '#{session_name}'"
bind -n M-l run-shell -b "$HOME/.local/bin/tide git    '#{window_name}' '#{@project}' '#{@view}' '#{pane_current_path}' '#{session_name}'"
```

## Install

```
uv tool install -e .
```
