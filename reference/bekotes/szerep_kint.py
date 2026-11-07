"""The working-folder boundary (friction #8): outside(root, tool, inp, cwd, sid) ->
[(path, op, consented)] for each path in the zone the base allowlist does not open.
Zone: HOME, /Users, /home, /root, /tmp, /Volumes, /mnt, $CLAUDE_CONFIG_DIR and all above them
(`find /`), resolved, case-insensitive. Open: the repo; in the ACTIVE config root this project's
folder and plugins|skills|commands|agents; its /tmp/claude-*/<slug>/; TOOLS; a fleet agent's
~/.config/<agent>/; onboarded non-memory sources. Consent (.mentat/engedelyek.json): a file by
inode and op (olvas/ir), a folder for one session, a zone root never. Every tool counts (MCP,
LSP, WebFetch file://); ALLOW and consent never match by lowercase.
"""
import glob
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from szerep_bash import analyse  # noqa: E402
from szerep_engedely import load  # noqa: E402
from szerep_pin import brain_root  # noqa: E402
from szerep_tiltott import sources  # noqa: E402

LEGACY_TOOLS = ("~/src/anytime-engine", "~/src/mentat-ai-bootstrap", "~/src/mentat-admin", "~/fleet-leader")  # < 0.5.0
TOOLS = ("~/src/mentat",) + LEGACY_TOOLS  # the one Mentat clone (0.5.0+)
HOMES = ("/users", "/home", "/root")
SHARED = ("/tmp", "/private/tmp", "/volumes", "/mnt", "/media")  # other sessions' scratch, disks (B-2)
CODE_DIRS = ("plugins", "skills", "commands", "agents")  # product code, not memories
WRITERS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def forms(p):
    """Written and resolved form, case kept: what an ALLOW matches (Codex: no lowercase identity)."""
    p = os.path.expanduser(str(p))
    return {os.path.normpath(p), os.path.realpath(p)}


def under(f, base):
    return f == base or f.startswith(base.rstrip("/") + "/")


def real(p):
    """Resolved and lowercased: what a DENY matches (conservative on case-insensitive disks)."""
    return os.path.realpath(os.path.expanduser(str(p))).lower()


def exact(p):
    return os.path.realpath(os.path.expanduser(str(p)))


def _zone():
    out = set(HOMES) | set(SHARED)
    for v in (os.environ.get("HOME"), os.environ.get("CLAUDE_CONFIG_DIR")):
        if v:
            out |= {f.lower() for f in forms(v)}
    return out


def base_allowed(root):
    root = pathlib.Path(root)
    out = forms(root)
    for t in TOOLS:
        out |= forms(t)
    slugs = {re.sub(r"[^A-Za-z0-9]", "-", f) for f in forms(root)}
    for f in forms(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"):  # the ACTIVE root only (B-3)
        out |= {f + "/projects/" + s for s in slugs} | {f + "/" + d for d in CODE_DIRS}
    for tmp in glob.glob("/tmp/claude-*") + glob.glob("/private/tmp/claude-*"):  # own scratch, task output
        out |= {exact(tmp) + "/" + s for s in slugs}
    try:  # onboarded sources the USER named (memory goes through the filter, never raw)
        out |= {f for k, b, _ in sources(root, brain_root(root)) if k != "memory" for f in forms(root / b)}
    except Exception:  # noqa: BLE001 - a broken bekotes.json only narrows access
        pass
    try:  # a fleet agent's own runtime folder: its bridge (send.mjs) and telegram.env
        agent = json.loads((root / ".claude" / "fleet.json").read_text(encoding="utf-8"))["agent"]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", agent):
            out |= forms("~/.config/" + agent)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return out


def paths(tool, inp, cwd):
    """[(path, "olvas" | "ir")] the call touches, absolute."""
    join = lambda p: os.path.join(cwd, os.path.expanduser(str(p)))  # noqa: E731
    if tool == "Bash":
        r, w = analyse(str(inp.get("command", "")), cwd)
        return [(p, "olvas") for p in r] + [(p, "ir") for p in w]
    if tool in ("Grep", "Glob", "LS"):
        out = [join(inp.get("path") or cwd)]
        pat = str(inp.get("pattern", "")) if tool == "Glob" else ""
        if pat.startswith(("/", "~")):
            out.append(join(re.split(r"[*?\[{]", pat)[0] or "/"))
        return [(p, "olvas") for p in out]
    p = inp.get("file_path") or inp.get("notebook_path")
    if tool in ("Read", "NotebookRead") or tool in WRITERS:
        return [(join(p), "ir" if tool in WRITERS else "olvas")] if p else []
    return [(join(s), "olvas") for s in _pathlike(inp)]  # any other tool (MCP, LSP, WebFetch file://…)


def _pathlike(v):
    if isinstance(v, dict):
        return [s for x in v.values() for s in _pathlike(x)]
    if isinstance(v, list):
        return [s for x in v for s in _pathlike(x)]
    if isinstance(v, str) and v.startswith(("/", "~", "file://")):
        return [v[7:] if v.startswith("file://") else v]
    return []


def is_root(path):
    """A zone root or above it (HOME, /Users/<x>, a config root, /): never a consent (B-1)."""
    f = real(path)
    homes = {z for z in _zone() if z not in HOMES} | {h + "/" + f.split("/")[2] for h in HOMES
                                                      if f.count("/") >= 2 and under(f, h)}
    return any(under(z, f) for z in _zone() | homes)


def _same(path, e):
    """The approved file itself: by device and inode when both exist, else the exact path."""
    try:
        st = os.stat(path)
        if "ino" in e:
            return (st.st_dev, st.st_ino) == (e.get("dev"), e["ino"])
    except OSError:
        pass
    return exact(path) == exact(e["ut"])


def _consented(path, op, entries, sid):
    for e in entries:
        if e.get("muvelet") != op:
            continue
        if e.get("session") is None and _same(path, e):  # a file, exactly
            return True
        if e.get("session") and e["session"] == sid and op == "olvas" and under(exact(path), exact(e["ut"])):
            return True  # a folder sweep, this session only
    return False


def outside(root, tool, inp, cwd, sid=None):
    """[(path, op, consented)] in the zone that the base allowlist does not open."""
    ok, zone, entries = base_allowed(root), _zone(), load(root)
    out = []
    for p, op in paths(tool, inp, cwd):
        f = real(p)
        if any(under(exact(p), a) for a in ok) or not any(under(f, z) or under(z, f) for z in zone):
            continue
        out.append((p, op, _consented(p, op, entries, sid)))
    return out
