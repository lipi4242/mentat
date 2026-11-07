"""The protected paths of the identity gate (F-41), resolved: what is protected, what is a user
Claude settings file, and whether interpreter code names one and writes (used by vedett.py).
The gate's code is protected where it really runs from (OWN: the plugin cache for the plugin) and the
whole ~/.mentat/bin/ (the Mac gate's and the nemakad hook's code, with its checksums); a same-named
folder elsewhere (a repo's own .mentat/bin) is not."""
import fnmatch
import os
import re

FILES = ("identitas.txt", "elsofel.txt", "identitas-cache.json")
WRITE_CODE = re.compile(  # a write call, not any word: str.replace / .copy() on data are reads
    r"open\([^)]*,\s*(mode\s*=\s*)?['\"][rbt]*[wax+]|\.open\(\s*['\"][rbt]*[wax+]|\.write_(text|bytes)\(|"
    r"\bos\.(remove|unlink|rename|replace|rmdir|removedirs|chmod|truncate|symlink|link)\(|"
    r"\bshutil\.(rmtree|move|copy\w*)\(|\.(unlink|rename|rmdir|touch|symlink_to)\(|"
    r"\bfs\.\w*(write|append|unlink|rm|rename|copy)\w*\(|\bFile\.(write|delete)|\bunlink\(|\brmtree\(")
STRINGS = re.compile(r"'([^']*)'|\"([^\"]*)\"|(~/\S+)")


def _home():
    return os.path.realpath(os.path.expanduser("~"))


def _resolve(p, cwd):
    p = os.path.expanduser(p.replace("${HOME}", "~").replace("$HOME", "~"))
    return os.path.realpath(os.path.join(cwd or os.getcwd(), p))


OWN = os.path.dirname(os.path.realpath(__file__))  # the gate's own code, wherever it runs from


def _targets():
    m = os.path.join(_home(), ".mentat")
    # A teljes ~/.mentat/bin/: a kapu ÉS a nemakad kódja, a jegyzékekkel (CISO, 10-24); a
    # ~/.mentat/titkok/: a titok-leltár, a jóváhagyások és a nyugták (csak `fleet secrets` írja, H5)
    return [os.path.join(m, f) for f in FILES], [os.path.join(m, "bin"), os.path.join(m, "titkok"), OWN]


def is_protected(t, ancestors=False):
    files, codes = _targets()
    every = files + codes
    under = [x for x in every if ancestors and x.startswith(t.rstrip(os.sep) + os.sep)]
    globbed = any(c in t for c in "*?[") and any(_glob(x, t) for x in every)
    inside = any(t == c or t.startswith(c + os.sep) for c in codes)
    if t in files or inside or under or globbed:
        return t
    return None


def _glob(name, pattern):
    """A shell glob match; a pattern fnmatch cannot compile (`[z-a]`) matches nothing, as in the shell."""
    try:
        return fnmatch.fnmatch(name, pattern)
    except re.error:
        return False


def is_settings(t):
    d, name = os.path.split(t)
    if name not in ("settings.json", "settings.local.json"):
        return False
    roots = [os.path.realpath(os.environ["CLAUDE_CONFIG_DIR"])] if os.environ.get("CLAUDE_CONFIG_DIR") else []
    return d in roots or (os.path.dirname(d) == _home() and os.path.basename(d).startswith(".claude"))


def _hit(path, cwd, ancestors=False):
    t = _resolve(path, cwd)
    if is_protected(t, ancestors):
        return t
    return "beallitas:" + t if is_settings(t) else None


def _code(text, cwd):
    """Interpreter code: a protected file named in it, and a write."""
    if not WRITE_CODE.search(text):
        return None
    for m in STRINGS.finditer(text):
        lit = next(g for g in m.groups() if g is not None)
        if "\n" in lit or not ("/" in lit or lit.startswith("~")):
            continue  # not a path: data, a pattern, a code fragment
        hit = _hit(lit, cwd)
        if hit:
            return hit
    if ".mentat" in text and any(f in text for f in FILES + ("identitas-kapu",)):
        return os.path.join(_home(), ".mentat")
    return None


def _copy(name, paths, args, cwd):
    """cp/mv/ln/install/scp/rsync: the target is written (and, if it is a folder, the source's name in
    it); a copied source is only read, a moved one is gone (its ancestors count too)."""
    *srcs, dest = paths
    if name == "mv":
        hit = next((h for h in (_hit(p, cwd, True) for p in srcs) if h), None)
        if hit:
            return hit
    rec = name in ("cp", "rsync", "scp") and any(
        a in ("--recursive", "--archive", "--delete") or (a[:1] == "-" and a[1:2] != "-" and set("rRa") & set(a[1:]))
        for a in args)  # a recursive copy onto an ancestor can overwrite the protected file (ciso)
    hit = _hit(dest, cwd, rec)
    if hit:
        return hit
    d = os.path.expanduser(dest.replace("${HOME}", "~").replace("$HOME", "~"))
    if dest.endswith("/") or os.path.isdir(os.path.join(cwd or os.getcwd(), d)):
        return next((h for h in (_hit(os.path.join(dest, os.path.basename(p.rstrip("/"))), cwd) for p in srcs) if h), None)
    return None


def sed_files(args):
    """The files of `sed -i` / `perl -pi`: not the options, not a script (-e X, -f X, or the first word)."""
    out, skip, script = [], False, any(a in ("-e", "-f") or a.startswith(("-e", "-f")) for a in args)
    for a in args:
        if skip:
            skip = False
        elif a in ("-e", "-f"):
            skip = True
        elif a and not a.startswith("-"):
            out.append(a)
    return out if script else out[1:]
