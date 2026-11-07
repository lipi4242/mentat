"""`klon`: clone a repo source so its forbidden files never land on disk.

    git clone --no-checkout [--filter=blob:none]  (the filter only for remote URLs)
    git config core.ignorecase true   (sparse matching is case-sensitive otherwise)
    git sparse-checkout set --no-cone '/*' '!**/<glob>' ...   (one per tiltott glob)
    git checkout

Forbidden blobs stay in history (the inventory still names them) but are never
written to the working tree. Afterwards the tree is verified with our own
(case-insensitive) matcher; a leftover is reported by name, never by content.
"""
import json
import os
import pathlib
import re
import subprocess

import fajlszuro as fs
import hely
import leltar as lt


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise hely.HelyError("git %s: %s" % (args[0] if args[0] != "-C" else args[2],
                                             (r.stderr.strip().splitlines() or ["hiba"])[-1]))
    return r.stdout


SCP = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9.][A-Za-z0-9.-]*:[^-\s][^\s]*$")


def local_path(src):
    """A local `from` written as ~/… (the documented form) expanded; '..' is never accepted."""
    if ".." in src.replace("\\", "/").split("/"):
        return None
    return os.path.expanduser(src) if src.startswith("~/") else src


def valid_from(src):
    """https://, ssh://, git@host:path, or an existing local directory (~/…); nothing else."""
    if not isinstance(src, str) or not src or src.startswith("-") or "::" in src or any(c.isspace() for c in src):
        return False
    if src.startswith(("https://", "ssh://")):
        return True
    local = local_path(src)
    return bool(SCP.match(src)) or bool(local and os.path.isdir(local))


def patterns(globs):
    out = ["/*"]
    for g in globs:
        g = g.lstrip("/")
        out.append("!" + (g if g.startswith("**/") else "**/" + g))
    return out


def leftovers(dest, globs):
    found = []
    for d, dirs, files in os.walk(dest):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            rel = (pathlib.Path(d) / f).relative_to(dest).as_posix()
            if fs.tiltott(rel, globs):
                found.append(rel)
    return sorted(found)


def run(a):
    cfg = json.loads(pathlib.Path(a.config).read_text(encoding="utf-8"))
    src = next((s for s in cfg.get("sources") or [] if isinstance(s, dict) and s.get("name") == a.name), None)
    if not src or src.get("kind") != "repo":
        raise hely.HelyError("nincs ilyen repó-forrás a configban: %s" % a.name)
    globs = fs.globs_of(src)
    dest = lt.resolve(a.repo, a.dest or src.get("path") or "")
    if dest.exists() and any(dest.iterdir()):
        raise hely.HelyError("a cél nem üres: %s" % dest)
    if not valid_from(a.from_):
        raise hely.HelyError("érvénytelen --from (csak https://, ssh://, git@host:útvonal vagy létező helyi mappa "
                             "~/…-ként; '..' tilos)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_addr = local_path(a.from_) if os.path.isdir(local_path(a.from_) or "") else a.from_
    local = src_addr != a.from_ or os.path.isdir(a.from_)
    try:
        _git("clone", "-q", "--no-checkout", *([] if local else ["--filter=blob:none"]), "--", src_addr, str(dest))
    except hely.HelyError:  # git's message may quote the address (host, port, token): never echo it
        raise hely.HelyError("git clone sikertelen (cím, hálózat vagy jogosultság) — ellenőrizd a forrás from-ját")
    # sparse patterns follow core.ignorecase: on a case-sensitive filesystem (Linux) git sets it
    # false, and Ugyfelek/Private.json would slip past !**/ugyfelek/private.json
    _git("-C", str(dest), "config", "core.ignorecase", "true")
    _git("-C", str(dest), "sparse-checkout", "set", "--no-cone", *patterns(globs))
    _git("-C", str(dest), "checkout", "-q")
    left = leftovers(dest, globs)
    if left:
        print("tiltott fájl a munkafában (töröld, és jelezd): %s" % ", ".join(left))
        return 1
    print("klón: %s (%d tiltott minta kizárva)" % (a.dest or src.get("path"), len(globs)))
    return 0
