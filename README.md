# dotfiles

Portable zsh + Ghostty + starship setup for macOS and Linux.

## What's here

| File | Symlinked to | Purpose |
|------|--------------|---------|
| `zsh/zshrc` | `~/.zshrc` | Interactive shell: history, lazy nvm, completion cache, plugins, prompt |
| `zsh/zprofile` | `~/.zprofile` | Homebrew env (macOS or Linuxbrew) |
| `config/ghostty/config` | `~/.config/ghostty/config` | Terminal: Catppuccin Mocha, JetBrainsMono Nerd Font |
| `config/starship.toml` | `~/.config/starship.toml` | Prompt |
| `git/gitconfig` | `~/.gitconfig` | Identity + `include` of untracked `~/.gitconfig.local` |

## Install

```sh
git clone git@github.com:jaymoran103/dotfiles.git ~/dotfiles
cd ~/dotfiles
./install.sh          # installs deps + symlinks configs
exec zsh
```

`./install.sh link` symlinks only; `./install.sh deps` installs tools only.
Existing real files are backed up to `*.pre-dotfiles.<timestamp>` before linking.

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
