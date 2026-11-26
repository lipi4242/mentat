#!/bin/sh
# Put ~/.local/bin on the PATH of new login shells, once per file: ~/.profile
# (sh, dash, and bash without its own file), plus the file the user's login
# shell really reads instead — ~/.zprofile for zsh (the macOS default; zsh
# never reads ~/.profile), the first existing ~/.bash_profile / ~/.bash_login
# for bash (it then skips ~/.profile). A file that already mentions
# .local/bin is left alone. Prints the files it checked, one per line.
#
#   sh worker/scripts/login-path.sh        (uses $HOME and $SHELL)
set -eu
files=.profile
case "${SHELL:-}" in
  */zsh) files="$files .zprofile" ;;
  */bash) for f in .bash_profile .bash_login; do [ -f "$HOME/$f" ] && { files="$files $f"; break; }; done ;;
esac
for f in $files; do
  grep -qs '.local/bin' "$HOME/$f" ||
    printf '\n# mentat-admin: node/npm/npx live in ~/.local/bin\n[ -d "$HOME/.local/bin" ] && PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/$f"
  echo "$f"
done
