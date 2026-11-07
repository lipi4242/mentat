"""Képességfa, phase 2: the guard's net under `where --find` (for szerep_dontes).

needs(root, tool, inp, cwd)   -> True: new executable code, a unit, a schedule or a new package,
                                 and no fresh decided capability receipt (szerep_dontes denies it
                                 in both modes, with the finder's command: the agent resolves it).
touched(root, tool, inp, cwd) -> path: the receipts are written by hand (always deny).

A NEW file only (Write to a path that does not exist, or a shell redirect/copy to one) with an
executable suffix anywhere in the repo outside .mentat/ and .claude/, or a .service/.timer;
`systemctl --user enable|link`, `launchctl load|bootstrap`, `crontab` (not -l); a package install
that NAMES a package (pip/uv/npm/pnpm/yarn/bun). Restoring locked dependencies (`npm install`,
`npm ci`, `pip install -r`) and editing existing files stay open. Fresh = decided in the last
FRESH_HOURS, and only with its line in the finder's ledger (LEDGER: receipt name + sha256), so a
receipt that the finder did not write, or edited after its decision, opens nothing (integrity, not
authenticity: whoever can write both the ledger and the receipt still opens it).
Known limits: a net, not the process (inline code in a shell command, a string built at run time
is not seen); and a fresh receipt opens every new capability for FRESH_HOURS, not only the one it
decided on.
"""
import calendar
import hashlib
import json
import os
import pathlib
import time

from szerep_bash import commands
from szerep_kapu import _written
from szerep_kint import real, under

RECEIPTS = os.path.join(".mentat", "state", "capability-receipts")
FRESH_HOURS = 6
EXEC = (".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash")
UNIT = (".service", ".timer")
SKIP = (".mentat", ".claude", ".git")
INSTALL = {"pip": {"install"}, "pip3": {"install"}, "npm": {"install", "i", "add"}, "pnpm": {"add", "install", "i"},
           "yarn": {"add"}, "bun": {"add", "install", "i"}, "uv": {"add"}}
FINDER = "mentat_brain.py"


LEDGER = "_ledger.jsonl"


def _fresh(root):
    now, d = time.time(), pathlib.Path(root, RECEIPTS)
    try:
        lines = (d / LEDGER).read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return False
    for ln in lines:
        try:
            e = json.loads(ln)
            if now - calendar.timegm(time.strptime(e["decided_at"], "%Y-%m-%dT%H:%M:%SZ")) >= FRESH_HOURS * 3600:
                continue
            body = (d / os.path.basename(e["receipt"])).read_bytes()
            doc = json.loads(body)
            if hashlib.sha256(body).hexdigest() == e["sha256"] and doc["decision"]["decided_at"] == e["decided_at"]:
                return True
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return False


def _new_code(root, p):
    f = real(p)
    if not under(f, real(root)) or os.path.lexists(p):
        return False
    rel = os.path.relpath(f, real(root)).split(os.sep)
    return rel[0] not in SKIP and (f.endswith(UNIT) or f.endswith(EXEC))


VALUED = {"--prefix", "-C", "--cwd", "--dir", "--filter", "-w", "--workspace"}


def _plain(words):
    """The non-flag words, without a flag's value (`--prefix site`) or a bare fd (`2` of `2>&1`)."""
    out, skip = [], False
    for w in words:
        if skip:
            skip = False
        elif w in VALUED:
            skip = True
        elif not w.startswith("-") and not w.isdigit() and not set(w) & set("<>&|;$`"):
            out.append(w)
    return out


def _command(name, words):
    sub = _plain(words[1:])
    if name == "systemctl":
        return "--user" in words and bool(sub) and sub[0] in ("enable", "link")
    if name == "launchctl":
        return bool(sub) and sub[0] in ("load", "bootstrap")
    if name == "crontab":
        return "-l" not in words
    if name in ("python", "python3") and words[1:3] == ["-m", "pip"]:
        name, words, sub = "pip", words[2:], sub[1:]
    if name == "uv" and sub[:1] == ["pip"]:
        name, sub = "pip", sub[1:]
    if name in INSTALL and sub and sub[0] in INSTALL[name]:
        named = [w for w in sub[1:] if w not in (".",)]
        return bool(named) and "-r" not in words and "--requirement" not in words
    return False


def needs(root, tool, inp, cwd):
    hit = any(_new_code(root, p) for p in _written(tool, inp, cwd))
    if tool == "Bash" and not hit:
        hit = any(_command(name, words) for name, words, _, _, _ in commands(str(inp.get("command", "")), cwd))
    return hit and not _fresh(root)


def touched(root, tool, inp, cwd):
    """A write to the receipts (szerep_kapu_iras: real targets only). The repo's own finder, by its
    resolved path, may name them; a commit message, heredoc prose or `ssh box '…'` is not a write."""
    import szerep_kapu_iras as iras  # lazy: it imports szerep_kapu, which imports this module lazily
    return iras.hit(root, tool, inp, cwd, [RECEIPTS], trusted=[os.path.join(".mentat", "bin", FINDER)],
                    script_args=True)
