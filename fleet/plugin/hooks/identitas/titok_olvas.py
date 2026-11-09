"""Melyik Bash-parancs OLVAS titkot (a titok-kapu, titok_kapu.py). A vedett.py szóelemzője,
de olvasásra: átirányítás, cp/ln/rsync/tar, értelmező -c/heredoc, $(…)/`…`/<(…), for-ciklus,
xargs, plusz a környezet kiírása (env, printenv, ps e, show-environment, /proc/*/environ).

    bash(cmd, cwd, lel) -> ok-szöveg | None

A korábban adott értéket behelyettesíti (`F=út; cat "$F"`), a `dd if=` forrását is nézi; páratlan
idézőjelnél (`echo don't`) szóközös bontással dönt, nem tilt magától. Ami csak listáz (ls, stat, fleet …), szabad; de ha ugyanabban a sorban egy olvasó parancs
változón ($f) vagy xargs-on át kapja a listázott titkot, az tilt.
"""
import os
import re

from bash_szavak import subst, tokens
from titok_kod import PROC, code, envdump, search_args
from titok_minta import resolve, secret
from vedett import HEREDOC, INTERP, PREFIX, SEP, SHELLS

LISTERS = {"ls", "stat", "test", "[", "echo", "printf", "realpath", "readlink", "basename", "dirname", "du",
           "wc", "file", "find", "for", "tree"}
NOREAD = {"fleet", "mkdir", "true", "false", "cd", "pwd", "which", "type", "chmod", "touch", "date", "sleep",
          "exit", "unset", "trap", "wait", "kill", "pkill", "jobs"}
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "}", "done", "fi"}
GIT_SAFE = {"add", "rm", "mv", "status", "commit", "push", "pull", "fetch", "checkout", "switch", "branch",
            "merge", "rebase", "ls-files", "check-ignore", "worktree", "stash", "tag", "remote", "config",
            "init", "clone", "reset", "restore", "cherry-pick", "revert", "rev-parse", "log"}
RECURSIVE = {"find", "rsync", "tar", "zip", "rg", "ag", "7z", "tree", "scp"}
FLAG_REC = {"grep", "egrep", "fgrep", "cp", "ls", "chmod", "zgrep"}


def _subs(cmd):
    """$(…), <(…), >(…) és `…` belseje, egymásba ágyazva is."""
    out, i = [], 0
    while i < len(cmd):
        if cmd[i] in "$<>" and cmd[i + 1:i + 2] == "(":
            depth, j = 1, i + 2
            while j < len(cmd) and depth:
                depth += {"(": 1, ")": -1}.get(cmd[j], 0)
                j += 1
            out.append(cmd[i + 2:j - 1])
            i = j
        elif cmd[i] == "`":
            j = cmd.find("`", i + 1)
            out.append(cmd[i + 1:j] if j > 0 else cmd[i + 1:])
            i = j + 1 if j > 0 else len(cmd)
        else:
            i += 1
    return out


def _heredoc(line):
    """Az első HEREDOC-találat, aminek a `<<`-ja idézőjelen kívül áll (a shell szemében operátor): az
    idézőjelbe tett `"<<E"` nem nyit törzset, különben a következő, valóban futó sorok kimaradnának."""
    for m in HEREDOC.finditer(line):
        pre = line[:m.start()]
        if pre.endswith("<") or pre.count("((") > pre.count("))") or re.match(r"\s*let\s", line):
            continue  # here-string (`<<<`) vagy aritmetikai eltolás (`$((1<<2))`), nem heredoc
        if _unquoted(line, m.start()):
            return m
    return None


def _unquoted(line, pos):
    q, i = None, 0
    while i < pos:
        c = line[i]
        if c == "\\" and q != "'":
            i += 2
            continue
        if q is None and c == "#" and (i == 0 or line[i - 1] in " \t;&|()"):
            return False  # megjegyzés: a benne álló `<<` nem nyit heredocot
        if q is None and c in "'\"":
            q = c
        elif c == q:
            q = None
        i += 1
    return q is None and i == pos


def _literal_heredocs_out(cmd):
    """A parancs az idézett határolójú heredoc-törzsek nélkül (`<<'E'`): azokban a `…` és a $(…) szó
    szerinti szöveg, nem fut (11-08: egy markdown-jegyzet backtickjei parancsnak számítottak, és a
    bennük lévő `*` tiltott). Az idézetlen (`<<E`) törzsben a shell TÉNYLEG lefuttatja őket: az marad."""
    lines, kept, i = cmd.split("\n"), [], 0
    while i < len(lines):
        kept.append(lines[i])
        m = _heredoc(lines[i])
        if m:
            j = i + 1
            while j < len(lines) and lines[j].strip() != m.group(2):
                j += 1
            if not m.group(1):
                kept.extend(lines[i + 1:j])
            i = j
        i += 1
    return "\n".join(kept)


def _rec(name, args):
    return name in RECURSIVE or name in FLAG_REC and any(
        a in ("--recursive", "--archive") or (a[:1] == "-" and a[1:2] != "-" and set("rRa") & set(a[1:]))
        for a in args)


def _excludes(name, args):
    """A parancs saját kizárásai (csak sima név, glob nem): amit kihagy, azt nem olvassa, ezért annak
    a találata nem tilt (11-07). Jelölés a titok_minta._skipped szerint: `X` = X nevű mappa bárhol
    (grep --exclude-dir, find -name X -prune), `=X` = X nevű FÁJL bárhol (grep --exclude, find -not
    -name), `./X` = pontosan ez az út, `./X/` = ami alatta van (find -path)."""
    if name == "find":
        return _find_excludes(args)
    if name not in ("grep", "egrep", "fgrep", "zgrep", "rg"):
        return ()
    out = set()
    for i, a in enumerate(args):
        if a.startswith(("--exclude-dir=", "--exclude=")):
            out.add(("" if a.startswith("--exclude-dir=") else "=") + a.split("=", 1)[1].strip("/"))
        elif a in ("--exclude-dir", "--exclude") and i + 1 < len(args):
            out.add(("" if a == "--exclude-dir" else "=") + args[i + 1].strip("/"))
    return tuple(x for x in out if x.strip("=") and not re.search(r"[*?\[/]", x))


def _find_excludes(args):
    """find: a tagadott (`-not`/`!`, páratlanszor) `-name X` → `=X`, `-path ./X` → `./X`,
    `-path ./X/*` → `./X/`; a kifejezés elején álló `-path ./X -prune -o …` → `./X` + `./X/`,
    `-name X -prune -o …` → `X`. VAGY, zárójel és az első akció UTÁNI rész mellett nincs kizárás
    (`-not -path ./.env -o -exec cat {} +`, `-print -not -name X` X-et is olvassa/kiírja)."""
    expr = args[next((i for i, a in enumerate(args) if a[:1] in ("-", "!", "(")), len(args)):]
    root = _find_roots(args) == ["."]
    out = set()
    depth = any(a in ("-depth", "-d", "-delete") for a in args)  # -depth mellett a -prune hatástalan
    if not depth and expr[:1] in (["-path"], ["-wholename"], ["-name"]) and expr[2:4] in (["-prune", "-o"],
                                                                                          ["-prune", "-or"]):
        rest = expr[4:]
        if any(a.startswith(("-exec", "-ok", "-print", "-fprint", "-ls", "-fls")) for a in rest):
            out.update(_find_tok(expr[0], expr[1], root, prune=True))  # akció nélkül az implicit -print
        expr = rest                                                       # a prune-olt utat is kiírja
    if any(a in ("-o", "-or", ",", "(", ")", "\\(", "\\)") for a in expr):
        return tuple(out)
    act = next((i for i, a in enumerate(expr) if a.startswith(("-exec", "-ok", "-print", "-fprint", "-ls",
                                                               "-delete", "-fls"))), len(expr))
    expr = expr[:act]
    for i, a in enumerate(expr[:-1]):
        neg = 0
        while neg < i and expr[i - 1 - neg] in ("-not", "!"):
            neg += 1
        if a in ("-path", "-wholename", "-name") and neg % 2:
            out.update(_find_tok(a, expr[i + 1], root))
    return tuple(out)


def _find_tok(pred, raw, root, prune=False):
    if pred == "-name":
        return () if re.search(r"[*?\[/]", raw) or not raw else ((raw,) if prune else ("=" + raw,))
    if not (root and raw.startswith("./")):
        return ()  # a -path az egész útra illeszt: csak a `.` gyökér alatti `./X` értelmezhető
    below = raw.endswith("/*")
    if not below and (raw.endswith("/") or "//" in raw):
        return ()  # `-path ./X/` a ./X-re nem illik: ne vegyük kizárásnak
    v = re.sub(r"/\*$", "", raw[2:])
    if v != v.strip("/"):
        return ()
    if not v or re.search(r"[*?\[]", v):
        return ()
    if prune:  # `-path ./X/* -prune`: X maga kiíródik, csak ami alatta van, az nem
        return ("./" + v + "/",) if below else ("./" + v, "./" + v + "/")
    return ("./" + v + "/",) if below else ("./" + v,)


def _find_roots(args):
    """A find olvasott gyökerei: az első kifejezés-elem (-x, !, () előtti szavak; alapból `.`)."""
    roots = []
    for a in args:
        if a[:1] in ("-", "!", "("):
            break
        roots.append(a)
    return roots or ["."]


def _hint(why):
    """Végrehajtható kizárás a mappa-találathoz (a `grep -r … .`-tal azonos bánásmód)."""
    m = re.search(r"\(mappa: ([^)]+)\)|a mappában \(([^)]+)\)", why)
    x = m and (m.group(1) or m.group(2))
    if not x:
        return why
    return ("%s — zárd ki: `find … -not -path './%s'` (mappánál './%s/*'), `grep -r --exclude=%s` / "
            "`--exclude-dir=%s`, vagy adj meg konkrét útvonalat" % (why, x, x, x, x))


def _at(p, state):
    """A `cd X && …` utáni relatív út a tényleges mappához kötve (a tulajdonjogot továbbra is a hook
    cwd-je / a session projektje adja, nem a `cd`)."""
    d = state.get("cwd")
    return os.path.join(d, p) if d and not p.startswith(("/", "~")) else p


def _chdir(name, args, cwd, state):
    """cd/pushd/popd/`cd -` követése; amit nem tudunk követni (`cd $X`, üres popd), az „elveszett"
    mappa: utána a relatív út olvasása tilt (Codex 11-08: `pushd A; pushd B; popd; cat x` = A/x)."""
    here, stack = state.get("cwd") or cwd, state.setdefault("dirs", [])
    dest = next((a for a in args if not a.startswith("-") or a == "-"), None)
    if name == "popd":
        new = stack.pop() if stack else None
    elif dest == "-":
        new = state.get("oldpwd")
    else:
        new = resolve(_at(dest or "~", state), cwd) if not state.get("lost") or (dest or "~").startswith(("/", "~")) else None
        if name == "pushd" and new:
            stack.append(here)
    state["oldpwd"], state["cwd"], state["lost"] = here, new, new is None
    cands = state.setdefault("cands", [cwd])
    rel = name != "popd" and dest not in (None, "-") and not dest.startswith(("/", "~"))
    cdpath = [e for e in os.environ.get("CDPATH", "").split(":") if e]  # bash a CDPATH-ból is választ
    extra = [resolve(os.path.join(c, dest), cwd) for c in list(cands) + cdpath] if rel else []
    for d in [new] + extra:  # a cd sikertelen, feltételes, alhéjas vagy háttérben futó is lehet:
        if d and d not in cands:  # a relatív cél MINDEN eddigi lehetséges mappából indulhat
            cands.append(d)


def _rel_secret(p, cwd, lel, state, rec=False, skip=()):
    """Relatív út: MINDEN lehetséges mappához mérve (a hook cwd-je és minden cd-cél), bármelyik
    találat tilt — a cd nem biztos, hogy lefutott, sikerült, vagy a szülő shellt váltotta (CISO B-01)."""
    if p.startswith(("/", "~")) or not state.get("cands"):
        return secret(_at(p, state), cwd, lel, rec, skip)
    for d in state["cands"]:
        why = secret(os.path.join(d, p), cwd, lel, rec, skip)
        if why:
            return why
    return None


def _paths(args, base=None):
    for a in args:
        if a.startswith(("--exclude", "--include")):  # szűrő, nem olvasott út
            continue
        if a.startswith("--") and "=" in a:
            a = a.split("=", 1)[1]
        elif a.startswith("-") or re.match(r"^\w+=", a):
            continue
        a = a.lstrip("@")
        bases = base if isinstance(base, (list, tuple)) else [base or ""]
        if a and ("/" in a or a.startswith((".", "~")) or "*" in a or
                  any(os.path.lexists(os.path.join(b or "", a)) for b in bases)):
            yield a


def _command(words, cwd, lel, state):
    while words and (words[0] in KEYWORDS or re.match(r"^\w+=", words[0])):
        words = words[1:]
    if not words:
        return None
    name, args = os.path.basename(words[0]), words[1:]
    if name in ("cd", "pushd", "popd"):
        _chdir(name, args, cwd, state)
        return None
    if name == "dd":
        args = [a[3:] for a in args if a.startswith("if=")]
    args = search_args(name, args)  # grep MINTA nem út
    why = envdump(name, args)
    if why:
        return why
    if name == "xargs":
        state["var_reader"] = True
    if name in PREFIX and args:
        return _command(args, cwd, lel, state)
    if name in ("ssh", "mosh"):
        return None
    if name in SHELLS | {"eval"}:
        body = args[args.index("-c") + 1] if "-c" in args and args.index("-c") + 1 < len(args) else \
            " ".join(args) if name == "eval" else None
        if body is not None:
            return bash(body, cwd, lel)
    if name in INTERP or name.startswith("python"):
        flag = next((i for i, a in enumerate(args) if a in ("-c", "-e")), None)
        if flag is not None and flag + 1 < len(args):
            return code(args[flag + 1], cwd, lel)
    if name == "git":
        sub = next((a for i, a in enumerate(args) if not a.startswith("-") and (i == 0 or args[i - 1] != "-C")), "")
        if sub in GIT_SAFE and not (sub == "log" and any(a in ("-p", "--patch") or a.startswith("-L") for a in args)):
            return None
    if name in NOREAD:
        return None
    rec = _rec(name, args)
    skip = _excludes(name, args)
    lister = name in LISTERS and "-exec" not in args and "-execdir" not in args
    lost = next((a for a in args if a[:1] not in ("-", "/", "~")), None) if state.get("lost") and not lister else None
    if lost:
        return "relatív út egy nem követhető `cd`/`popd` után: %s" % lost
    targs = _find_roots(args) if name == "find" else args[2:] if name == "for" else args
    for p in _paths(targs, state.get("cands") or [state.get("cwd") or cwd]):
        why = _rel_secret(p, cwd, lel, state, rec, skip)
        if why and not lister:
            return _hint("%s: %s" % (why, os.path.basename(p.rstrip("/")) or p))
        if why:
            state["listed"] = state.get("listed") or "%s: %s" % (why, os.path.basename(p.rstrip("/")))
    if not lister and (name == "xargs" or any("$" in a for a in args)):
        state["var_reader"] = True
    return None


def bash(cmd, cwd, lel, state=None):
    state = {} if state is None else state
    if re.search(r"\bCDPATH\s*=", cmd):
        state["lost"] = True  # a parancsban állított CDPATH: a cd célja nem követhető
    cmd = subst(cmd)  # `F=~/.config/x/x.env; cat "$F"`
    if PROC.search(cmd):
        return "környezet kiírása (/proc/*/environ)"
    for inner in _subs(_literal_heredocs_out(cmd)):
        why = bash(inner, cwd, lel, state)
        if why:
            return why
    lines, kept, i = cmd.split("\n"), [], 0
    while i < len(lines):
        kept.append(lines[i])
        m = _heredoc(lines[i])
        if m:
            first = os.path.basename((lines[i].split() or [""])[0])
            j = i + 1
            while j < len(lines) and lines[j].strip() != m.group(2):
                j += 1
            body = "\n".join(lines[i + 1:j])
            why = code(body, cwd, lel) if first in INTERP or first.startswith("python") else \
                bash(body, cwd, lel, state) if first in SHELLS else None
            if why:
                return why
            i = j
        i += 1
    toks = tokens(" ; ".join(kept))  # páratlan idézőjel: szóközös bontás, csak valódi találat tilt
    words, k = [], 0
    while k <= len(toks):
        tok = toks[k] if k < len(toks) else ";"
        if tok[:1] in "<>" and re.fullmatch(r"[<>&|()]+", tok) or tok in ("&>", "&>>"):  # "<<'E'" szó, nem operátor
            target = toks[k + 1] if k + 1 < len(toks) and not tok.endswith("&") and tok not in ("<<", "<<<") else None
            if target and state.get("lost") and target[:1] not in ("/", "~", "&", "("):
                return "átirányítás egy nem követhető `cd`/`popd` után: %s" % target
            why = _rel_secret(target, cwd, lel, state) if target and not target.startswith("(") else None
            if why:
                return "%s: %s" % (why, os.path.basename(target))
            k += 2
        elif tok in SEP or re.fullmatch(r"[;&|()]+", tok):  # a shlex összevonja: `);`, `)|`
            why = _command(words, cwd, lel, state) if words else None
            if why:
                return why
            words, k = [], k + 1
        else:
            words.append(tok)
            k += 1
    if state.get("listed") and state.get("var_reader"):
        return _hint("listázott titok egy olvasó parancsnak átadva (%s)" % state["listed"])
    return None
