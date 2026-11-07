"""`check`: is the onboarding done? One PASS/FAIL line per check, all of them.

Exit 0 only if every line is PASS. Values found by the filter are never
printed, only file names and kinds.
"""
import pathlib
import os
import subprocess

import fajlszuro as fs
import hely
import hivatkozas
import klon
import leltar as lt
import mentat_manifest as mm
import mentat_rules as rules
import szuro_kor

ALLOWED_KEYS = {"path", "file", "tiltott"}


def _short(items, n=8):
    items = list(items)
    return ", ".join(items[:n]) + (" … (+%d)" % (len(items) - n) if len(items) > n else "")


def _tracked(repo):
    try:
        # tracked AND untracked-but-not-ignored: the check must hold before `git add`, too
        r = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "-co", "--exclude-standard"],
                           capture_output=True, env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))
    except OSError:
        return None
    return [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p] if r.returncode == 0 else None


def _roles(repo, root, lel):
    manifest = mm.load(repo)
    bad = ["%s at %s" % (e["code"], e["at"]) for e in rules.roles_errors(manifest)]
    section = rules._dict(manifest.get("roles"))
    default = section.get("default")
    if not default:
        bad.append("nincs roles.default")
    if default == "kiado" and (lel or {}).get("kiado_alapnak") is not True:
        bad.append("a kiado nem lehet fő szerep (van kiadó ágens, vagy nincs leltár)")
    for n in section.get("installed") or []:
        if isinstance(n, str) and not (repo / root / "szerepek" / (n + ".md")).is_file():
            bad.append("hiányzik %s/szerepek/%s.md" % (root, n))
    return bad


def _tiltott(cfg, lel, tracked):
    by_name = {s.get("name"): fs.globs_of(s) for s in cfg.get("sources") or [] if isinstance(s, dict)}
    every = [g for gs in by_name.values() for g in gs]
    bad = [p for p in tracked if fs.tiltott(p, every)]
    for s in (lel or {}).get("sources") or []:
        if not isinstance(s, dict):
            continue
        for f in [f for f in s.get("files") or [] if isinstance(f, dict)]:
            key = f.get("path") or f.get("file")
            forbidden = isinstance(key, str) and fs.tiltott(key, by_name.get(s.get("name")) or [])
            if (forbidden or f.get("tiltott")) and (set(f) - ALLOWED_KEYS or f.get("tiltott") is not True):
                bad.append("leltar.json:%s:%s" % (s.get("name"), key))
    return bad, every


def _lemez(repo, cfg):
    """Forbidden files present in a repo source's working tree (`klon` keeps them out)."""
    bad = []
    for s in cfg.get("sources") or []:
        if not (isinstance(s, dict) and s.get("kind") == "repo" and fs.globs_of(s)):
            continue
        try:
            path = lt.resolve(repo, s.get("path") or "")
        except ValueError:
            continue
        if path.is_dir():
            bad += ["%s:%s" % (s.get("name"), rel) for rel in klon.leftovers(path, fs.globs_of(s))]
    return bad


def _hook(repo):
    s = hely.read_json(repo / ".claude" / "settings.json") or {}
    hooks = rules._dict(s.get("hooks"))

    def cmds(event):
        return [str(h.get("command", "")) for e in hooks.get(event) or [] if isinstance(e, dict)
                for h in e.get("hooks") or [] if isinstance(h, dict)]
    pre = [c for c in cmds("PreToolUse") if ".mentat/bin/bekotes/szerep_guard.py" in c
           and "--session-start" not in c]
    start = [c for c in cmds("SessionStart") if ".mentat/bin/bekotes/szerep_guard.py" in c
             and "--session-start" in c]
    bad = [] if pre else ["nincs PreToolUse szerep-őr"]
    bad += [] if start else ["nincs SessionStart szerep-őr"]
    if not (repo / ".mentat" / "bin" / "bekotes" / "szerep_guard.py").is_file():
        bad.append("hiányzik .mentat/bin/bekotes/szerep_guard.py (0. lépés)")
    return bad


def results(repo, business):
    repo = pathlib.Path(repo)
    root, biz = hely.brain_root(repo), hely.biz_dir(repo, business)
    cfg, lel = hely.read_json(biz / "bekotes.json"), hely.read_json(biz / "leltar.json")
    out = [("bekotes-json", (["'..' tilos: %s" % x for x in hely.dotdot_errors(cfg)])
            if cfg and isinstance(cfg.get("sources"), list)
            else ["hiányzik vagy hibás: %s" % (biz / "bekotes.json").relative_to(repo)]),
           ("leltar-json", [] if lel else ["hiányzik vagy hibás: %s" % (biz / "leltar.json").relative_to(repo)])]
    cfg = cfg or {}
    gaps = {g.get("name"): g for g in (lel or {}).get("hianylista") or [] if isinstance(g, dict)}
    out.append(("hianylista", ["nincs leltár"] if not lel else [
        s.get("name") for s in lel.get("sources") or [] if isinstance(s, dict)
        and s.get("state") == "blokkolt" and not (gaps.get(s.get("name")) or {}).get("reason")]))
    for n in hivatkozas.MAP_FILES:
        p = biz / (n + ".md")
        text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
        out.append((n, ["hiányzik"] if text is None else
                    ([] if "(forrás: " in text else ["nincs (forrás: …) hivatkozás"])))
    total, bad = hivatkozas.check(repo, biz, cfg, lel)
    out.append(("hivatkozas", bad if total else ["nincs hivatkozás"]))
    out.append(("szerepek", _roles(repo, root, lel)))
    tracked = _tracked(repo)
    try:
        tilt, globs = _tiltott(cfg, lel, tracked or [])
    except ValueError as e:
        tilt, globs = [str(e)], []
    out.append(("szuro", ["nem git-repó"] if tracked is None
                else szuro_kor.scan(repo, root, business, tracked, globs)))
    out.append(("tiltott", ["nem git-repó"] if tracked is None else tilt))
    try:
        out.append(("tiltott-lemez", _lemez(repo, cfg)))
    except ValueError as e:
        out.append(("tiltott-lemez", [str(e)]))
    out.append(("hook", _hook(repo)))
    return out


def run(a):
    out = results(a.repo, a.business)
    for name, bad in out:
        print("PASS %s" % name if not bad else "FAIL %s: %s" % (name, _short(bad)))
    return 0 if all(not bad for _, bad in out) else 1
