# dotfiles

Portable zsh + Ghostty + starship setup for macOS and Linux.

## What's here

| File | Symlinked to | Purpose |
|------|--------------|---------|
| `zsh/zshrc` | `~/.zshrc` | Interactive shell: history, lazy nvm, completion cache, plugins, prompt |
| `zsh/zprofile` | `~/.zprofile` | Homebrew env (macOS or Linuxbrew) |
| `config/ghostty/config` | `~/.config/ghostty/config` | Terminal: SF Mono, block cursor, `theme =` names a file in `themes/` |
| `config/ghostty/themes/` | `~/.config/ghostty/themes` | Colour schemes: ayu, gruvbox, jellybeans, srcery |
| `bin/ghostty-theme` | `~/.local/bin/ghostty-theme` | Theme picker — see below |
| `bin/ghostty-theme-edit` | `~/.local/bin/ghostty-theme-edit` | Theme editor — see below |
| `bin/icons-batch` | `~/.local/bin/icons-batch` | One DiceBear blob PNG per seed, into `icons-<timestamp>/` |
| `bin/color-pick` | `~/.local/bin/color-pick` | Colour picker any script or TUI can call — see below |
| `config/starship.toml` | `~/.config/starship.toml` | Prompt |
| `git/gitconfig` | `~/.gitconfig` | Identity + `include` of untracked `~/.gitconfig.local` |

## Install

```sh
git clone https://github.com/jaymoran103/dotfiles.git ~/dotfiles
cd ~/dotfiles
./install.sh          # installs deps + symlinks configs
exec zsh
```

`./install.sh link` symlinks only; `./install.sh deps` installs tools only.
Existing real files are backed up to `*.pre-dotfiles.<timestamp>` before linking.

### New Linux machine — full sequence

Validated on Ubuntu 24.04. Run in order:

```sh
cat /etc/os-release                       # 1. confirm the distro (see caveat below)
git clone https://github.com/jaymoran103/dotfiles.git ~/dotfiles
cd ~/dotfiles && ./install.sh             # 2. deps + symlinks
chsh -s "$(command -v zsh)"               # 3. make zsh the login shell (log out/in)
exec zsh                                  # 4. start using it now
nvm install --lts                         # 5. install a Node version (lazy-load works, but none ships)
corepack enable                           # 6. enable pnpm
```

**Distro caveat:** `install.sh`'s package step is tested on **apt** (Debian/Ubuntu).
It also has a `pacman` (Arch) branch that's untested, and **no `dnf` (Fedora/RHEL)
branch** — on those, install the two packages by hand:
`zsh zsh-autosuggestions`, then re-run `./install.sh link`. Everything else
(starship, nvm, symlinks, the shell config) is distro-independent and works as-is.

## Dependencies (installed by `install.sh`)

- **starship** — prompt
- **zsh-autosuggestions** — inline history suggestions
- **nvm** — Node version manager (lazy-loaded)
- **ghost-complete** — *macOS-only* terminal autocomplete (skipped on Linux; the
  shell config degrades gracefully when it's absent)

The prompt uses plain-text symbols only, so **no special/Nerd font is required** —
it renders the same in any monospace font.

### Linux notes
- `zsh-autosuggestions` comes from the distro package (apt/pacman); the shell config
  searches Homebrew, apt, and Arch install paths automatically.
- If zsh isn't your login shell yet: `chsh -s "$(command -v zsh)"` (log out/in after).

## Machine-specific settings

Anything private or per-machine (corp CA certs, work remotes, tokens) goes in
`~/.gitconfig.local`, which is **not tracked**. `install.sh` creates an empty one.

## Notes
- `~/.zshrc` lazy-loads nvm, so the *first* `node`/`npm` in a shell pays a one-time
  ~250ms load; every shell after starts in ~50ms.
- Re-running `ghost-complete install` may overwrite the guarded ghost-complete blocks
  in `~/.zshrc` with absolute paths — re-run `./install.sh link` to restore.

## Switching themes

```sh
ghostty-theme              # picker: arrow keys preview live, enter keeps, esc reverts
ghostty-theme theme-ayu    # apply directly
ghostty-theme -l           # list names
```

Moving through the list repaints the current window immediately via OSC colour
escapes, so what you see is the real thing rather than a swatch. Enter rewrites
the `theme =` line in `config`; other already-open Ghostty windows pick it up on
`Cmd+Shift+,` (or the next time they launch).

To add a theme, drop a Ghostty colour-scheme file into `config/ghostty/themes/`.
`ghostty +list-themes` shows the bundled ones worth copying from.

## Editing themes

```sh
ghostty-theme -e              # theme list: open one, or n for a new one
ghostty-theme -e theme-ayu    # open one straight away (a new name starts a copy)
```

Three levels: the theme list, the theme's elements in groups (base,
cursor, selection, normal and bright palette), and a picker for one
colour. The picker has H S L and R G B sliders drawn as gradients, `#`
for a hex value, and a `P` row that steps through the theme's other
colours. Enter opens the picker, and enter closes it with the change
kept. Esc closes it and undoes the change.

Every change repaints the window as you make it. `s` saves into
`config/ghostty/themes/`, keeping any lines the editor does not manage,
`S` saves as a new name and `a` saves and applies through `ghostty-theme`.
Leaving puts the config's theme back. Needs only `python3`.

## Picking a colour

`color-pick` draws on the terminal and prints the colour you pick on stdout.
Enter keeps it and exits 0. Esc cancels and exits 1 with nothing printed.

```sh
color-pick                                # start from grey
color-pick '#ff8800' -t "accent"          # start from a colour, say what it is for
color-pick -p '#e06c75,#98c379,#61afef'   # offer your own swatches beside the recent ones
color-pick -f rgb                         # 255 136 0 instead of #ff8800
color-pick --tab                          # pick in a new Ghostty tab, answer comes back here
color-pick --split                        # the same, in a split to the right
```

The screen has a hue × lightness grid for a fast first pick, H S L and R G B
sliders to fine-tune, and a swatch row of your `-p` colours and the last 16
picks. Tab moves between the three, arrows move and pick at once, shift moves
by 10. `#` types a hex value, and pasting text with a hex in it takes that
colour from anywhere. `c` copies the hex, `r` returns to the start colour.

### From another script or TUI

Any language can shell out to it, because only the answer goes to stdout:

```sh
hex=$(color-pick "$current" -t "border colour") && apply_border "$hex"
```

A TUI that holds the alternate screen passes `--nested`, then redraws:

```python
def pick_colour(start=None, title=None):
    args = ["color-pick", "--nested"] + (["-t", title] if title else []) + ([start] if start else [])
    r = subprocess.run(args, stdout=subprocess.PIPE, text=True)
    return r.stdout.strip() or None     # None on cancel
```

`color-pick` saves and restores the caller's terminal mode, so a raw-mode
caller needs no setup. Add `--tab` instead of `--nested` to keep the app on
screen while the pick happens beside it. `-o FILE` writes every change to
`FILE` as it happens, for an app that wants a live preview; a cancel writes the
start colour back. macOS asks once to let your terminal control Ghostty, the first
time `--tab` or `--split` runs.
