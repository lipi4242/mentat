"""The real write targets of a tool call, for the gates that guard their own files
(szerep_kapu_kepesseg: the capability receipts; szerep_kapu_id: the identity gate's files).
Decides like the fleet's F-41 gate (its vedett.py).

hit(root, tool, inp, cwd, paths, trusted=(), script_args=False) -> path | None

Only what is WRITTEN counts, at its resolved path: Write/Edit targets; shell redirects, `tee`,
`cp`, `scp` (its local target), `sed -i`, `rm`, … (szerep_bash) outside heredoc bodies; `mv`/`rm`
of a folder above; a heredoc fed to a shell is read as commands; code given to an interpreter
(`-c`, `-e`, a heredoc) counts when it names a guarded file AND writes. With `script_args`, the
arguments of a script that is not one of `trusted` count too (the receipts: only the repo's own
finder may name them). Free: running or reading the brain's tools (`python3 -I .mentat/bin/…`),
reading a guarded file, a commit message, heredoc prose written to another file, and a command
sent to another machine (`ssh box '…'`).
"""
import os
import re

from szerep_bash import commands
from szerep_kapu import _hits, _replaced, _written
from szerep_kint import real

HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
INTERP = {"python", "python3", "node", "perl", "ruby", "deno", "bun", "php", "osascript"}
SHELLS = {"sh", "bash", "zsh", "dash"}
CODE_FLAGS = {"-c", "-e", "--eval"}
WRITE_CODE = re.compile(r"open\([^)]*,\s*(mode\s*=\s*)?['\"][rbt]*[wax+]|\.open\(\s*['\"][rbt]*[wax+]|write_text|"
                        r"write_bytes|unlink|remove|rmtree|rename|replace|chmod|truncate|writeFile|appendFile|"
                        r"rmSync|unlinkSync|copy|move|symlink")


def _split(cmd):
    """(the command without heredoc bodies, interpreter bodies, shell bodies) — vedett.bash's split."""
    lines, kept, code, shell, i = cmd.split("\n"), [], [], [], 0
    while i < len(lines):
        kept.append(lines[i])
        m = HEREDOC.search(lines[i])
        if m:
            first = os.path.basename((lines[i].split() or [""])[0]).rstrip("0123456789.")
            j = i + 1
            while j < len(lines) and lines[j].strip() != m.group(2):
                j += 1
            body = "\n".join(lines[i + 1:j])
            (code if first in INTERP else shell if first in SHELLS else []).append(body)
            i = j
        i += 1
    return "\n".join(kept), code, shell


def _texts(bare, bodies, cwd, trusted, script_args):
    out = []
    for name, words, wd, _, _ in commands(bare, cwd):
        if name.rstrip("0123456789.") not in INTERP:
            continue
        out += [words[i + 1] for i, w in enumerate(words[:-1]) if w in CODE_FLAGS]
        out += bodies
        script = next((w for w in words[1:] if not w.startswith("-")), "")
        if script_args and script and real(os.path.join(wd or ".", script)) not in trusted:
            out.append(" ".join(words[1:]) + " write_text")  # naming the receipts is enough here
    return out


def _scp(bare, cwd):
    return [os.path.join(wd or ".", os.path.expanduser(w)) for name, words, wd, _, _ in commands(bare, cwd)
            if name == "scp" for w in words[-1:] if not re.match(r"^[\w.-]+:", w)]


def hit(root, tool, inp, cwd, paths, trusted=(), script_args=False):
    guarded = [real(os.path.join(str(root), p)) for p in paths]
    if tool != "Bash":
        found = [p for p in _written(tool, inp, cwd) if _hits(p, guarded, root)]
        return found[0] if found else None
    bare, code, shell = _split(str(inp.get("command", "")))
    for body in shell:
        h = hit(root, "Bash", {"command": body}, cwd, paths, trusted, script_args)
        if h:
            return h
    for p in _written("Bash", {"command": bare}, cwd) + _scp(bare, cwd):
        if _hits(p, guarded, root):
            return p
    for p in _replaced(bare, cwd):
        if _hits(p, guarded, root, True):
            return p
    trusted = {real(os.path.join(str(root), t)) for t in trusted}
    for text in _texts(bare, code, cwd, trusted, script_args):
        if WRITE_CODE.search(text):
            for p, g in zip(paths, guarded):
                if os.path.basename(g) in text.lower():
                    return p
    return None
