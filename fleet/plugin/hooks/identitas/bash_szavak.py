"""Bash-szöveg szavakra bontása az ágens-határnak és a titok-kapunak (CISO Q5/5. pont, 2026-10-29).

    tokens(text)          shlex (punctuation_chars); páratlan idézőjelnél szóközös bontás — a ValueError
                          önmagában nem tilthat (`echo don't`)
    subst(cmd)            a parancsban korábban adott értékek behelyettesítése (`F=út; cat "$F"`)
    heredocs(cmd)         (a heredoc-törzsek nélküli szöveg, [(első szó, törzs)])
    segments(cmd, cwd)    [(szavak, tényleges cwd)]; a `cd X` / `pushd X` a későbbi szakaszok cwd-je
    targets(cmd, cwd)     amit a parancs ÍR (abszolút utak): átirányítás, tee/mv/rm, cp/ln célja, sed -i,
                          dd of=, és értelmező-kódban a fájlírás mellett álló utak
    literals(cmd)         minden abszolút vagy ~-os út a szövegben (idézőjelben, -c-törzsben, heredocban is)
"""
import os
import re
import shlex

SEPS = {";", "&&", "||", "|", "&", "(", ")", ";;", "|&"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
ASSIGN = re.compile(r"(?:^|[;&|\n(]|&&|\|\|)\s*([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]*)")
PY_WRITE = re.compile(r"open\([^)]*['\"][wa]\+?['\"]|json\.dump\(|write_text\(|\.write\(|writeFileSync|appendFile")
ALL_ARGS = {"tee", "mv", "truncate", "touch", "rm", "chmod"}
LAST_ARG = {"cp", "install", "ln", "rsync", "scp"}
LITERAL = re.compile(r"(?:(?<=[\s'\"=(:,])|^)(~?/[^\s'\"`;|&()<>,]+)")


def tokens(text):
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return [w.strip("'\"") for w in re.findall(r"&&|\|\||[;|&()]|[<>]+|[^\s;|&()<>]+", text)]


def subst(cmd):
    vals = {}
    for m in ASSIGN.finditer(cmd):
        v = m.group(2)
        vals[m.group(1)] = v[1:-1] if v[:1] in "'\"" and v[-1:] == v[:1] and len(v) > 1 else v
    for k, v in vals.items():
        if "$" not in v:
            cmd = re.sub(r"\$\{%s\}|\$%s\b" % (k, k), lambda _m, v=v: v, cmd)
    return cmd


def heredocs(cmd):
    lines, kept, bodies, i = cmd.split("\n"), [], [], 0
    while i < len(lines):
        kept.append(lines[i])
        m = HEREDOC.search(lines[i])
        if m:
            j = i + 1
            while j < len(lines) and lines[j].strip() != m.group(2):
                j += 1
            bodies.append(((lines[i].split() or [""])[0], "\n".join(lines[i + 1:j])))
            i = j
        i += 1
    return "\n".join(kept), bodies


def _abs(p, cwd):
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))


def segments(cmd, cwd):
    text, _ = heredocs(cmd)
    cwd = os.path.realpath(cwd)
    out, words = [], []
    for tok in tokens(text.replace("\n", " ; ")) + [";"]:
        if tok not in SEPS:
            words.append(tok)
            continue
        if words and words[0] in ("cd", "pushd") and len(words) > 1 and not words[1].startswith("-"):
            cwd = _abs(words[1], cwd)
        elif words:
            out.append((words, cwd))
        words = []
    return out


def literals(cmd):
    return [m.group(1) for m in LITERAL.finditer(cmd)]


def targets(cmd, cwd):
    """Amit a parancs ír: átirányítás célja, tee/cp/mv/sed -i/dd of= argumentuma, értelmező-kód útjai."""
    out = []
    for words, c in segments(cmd, cwd):
        name = os.path.basename(words[0])
        for i, w in enumerate(words):
            if w in (">", ">>", ">|", "&>", "&>>") and i + 1 < len(words):
                out.append(_abs(words[i + 1], c))
        inplace = name in ("sed", "perl") and any(re.match(r"^-[a-zA-Z]*i", a) for a in words[1:])
        args = [a for a in words[1:] if not a.startswith("-")]
        out += [_abs(a, c) for a in (args if name in ALL_ARGS or inplace else args[-1:] if name in LAST_ARG else [])]
        out += [_abs(a[3:], c) for a in words if name == "dd" and a.startswith("of=")]
    if PY_WRITE.search(cmd):
        out += [_abs(p, cwd) for p in literals(cmd)]
    return out
