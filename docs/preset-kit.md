# The preset kit

`lib/preset_kit.py` is the shared frame for a tool that keeps named presets for one thing and lets you pick one. A preset says which elements show, in what order, and the value of each setting. Every tool on the kit has the same command line, files and keys. `claude-statusline` is the first tool on it.

## What a tool supplies

A tool is one script that subclasses `Tool`. It sets four fields and writes `render()`:

```python
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
from preset_kit import Element, Tool, main

class Prompt(Tool):
    name = "my-prompt"                       # the command, and the config and state dir names
    title = "what my prompt shows"           # a few words for the header
    elements = (
        Element("dir", "directory"),         # kind "show": in or out, and ordered
        Element("git", "git branch"),
        Element("sep", "separator", kind="choice", choices=(" | ", " · ")),
    )
    builtins = {"default": {"show": ["dir", "git"]}}

    def render(self, preset, width):         # lines for the preview pane, ANSI is fine
        return [" ".join(preset["show"])]

    def value(self, key):                    # optional: a live reading beside each element
        return ""

if __name__ == "__main__":
    main(Prompt(), sys.argv[1:])
```

The tool's runtime reads `tool.active_preset()`. It gets `{"show": [keys], "set": {key: value}}`, cleaned of keys the tool no longer has.

## What every tool gets

| | |
| --- | --- |
| `tool` | the picker and editor, in a terminal |
| `tool <preset>` | use a preset |
| `tool -l` | list presets, `•` on the one in use |
| `tool -s` | the preset in use, and where it comes from |
| `tool -r` | back to the default |
| `tool --print [p]` | draw a preset, or the one in use |
| `tool --save NAME` | keep the preset in use as NAME |
| exit code | 0 done, 1 unknown preset or bad name, 2 usage error |

## Files

| | |
| --- | --- |
| built-ins | in the script, as `builtins` |
| yours | `config/<tool>/presets/<preset>.json`, linked to `~/.config/<tool>/presets` by `install.sh` |
| the pick | `~/.local/state/<tool>/active`, one name; no file means the default |

A preset of yours with a built-in's name hides it, and the list calls it `changed`. Deleting it brings the built-in back. `<TOOL>_PRESETS_DIR` and `XDG_STATE_HOME` move the files, for tests.

## Keys

Two screens. The preset list draws the hovered preset on the right, with what it shows. The editor lists every element, shown ones first in order. Edits save as you make them, so `esc` only goes back. Undo all and delete are armed: `⌫` once says what goes, and `⌫` again does it.

| list | | editor | |
| --- | --- | --- | --- |
| `enter` | use it | `space` | show or hide |
| `e` `→` | edit | `←→` | change a setting |
| `n` | new from this | `⇧↑↓` `K` `J` | reorder |
| `⌫ ⌫` | delete yours | `z` `y` | undo, redo |
| `q` `esc` | quit | `⌫ ⌫` | undo all |
| `?` | keys | `esc` `←` | back |

## The worked example: claude-statusline

Claude Code pipes session JSON into `bin/claude-statusline`, and it prints one line from the preset in use. Run by hand in a terminal, the same script opens the picker. Each run keeps its input in `~/.local/state/claude-statusline/sample.json`, so the preview uses your last session's numbers. A pick reaches running sessions on their next refresh.

Its elements are segment functions in a dict, `SEGMENTS`. A new stat is one function and one `Element` line. `ATTACH` joins a segment to the one before with a space, and `APART` sets one off with a wide gap.

## Next on the kit

`starship-preset` and `ghostty-theme-edit` predate the kit. Moving them on means one `Tool` subclass each, with Starship modules or Ghostty colours as the elements. A `color` element kind that opens `color-pick --nested` would serve both.
