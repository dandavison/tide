-- tide Hammerspoon module: tide views as global hotkeys, either in the current
-- tmux window or, via a project picker popup, in any wormhole project.

local M = {}

-- Resolve tmux via a login shell (hs.execute(_, true)) so GUI-launched
-- Hammerspoon picks up Homebrew's PATH rather than launchd's minimal one.
local tmux = hs.execute("command -v tmux", true):gsub("%s+$", "")

local tasks = {} -- retain tasks so GC doesn't drop their completion callbacks

local function run(binary, args, done)
    local task
    task = hs.task.new(binary, function(exitCode)
        tasks[task] = nil
        if done then done(exitCode) end
    end, args)
    tasks[task] = true
    task:start()
end

local function focusAlacritty()
    local app = hs.application.find("alacritty")
    if not (app and app:isFrontmost()) then
        hs.application.launchOrFocus("/Applications/Alacritty.app")
    end
end

-- Alacritty, not tmux, must own the mouse while a popup is up. A popup is not a
-- pane: tmux forwards mouse events to the popup's program only if that program
-- asked for mouse mode and drops them otherwise (popup_key_cb), yet `mouse on`
-- still enables mouse reporting on the client -- so double-click would select
-- nothing. With mouse off the popup's own screen mode drives reporting, so a
-- plain shell gets native Alacritty selection while a TUI in the popup still
-- gets mouse. display-popup blocks the command queue until the popup is
-- dismissed, so the trailing set restores pane behavior on close.
local function withMouseOff(args)
    local argv = { "set", "-g", "mouse", "off", ";" }
    table.move(args, 1, #args, #argv + 1, argv)
    for _, arg in ipairs({ ";", "set", "-g", "mouse", "on" }) do
        argv[#argv + 1] = arg
    end
    return argv
end

-- tmux display-popup, focusing alacritty first if needed. When the popup is
-- dismissed, focus returns to the previously frontmost app, unless focus has
-- been switched or keepFocus is set (for popups whose action leaves you
-- somewhere in tmux). onSuccess runs if the popup's command exits 0.
function M.popup(args, keepFocus, onSuccess)
    local prev = hs.application.frontmostApplication()
    focusAlacritty()
    run(tmux, withMouseOff(args), function(exitCode)
        if exitCode == 0 and onSuccess then
            onSuccess()
            return
        end
        local front = hs.application.frontmostApplication()
        if not keepFocus
            and prev
            and prev:bundleID() ~= "org.alacritty"
            and prev:isRunning()
            and front
            and front:bundleID() == "org.alacritty"
        then
            prev:activate()
        end
    end)
end

-- The pickers run under an interactive shell: a popup's shell is otherwise
-- non-interactive, so it would miss shell/env.sh, and fzf would fall back to
-- its own defaults rather than FZF_DEFAULT_OPTS.
function M.picker(command)
    return "zsh -ic '" .. os.getenv("HOME") .. "/bin/" .. command .. "'"
end

local function shellPopup()
    M.popup({ "display-popup", "-d", "#{pane_current_path}", "-E", "-w", "100%", "-h", "100%", "-b", "rounded", "-T", "", "SKIP_XOLMIS=1 zsh" })
end

-- Pick a project, switch to its tmux window, and run tide's view there, as
-- tmux M-j/M-k/M-l/M-; do from inside it. With view "recent", pick a recently
-- opened file instead and open it in its project's files view. onSuccess runs
-- after the switch.
local function projectPopup(view, onSuccess)
    M.popup({ "display-popup", "-E", "-w", "60%", "-h", "70%", "-b", "rounded", "-T", "", M.picker("f-tide " .. view) }, true, onSuccess)
end

function M.bindKeys()
    hs.hotkey.bind({ "alt" }, "space", shellPopup)
    -- hyper is caps lock held, via Karabiner.
    local hyper = { "cmd", "alt", "ctrl", "shift" }
    -- ctrl + caps lock, via Karabiner: hyper without shift.
    local ctrlHyper = { "cmd", "alt", "ctrl" }
    hs.hotkey.bind(hyper, "j", function() projectPopup("recent") end)
    hs.hotkey.bind(ctrlHyper, "j", function() projectPopup("files") end)
    -- Copy a project's directory to the clipboard, staying where you are.
    hs.hotkey.bind(ctrlHyper, "c", function()
        M.popup({ "display-popup", "-E", "-w", "60%", "-h", "70%", "-b", "rounded", "-T", "", M.picker("f-tide copy-path") })
    end)
    hs.hotkey.bind(hyper, "k", function() projectPopup("search") end)
    hs.hotkey.bind(hyper, "l", function() projectPopup("git") end)
    hs.hotkey.bind(hyper, "space", function() projectPopup("home", shellPopup) end)
    hs.hotkey.bind(hyper, ";", function() projectPopup("home") end)
    -- tide's git view in the current tmux window, i.e. tmux M-l there: given
    -- no context, tide reads the current pane's.
    hs.hotkey.bind({ "cmd" }, "m", function()
        focusAlacritty()
        run(os.getenv("HOME") .. "/.local/bin/tide", { "git" })
    end)
end

return M
