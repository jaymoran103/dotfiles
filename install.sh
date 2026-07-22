#!/usr/bin/env bash
# Dotfiles installer. Idempotent — safe to re-run.
#   ./install.sh          install deps + symlink configs
#   ./install.sh link     symlink configs only
#   ./install.sh deps     install dependencies only
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"
info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }

# Symlink $1 -> $2, backing up any existing real file first.
backup_and_link() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -e "$dest" && ! -L "$dest" ]]; then
    local bak="$dest.pre-dotfiles.$(date +%Y%m%d%H%M%S)"
    mv "$dest" "$bak"
    info "backed up existing $dest -> $bak"
  fi
  ln -sfn "$src" "$dest"
  info "linked $(basename "$dest")"
}

install_deps() {
  info "Installing dependencies for $OS"
  if [[ "$OS" == "Darwin" ]]; then
    command -v brew >/dev/null || { info "Install Homebrew first: https://brew.sh"; return; }
    brew install starship zsh-autosuggestions nvm || true
    brew install stanmarek/tap/ghost-complete || true   # macOS-only autocomplete
    command -v ghost-complete >/dev/null && ghost-complete install || true
  elif [[ "$OS" == "Linux" ]]; then
    if command -v apt >/dev/null; then
      sudo apt update
      sudo apt install -y zsh zsh-autosuggestions
    elif command -v pacman >/dev/null; then
      sudo pacman -S --needed --noconfirm zsh zsh-autosuggestions
    fi
    command -v starship >/dev/null || sh -c "$(curl -fsSL https://starship.rs/install.sh)" -- -y
    [[ -d "$HOME/.nvm" ]] || \
      sh -c "$(curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh)"
    info "NOTE: ghost-complete is macOS-only and is skipped on Linux (the shell"
    info "      config degrades gracefully when it's absent). No special font needed."
  fi
}

link_configs() {
  backup_and_link "$DOTFILES/zsh/zshrc"             "$HOME/.zshrc"
  backup_and_link "$DOTFILES/zsh/zprofile"          "$HOME/.zprofile"
  backup_and_link "$DOTFILES/config/ghostty/config" "$HOME/.config/ghostty/config"
  backup_and_link "$DOTFILES/config/starship.toml"  "$HOME/.config/starship.toml"
  backup_and_link "$DOTFILES/git/gitconfig"         "$HOME/.gitconfig"
  if [[ ! -f "$HOME/.gitconfig.local" ]]; then
    : > "$HOME/.gitconfig.local"
    info "created empty ~/.gitconfig.local (put machine-specific git settings here)"
  fi
}

case "${1:-all}" in
  deps) install_deps ;;
  link) link_configs ;;
  all)  install_deps; link_configs ;;
  *)    echo "usage: $0 [all|deps|link]" >&2; exit 1 ;;
esac

info "Done. Start a fresh shell:  exec zsh"
