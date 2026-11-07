"""Ágens-határ: amit egy Claude-session egy MÁSIK ágens nevében nem tehet (H5, 2026-10-29).

A titok-kapu hívja, ugyanabban a PreToolUse hookban; csak tilt. MINDIG tilos: más ágens élő
checkoutjában a szabályfájl (AGENTS.md, CLAUDE.md, .claude/rules, .claude/settings*) írása a fő ágon,
és a systemd user-unitok (~/.config/systemd/user) kézi írása. CSAK ÖSSZEOLVASZTÁS-MÓDBAN (a
`fleet secrets merge-mode` jelzője, hatar_jel.py) tilos: helyi `tmux send-keys`, és más ágens kódjának
futtatása kifelé ható paranccsal (`--dry-run` nélkül). „Más ágens": a legközelebbi git-gyökér
AGENTS.md / CLAUDE.md / mentat.json fájllal, amely nem tartalmazza a session saját könyvtárát.

Ez sebességcsökkentő küszöb, nem határ: szkriptfájl, értelmező, futás közben összerakott parancs
átmegy rajta (HATAR-KORLATOK.md). A valódi kontroll az állapot-ellenőrzés: Rilí kézi merge-észlelése,
a doctor unit-eltérése, a registry git-története.
"""
import os
import re

import bash_szavak as S
import hatar_jel as J

RULE_FILES = re.compile(r"^(AGENTS\.md|CLAUDE\.md|\.claude/rules/.+|\.claude/settings[^/]*\.json)$")
MARKERS = ("AGENTS.md", "CLAUDE.md", "mentat.json")
OUTWARD = re.compile(r"send|k[uü]ld|e-?mail|\bmail|level|posta|smtp|notify|telegram|[uü]zen|megh[ií]v|invite",
                     re.I)
TESTS = re.compile(r"\b(unittest|pytest)\b")
UNIT_EDIT = re.compile(r"\bsystemctl\b[^|;&]*\s(edit|link|revert)\b")
DRY = re.compile(r"(^|\s)--dry-run\b")
TMUX = re.compile(r"\btmux\b[^|;&]*\b(send-keys|send|paste-buffer|pasteb)\b")
HELP = ("Más ágens nevében nem lépsz: a szabályai PR-ral és a tulajdonos 👍-ével változnak, a unitjait a "
        "`fleet install` írja, és amit kifelé kell tenni, azt `fleet ask <fogadó>`-val tőle kéred.")


def home():
    return os.path.realpath(os.path.expanduser("~"))


def _abs(p, cwd):
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))


def agent_root(p):
    d = p if os.path.isdir(p) else os.path.dirname(p)
    while d and d != os.sep:
        if os.path.isdir(os.path.join(d, ".git")) and any(os.path.exists(os.path.join(d, m)) for m in MARKERS):
            return d
        d = os.path.dirname(d)
    return None


def _inside(p, root):
    return p == root or p.startswith(root.rstrip(os.sep) + os.sep)


def foreign(p, cwd):
    """A p egy másik ágens checkoutjában van-e (a gyökér, vagy None)."""
    r = agent_root(os.path.realpath(p))  # mindkét oldal valódi út (macOS: /var → /private/var)
    return r if r and not _inside(os.path.realpath(cwd), r) else None


def _on_default_branch(root):
    try:
        with open(os.path.join(root, ".git", "HEAD")) as f:
            head = f.read().strip()
    except OSError:
        return True
    return head in ("ref: refs/heads/main", "ref: refs/heads/master") or not head.startswith("ref:")


def _units_dir():
    return os.path.join(home(), ".config", "systemd", "user")


def file_write(p, cwd):
    a = _abs(p, cwd)
    if _inside(a, _units_dir()):
        return "kézzel írt systemd-unit (%s): a flotta írja, `fleet install <ágens>`" % os.path.basename(a)
    r = foreign(a, own_dir(cwd))
    if r and RULE_FILES.match(os.path.relpath(a, r)) and _on_default_branch(r):
        return "másik ágens szabályfájlja a fő ágon (%s)" % os.path.relpath(a, home())
    return None


def _paths(cmd, cwd):
    """Út-jelöltek: a szavak a tényleges (cd utáni) cwd-hez mérve, plusz minden abszolút út a szövegben."""
    out = [_abs(w, c) for words, c in S.segments(cmd, cwd) for w in words if not w.startswith("-")]
    out += [c for _w, c in S.segments(cmd, cwd)]
    return out + [_abs(p, cwd) for p in S.literals(cmd)]


#: csak olvasó / git parancsok: bennük a „send" vagy „email" szó keresőkifejezés, nem küldés
READERS = re.compile(r"(git|cd|grep|egrep|rg|cat|head|tail|less|ls|find|wc|echo|printf|sort|uniq|stat|"
                     r"file|diff|tree|sed\s+-n|awk)\b")


def _no_exec(cmd):
    """Minden parancsszakasz csak olvas vagy git (pl. `git -c user.email=… commit`, `grep -rn send`)."""
    if "<<" in cmd or "$(" in cmd or "`" in cmd:
        return False
    segs = [x.strip() for x in re.split(r"&&|\|\||;|\||\n", cmd) if x.strip()]
    return bool(segs) and all(READERS.match(x) and not re.match(r"sed\b[^|;&]*\s-i", x) for x in segs)


def _local_tmux(cmd, cwd):
    """`tmux send-keys` ezen a gépen; az `ssh <host> "tmux …"` a távoli gépen fut (operátori kibillentés)."""
    return any(os.path.basename(w[0]) not in ("ssh", "mosh") and TMUX.search(" ".join(w))
               for w, _c in S.segments(cmd, cwd))


def own_dir(cwd):
    """A session saját checkoutja: a CLAUDE_PROJECT_DIR (a `cd` nem viszi el), különben a cwd."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or cwd


def bash(cmd, cwd, merge=False):
    cmd = S.subst(cmd)
    own = own_dir(cwd)
    if UNIT_EDIT.search(cmd):
        return "systemd-unit kézi szerkesztése: `fleet install <ágens>`"
    for a in S.targets(cmd, cwd):
        if _inside(a, _units_dir()):
            return "systemd-unit kézi írása: `fleet install <ágens>`"
        r = foreign(a, own)
        if r and RULE_FILES.match(os.path.relpath(a, r)) and _on_default_branch(r):
            return "másik ágens szabályfájlja a fő ágon (%s)" % os.path.relpath(a, home())
    if not merge:
        return None
    if _local_tmux(cmd, cwd):
        return "gépelés egy tmux-ablakba (a fogadót `fleet ask`-kal éred el)"
    if OUTWARD.search(cmd) and not DRY.search(cmd) and not TESTS.search(cmd) and not _no_exec(cmd):
        for a in _paths(cmd, cwd):
            r = foreign(a, own)
            if r:
                return "kifelé ható parancs %s kódjával (azt ő teszi)" % os.path.basename(r)
    return None


def decide(tool, inp, cwd, merge=None):
    """merge: él-e az összeolvasztás-mód (None = a jelzőből, hatar_jel.aktiv())."""
    if tool in ("Edit", "MultiEdit", "Write"):
        return file_write(str(inp.get("file_path") or ""), cwd) if inp.get("file_path") else None
    if tool == "NotebookEdit":
        return file_write(str(inp.get("notebook_path") or ""), cwd) if inp.get("notebook_path") else None
    if tool == "Bash":
        return bash(str(inp.get("command", "")), cwd, J.aktiv() if merge is None else merge)
    return None
