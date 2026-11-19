# tide

Per-project persistent browser windows in tmux, over your existing tools
([fsi](https://github.com/dandavison/fzfui), rgi, gitu, a terminal editor). Built for
alacritty + tmux with wormhole managing one window per project.

## Model

- **files**, **search**, **git** are long-lived tmux windows, one per project,
  each running the respective tool (fsi / rgi / gitu). `Alt-{j,k,l}` find-or-
  create-and-select the window for the current project. Persistent: switching
  away leaves the tool running; switching back resumes it exactly. `Alt-;`
  (`tide home`) always returns to the main (work) window; pressing the key for
  the view you're already in does the same (unless the editor is active, in which
  case it saves and quits the editor, returning to the browser tool, and in the
  files view clears the fzf query).
  `bin/f-tide` (pick a project, then a view) instead always lands on the view
  fresh: the editor popped and the files query cleared. `f-tide recent` picks
  from files recently opened in the editor, across projects, and opens the
  chosen one in the editor in its project's files view; it reads
  `~/.config/micro/recent-files`, which a micro `onBufferOpen` hook and an emacs
  `find-file-hook` in my dotfiles append to. Files not under a project wormhole
  is tracking are not offered.
- **edit** is not a window. Each browser opens the editor as a **child** on
  Enter (`RET` on a hunk in gitu); quitting it pops back to the browser you
  launched from. The editor is `tui-editor`, a script in my dotfiles that runs
  emacs or micro. It is wired purely via env vars — `FSI_ACTION`, `RGI_EDITOR`,
  `GITU_SHOW_EDITOR` — so the tools stay unmodified and standalone. To pop the
  editor, tide sends the editor's save-and-quit keys (`QUIT_KEYS` in
  `src/tide/__init__.py`).
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
