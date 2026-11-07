"""Hamis `systemctl`, `journalctl`, `loginctl` és `claude` a PATH elején.

Állapottartó: az `enable --now`/`start`/`restart` aktívvá tesz, a `stop`/
`disable --now` leállít, az `is-active`/`is-enabled` ebből válaszol. Minden
hívás a `calls` naplóba kerül. Hibát injektálni a `fail` fájllal lehet: ha a
hívás argumentumai tartalmazzák valamelyik sorát, a hamis systemctl 1-gyel lép ki.
"""
from __future__ import annotations
import os
import tempfile
from pathlib import Path

SYSTEMCTL = r'''#!/bin/sh
D="$FAKE_DIR"; echo "systemctl $*" >> "$D/calls"
[ "$1" = "--user" ] && shift
if [ -s "$D/fail" ]; then
  while IFS= read -r pat; do
    case "systemctl --user $*" in *"$pat"*) echo "hamis hiba: $pat" >&2; exit 1;; esac
  done < "$D/fail"
fi
verb="$1"; shift; now=0
[ "$1" = "--now" ] && { now=1; shift; }
mkdir -p "$D/active" "$D/enabled"
# mint a valódi systemd: nem létező unit-fájlt nem lehet engedélyezni/letiltani
if [ -n "$FAKE_UNITS" ] && { [ "$verb" = enable ] || [ "$verb" = disable ]; }; then
  for u in "$@"; do [ -e "$FAKE_UNITS/$u" ] || { echo "Unit file $u does not exist." >&2; exit 1; }; done
fi
case "$verb" in
  enable) for u in "$@"; do touch "$D/enabled/$u"; [ $now = 1 ] && touch "$D/active/$u"; done;;
  disable) for u in "$@"; do rm -f "$D/enabled/$u"; [ $now = 1 ] && rm -f "$D/active/$u"; done;;
  start|restart) for u in "$@"; do touch "$D/active/$u"; done;;
  stop) for u in "$@"; do rm -f "$D/active/$u"; done;;
  is-active) [ -e "$D/active/$1" ] && { echo active; exit 0; }; echo inactive; exit 3;;
  is-enabled) [ -e "$D/enabled/$1" ] && { echo enabled; exit 0; }; echo disabled; exit 1;;
esac
exit 0
'''
JOURNALCTL = '#!/bin/sh\necho "journalctl $*" >> "$FAKE_DIR/calls"\ncat "$FAKE_DIR/journal" 2>/dev/null\nexit 0\n'
LOGINCTL = '#!/bin/sh\necho yes\n'
CLAUDE = r'''#!/bin/sh
echo "claude $*" >> "$FAKE_DIR/calls"
if [ "$1 $2" = "auth status" ]; then
  # a valódi claude-hoz hasonlóan a CLAUDE_CODE_OAUTH_TOKEN is login; "bad-token" = lejárt
  if [ -e "$FAKE_DIR/logged-out" ] && { [ -z "$CLAUDE_CODE_OAUTH_TOKEN" ] || [ "$CLAUDE_CODE_OAUTH_TOKEN" = bad-token ]; }; then
    echo '{"loggedIn": false}'; exit 1; fi
  env > "$FAKE_DIR/auth-env"
  echo '{"loggedIn": true}'; exit 0
fi
[ "$1" = "-p" ] && { cat "$FAKE_DIR/claude-says" 2>/dev/null; exit 1; }
[ "$1" = "plugin" ] && { [ -e "$FAKE_DIR/plugin-fail" ] && { cat "$FAKE_DIR/plugin-fail" >&2; exit 1; }; exit 0; }
exit 0
'''


TMUX = '#!/bin/sh\necho "tmux $*" >> "$FAKE_DIR/calls"\n[ "$1" = capture-pane ] && { cat "$FAKE_DIR/pane" 2>/dev/null; exit 0; }\nexit 0\n'


class FakeBin:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        for name, body in (("systemctl", SYSTEMCTL), ("journalctl", JOURNALCTL),
                           ("loginctl", LOGINCTL), ("claude", CLAUDE), ("tmux", TMUX)):
            p = self.bin / name
            p.write_text(body)
            p.chmod(0o755)
        self.claude = self.bin / "claude"
        self.tmux = self.bin / "tmux"
        self._saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_DIR", "FAKE_UNITS")}
        os.environ["PATH"] = f"{self.bin}:{os.environ.get('PATH', '')}"
        os.environ["FAKE_DIR"] = str(self.dir)

    def units_in(self, unit_dir) -> None:
        """Az enable/disable csak létező unit-fájlra sikerül (a valódi viselkedés)."""
        os.environ["FAKE_UNITS"] = str(unit_dir)

    def fail_on(self, pattern: str) -> None:
        with (self.dir / "fail").open("a") as f:
            f.write(pattern + "\n")

    def journal(self, text: str) -> None:
        (self.dir / "journal").write_text(text)

    def claude_says(self, text: str) -> None:
        (self.dir / "claude-says").write_text(text)

    def pane(self, text: str) -> None:
        (self.dir / "pane").write_text(text)

    def plugin_fail(self, text: str) -> None:
        (self.dir / "plugin-fail").write_text(text)

    def logged_out(self) -> None:
        (self.dir / "logged-out").touch()

    def set_active(self, unit: str) -> None:
        (self.dir / "active").mkdir(exist_ok=True)
        (self.dir / "active" / unit).touch()

    def calls(self) -> list[str]:
        p = self.dir / "calls"
        return p.read_text().splitlines() if p.exists() else []

    def cleanup(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()
