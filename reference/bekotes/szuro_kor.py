"""Scope of `check szuro`: only what the onboarding writes, in the tree AND in git history.

In scope: <root>/business/<name>/**, <root>/szerepek/**, <root>/sablonok/**,
mentat.json, and the AGENTS.md managed block bekotes-<name>. Other tracked
files (an AGENTS.md commit rule with noreply@, a README) are not ours to judge.
Only file names and kinds are reported, never values.
"""
import os
import subprocess

import blokk
import fajlszuro as fs
import szuro

FILES = ("mentat.json",)
MAX_READ = 1024 * 1024


def prefixes(root, business):
    return ["%s/business/%s/" % (root, business), "%s/szerepek/" % root, "%s/sablonok/" % root]


def _git(repo, *a):
    try:
        r = subprocess.run(["git", "-C", str(repo), "-c", "core.quotePath=false", *a],
                           capture_output=True, env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))
    except OSError:
        return ""
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


def _kinds(text):
    return set(szuro.redact(text)[1])


def _fmt(label, kinds):
    return "%s (%s)" % (label, ", ".join(sorted(kinds)))


def scan(repo, root, business, tracked, globs):
    pre, bid, bad = prefixes(root, business), "bekotes-" + business, []
    for p in tracked:
        f = repo / p
        if not (p in FILES or p.startswith(tuple(pre))) or fs.is_binary(p) or fs.tiltott(p, globs) \
                or not f.is_file() or f.stat().st_size > MAX_READ:
            continue
        try:
            k = _kinds(f.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        if k:
            bad.append(_fmt(p, k))
    if "AGENTS.md" in tracked:
        k = _kinds(blokk.extract((repo / "AGENTS.md").read_text(encoding="utf-8", errors="replace"), bid))
        if k:
            bad.append(_fmt("AGENTS.md#" + bid, k))
    history, cur, header = {}, None, False
    for line in _git(repo, "log", "-p", "--format=", "--no-color", "--no-ext-diff", "--",
                     *pre, *FILES).splitlines():
        if line.startswith("diff --git "):  # file attribution from headers only
            cur, header = (line.rsplit(" b/", 1)[1] if " b/" in line else None), True
        elif header:  # ---/+++ and mode lines until the first hunk; an added "++ x" is content
            header = not line.startswith("@@")
        elif line.startswith("+") and cur and not fs.tiltott(cur, globs):
            history.setdefault(cur, set()).update(_kinds(line[1:]))
    bad += [_fmt("történet:" + p, k) for p, k in sorted(history.items()) if k]
    k = set()
    for sha in _git(repo, "log", "--format=%H", "--", "AGENTS.md").split():
        k |= _kinds(blokk.extract(_git(repo, "show", "%s:AGENTS.md" % sha), bid))
    if k:
        bad.append(_fmt("történet:AGENTS.md#" + bid, k))
    return bad
