#!/usr/bin/env python3
"""The whole install in one call, after the USER answered the few real questions at once.

    python3 .mentat/bin/mentat_init.py --lang hu --user "Kertész Anna" --address tegez \\
        --agent Thufir [--engine --tz Europe/Budapest] [--git-name … --git-email …] [--no-prove]

Preflight (git, python, Claude Code >= 2.1.295, disk, network) -> skeleton + guard hook ->
identity placeholders -> mentat.json -> git identity (this repo only) -> engine from the one
Mentat clone (~/src/mentat) at the release tag, `--pack cases`, settings without a timer ->
first commit -> selftest (skeleton check, the guard on an outside read, notes, engine, a fresh session).
Prints a short summary that ends in `MENTAT-INIT OK` or `MENTAT-INIT HIBA: <the one thing>`.
Idempotent: nothing is overwritten. After a HIBA, and with --parts alone, it lists the parts.
"""
import argparse
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE))  # at the END: with `python3 -I` a planted json.py here cannot shadow the stdlib
import mentat_verify  # noqa: E402  (first: nothing downloaded runs before it is checked)
_BAD = mentat_verify.verify(HERE)
if _BAD:
    print("MENTAT-INIT HIBA: " + _BAD)
    sys.exit(1)
import mentat_init_checks as checks  # noqa: E402
import mentat_init_inventory as inv  # noqa: E402
import mentat_init_os as osx  # noqa: E402
import mentat_init_parts as parts  # noqa: E402
import mentat_scaffold as sc  # noqa: E402

ADDRESS = {"hu": {"tegez": "tegezve", "magaz": "magázva"}, "en": {"tegez": "informal", "magaz": "formal"}}
PLACE = {"hu": ("<FELHASZNÁLÓ neve TBD>", "<megszólítás TBD>", "<ügynök neve TBD>"),
         "en": ("<USER name TBD>", "<form of address TBD>", "<agent name TBD>")}
PRODUCT_REPO = "https://github.com/lipi4242/mentat"  # one clone: engine/ (and fleet/, admin/) inside it
CLONE = "~/src/mentat"
MSG = {"hu": {"ready": "Kész az agyad: %s (%s), %s, ezen a gépen.",
              "saved": "Mentve: %s (git: %s <%s>, csak ez a mappa).",
              "safe": "Biztonság: a munkamappán kívül csak a te engedélyeddel olvasok; a Claude Code rákérdez.",
              "engine": "Motor: %s.", "eng_yes": "telepítve (v%s, %s, időzítő nélkül)",
              "eng_no": "nincs (később: „telepítsd a motort”)"},
       "en": {"ready": "Your brain is ready: %s (%s), %s, on this machine.",
              "saved": "Saved: %s (git: %s <%s>, this folder only).",
              "safe": "Safety: outside the working folder I read only with your approval; Claude Code asks you.",
              "engine": "Engine: %s.", "eng_yes": "installed (v%s, %s, no timer)",
              "eng_no": "not installed (later: \"install the engine\")"}}


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)


def fill(root, lang, user, address, agent):
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    for ph, value in zip(PLACE[lang], (user, ADDRESS[lang][address], agent)):
        text = text.replace(ph, value)
    path.write_text(text, encoding="utf-8")


def set_identity(root, who):
    for key, want in zip(("user.name", "user.email"), who):
        if not _git(root, "config", key).stdout.strip():
            _git(root, "config", key, want)  # this repo only, never --global


def checkout(clone, tag, src):
    """The one product clone at the release tag: cloned once, reused at that tag, moved on upgrade."""
    if not clone.exists():
        steps = [["clone", "-q", "--depth", "1", "--branch", tag, src, str(clone)]]
    elif _git(clone, "describe", "--tags", "--exact-match", "HEAD").stdout.strip() == tag:
        return None
    else:
        steps = [["-C", str(clone), "fetch", "-q", "--depth", "1", "origin", "tag", tag],
                 ["-C", str(clone), "checkout", "-q", tag]]
    for cmd in steps:
        r = subprocess.run(["git", *cmd], capture_output=True, text=True)
        if r.returncode != 0:
            return "a Mentat %s nem érhető el itt: %s (%s)" % (tag, clone, (r.stderr.strip().splitlines() or ["?"])[-1])
    return None


def engine(root, a):
    clone = pathlib.Path(os.path.expanduser(CLONE))
    problem = checkout(clone, "v" + a.version_resolved, a.engine_src or PRODUCT_REPO)
    if problem:
        return problem
    for cmd in (osx.script(clone / "engine" / "sync-to.sh") + [".", "--pack", "cases"],
                [sys.executable, "-m", "anytime_engine.setup", "--tz", a.tz, "--lang", a.lang,
                 "--deliver", "file", "--install", "--no-timer"]):
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if r.returncode != 0:
            return "a motor telepítése megállt (%s): %s" % (cmd[1] if cmd[0] == sys.executable else "sync-to.sh",
                                                            (r.stdout + r.stderr).strip()[-200:])
    return None


def run(a):
    root = pathlib.Path(a.repo).resolve()
    lines, problem = checks.preflight(a.engine, bool(a.engine_src))
    if problem:
        return lines, problem
    who, problem = checks.git_identity(root, a.git_name or a.user, a.git_email)
    if problem:
        return lines, problem
    found = inv.found_lines(inv.scan(root), a.lang)   # before anything is written
    os.chdir(root)
    sc.scaffold(root, a.lang, a.base)
    fill(root, a.lang, a.user, a.address, a.agent)
    a.version_resolved = sc.version(a.version)
    if not (root / "mentat.json").exists():
        r = subprocess.run([sys.executable, str(HERE / "mentat_cli.py"), "init-brain", "--name", a.agent,
                            "--language", a.lang, "--brain-root", sc.layout(a.lang)["root"],
                            "--version", a.version_resolved, "--repo", str(root)], capture_output=True, text=True)
        if r.returncode != 0:
            return lines, "a mentat.json nem jött létre: " + (r.stdout + r.stderr).strip()[-160:]
    set_identity(root, who)
    if a.engine:
        problem = engine(root, a)
        if problem:
            return lines, problem
    before = inv.head(root)
    if subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", a.lang, "--repo", str(root),
                       "--commit"], capture_output=True, text=True).returncode != 0:
        return lines, "az első commit nem sikerült (git status)"
    more, problem = checks.selftest(root, a.lang, a.engine, a.prove, a.agent, a.user)
    m = MSG[a.lang]
    head = _git(root, "log", "--oneline", "-1").stdout.strip()
    lines += [m["ready"] % (a.agent, a.user, ADDRESS[a.lang][a.address])] + found + [m["saved"] % (head, *who)] + \
        inv.after_lines(root, before, a.lang) + [m["safe"],
              m["engine"] % (m["eng_yes"] % (a.version_resolved, a.tz) if a.engine else m["eng_no"])] + more
    return lines, problem


def main(argv=None):
    if parts.cli(sys.argv[1:] if argv is None else argv):  # --parts: which Mentat parts are here
        return 0
    p = argparse.ArgumentParser(prog="mentat_init.py")
    p.add_argument("--repo", default=".")
    p.add_argument("--lang", required=True, choices=["hu", "en"])
    p.add_argument("--user", required=True)
    p.add_argument("--address", required=True, choices=["tegez", "magaz"])
    p.add_argument("--agent", required=True)
    p.add_argument("--base", required=True, help="the manual's base URL (…/vX.Y.Z/)")
    p.add_argument("--version", help="defaults to release.json next to this tool")
    p.add_argument("--git-name")
    p.add_argument("--git-email")
    p.add_argument("--engine", action="store_true")
    p.add_argument("--tz", help="with --engine: the USER's IANA timezone")
    p.add_argument("--engine-src", help="a local clone or mirror of the Mentat repo instead of GitHub")
    p.add_argument("--no-prove", dest="prove", action="store_false", help="skip the fresh-session check")
    a = p.parse_args(argv)
    if a.engine and not a.tz:
        p.error("--engine needs --tz")
    lines, problem = run(a)
    lines += parts.lines(a.repo, a.lang) if problem else []
    print("\n".join(lines + ["MENTAT-INIT HIBA: " + problem if problem else "MENTAT-INIT OK"]))
    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
