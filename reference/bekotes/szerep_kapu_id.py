"""F-41 "identitás kifelé" for szerep_kapu: the USER's identifier must not go to a third party.

decide(tool, inp, cwd, ids, allow) -> None | {"azonosito": [...], "cel": [...]}
needs(root, tool, inp, cwd)        -> the same, with the identifiers and the allowlist loaded
save(root)                         SessionStart: the identifiers into .mentat/identitas.json (0600)
protected(tool, inp, cwd, root)    -> path: the gate's own files are written (always deny)

A network-writing call (szerep_id_halozat) whose text, or a local file it reads, holds one of
the USER's identifiers (szerep_id: git e-mail, the Claude account's e-mail, the gh e-mail,
~/.mentat/identitas.txt; plain, URL-encoded, base64, hashed), with a target that is not a first
party (szerep_id_elsofel: own domains, GitHub incl. commit/push, the own Google account,
Anthropic, Cloudflare, localhost, ~/.mentat/elsofel.txt). An unknown target is not a first party.
The gh call needs the network, so the list is built at SessionStart; PreToolUse only reads it.
"""
import json
import os
import subprocess

import szerep_id as ident
import szerep_id_elsofel as elsofel
import szerep_id_halozat as halozat

CACHE = os.path.join(".mentat", "identitas.json")
SHARE = os.path.expanduser("~/.mentat/kepessegfa-megosztas.txt")  # what the capability export may show
USER_FILES = (ident.EXTRA, elsofel.FILE, SHARE)


def decide(tool, inp, cwd, ids, allow):
    if tool in elsofel.LOCAL_TOOLS or allow.tool_ok(tool) or not ids.values:
        return None
    out = halozat.outbound(tool, inp, cwd)
    if not out.net:
        return None
    found = ids.find(out.text)
    if not found:
        return None
    third = sorted(h for h in out.hosts if not allow.host_ok(h)) or ([] if out.hosts else ["<ismeretlen cel>"])
    return {"azonosito": found, "cel": third} if third else None


def _ignored(root):
    """The cache holds the USER's addresses: it is written only where git ignores it (CISO #81)."""
    try:
        return subprocess.run(["git", "-C", str(root), "check-ignore", "-q", CACHE],
                              capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def session_start(root):
    """SessionStart: the cache (only if git-ignored), and a word when the first-party list is empty."""
    try:
        if _ignored(root):
            save(root)
        if elsofel._lines(elsofel.FILE):
            return None
        import szerep_id_javaslat
        got = szerep_id_javaslat.suggest(root)
    except Exception:  # noqa: BLE001 - never blocks a session; PreToolUse reads live
        return None
    if not got:
        return None
    # Only a count: no host or IP leaves the machine's own files at session start (0.3.1); the list
    # itself is shown when the suggestion tool is run on purpose.
    return ("F-41: a saját helyeid listája (elsofel.txt a ~/.mentat alatt) üres; %d javasolt sor vár a "
            "FELHASZNÁLÓ jóváhagyására. Mutasd meg neki: `python3 .mentat/bin/bekotes/szerep_id_javaslat.py`, "
            "és csak az igenjével írd be: `… --write <sor> …`." % len(got))


def writes_allowlist(tool, inp):
    """The suggestion tool's --write: the USER approves it (ask), headless deny."""
    cmd = str(inp.get("command", "")) if tool == "Bash" else ""
    return "szerep_id_javaslat" in cmd and "--write" in cmd


def save(root):
    email, _, login = ident._run(["gh", "api", "user", "-q", '[.email // "", .login] | @tsv']).partition("\t")
    ids = ident.Ids(ident.load(extra_dirs=[str(root)], gh=False).values + [email])
    path = os.path.join(str(root), CACHE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"ids": ids.values, "gh_logins": [login] if login else []}, f)
    os.replace(path + ".tmp", path)


def _load(root):
    try:
        with open(os.path.join(str(root), CACHE), encoding="utf-8") as f:
            d = json.load(f)
        ids, logins = (d.get("ids"), d.get("gh_logins", [])) if isinstance(d, dict) else (None, None)
        if not (isinstance(ids, list) and isinstance(logins, list) and all(isinstance(v, str) for v in ids + logins)):
            raise ValueError("odd cache")  # an odd cache counts as none: read live, lose nothing (CISO #89)
        repo = ident._run(["git", "-C", str(root), "config", "user.email"])
        return ident.Ids(ids + [repo] + ident._extra()), logins
    except (OSError, ValueError, AttributeError):
        return ident.load(extra_dirs=[str(root)], gh=False), []


def needs(root, tool, inp, cwd):
    if tool in elsofel.LOCAL_TOOLS or user_gate_active(root):
        return None
    ids, logins = _load(root)
    return decide(tool, inp, cwd, ids, elsofel.Allow.load(ids, gh_logins=logins))


def user_gate_active(root):
    """A verified user-level F-41 gate (settings hook or fleet plugin) runs: see szerep_id_felhasznaloi."""
    import szerep_id_felhasznaloi
    return szerep_id_felhasznaloi.user_gate_active(root)


def allowlist_detail(root, inp):
    """For the USER's question about `--write`: each named line with where it was suggested from."""
    import szerep_id_javaslat
    src = dict(szerep_id_javaslat.suggest(root))
    lines = [w for w in str(inp.get("command", "")).split("--write", 1)[-1].split() if not w.startswith("-")]
    return "; ".join("%s ← %s" % (x, src.get(x, "NEM JAVASOLT, nem kerül be")) for x in lines)


def protected(tool, inp, cwd, root):
    """The identifier cache and the USER's two files: the agent never WRITES them (szerep_kapu_iras:
    real targets only). Reading them, running the brain's tools and mentioning them is free; the
    suggestion tool writes the list only through its own `--write`, which the USER is asked about."""
    import szerep_kapu_iras as iras  # lazy: it imports szerep_kapu
    return iras.hit(root, tool, inp, cwd, [CACHE] + list(USER_FILES))  # as fleet vedett.py decides
