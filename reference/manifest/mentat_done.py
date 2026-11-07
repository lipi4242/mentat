#!/usr/bin/env python3
"""mentat_done.py — before you call work done: check it the way the USER will meet it.

    python3 .mentat/bin/mentat_done.py [--url A]... [--protected A]... [--file P]... [--scheduled [--output F]... [--expect TEXT]...]

--protected ADDRESS: unsigned, it answers with the sign-in, never the page. --url: the address you gave the USER answers 200 (no redirect followed; behind a sign-in use
mentat_web.py check with their cookie). --file: the file you said you made is there and not
empty. --scheduled [--output FILE]: the last scheduled run landed within --hours, was not degraded, and
left its output (the engine's file delivery, and each --output of an own job, written for that
run): mentat_done_sched.py. Without a run, do not say a schedule ran. Always: unsaved changes in this
folder (WARN: commit your own, and tell the USER theirs are left alone) and pages started with
mentat_serve.py that still run (WARN: say so and until when, or stop them).
Also TELL lines: a credential in a tracked file (mentat_secret_scan.py) — tell the USER. Verdict:
`DONE-CHECK GREEN` (exit 0) only with a check where the USER meets it (a non-local --url, --file,
--scheduled); `LOCAL ONLY` / `NOT VERIFIED` (exit 2): say so, do not call it working;
`DONE-CHECK RED — do not call it done` (exit 1). It does not judge whether the content is what was asked: that is the contract
check (mentat_accept.py).
"""
import argparse
import ipaddress
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE))  # at the END: with `python3 -I` a planted module here cannot shadow the stdlib
import mentat_serve_proc as proc  # noqa: E402
import mentat_done_sched as sched  # noqa: E402
import mentat_secret_scan as secrets  # noqa: E402
import mentat_web  # noqa: E402


def _stamp(t):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))


def urls(addresses):
    out = []
    for u in addresses:
        status, _, why = mentat_web.fetch(u, {"User-Agent": "mentat-done"}, timeout=10)
        out.append("OK address answers: %s" % u if status == 200 else
                   "RED address %s does not answer 200 (%s)%s" % (u, why or status, " — a sign-in page: check it with "
                   "--protected, signed in with mentat_web.py check --cookie-file" if "access" in str(why) else ""))
    return out


def protected(addresses):
    """Unsigned, a page that should be protected answers with the sign-in (Access), never the page."""
    out = []
    for u in addresses:
        status, _, where = mentat_web.fetch(u, {"User-Agent": "mentat-done"}, timeout=10)
        gate = status in (401, 403) or (300 <= status < 400 and re.search(r"cloudflareaccess\.com|/cdn-cgi/access/", where or ""))
        out.append("OK protected: an unsigned visitor of %s gets the sign-in (%d)" % (u, status) if gate else
                   "RED %s is not protected: anyone can open it (%s)" % (u, status if status == 200 else where or status))
    return out


def files(root, paths):
    out = []
    for f in paths:
        p = root / f
        if p.is_file() and p.stat().st_size > 0:
            out.append("OK file %s (%d bytes, changed %s)" % (f, p.stat().st_size, _stamp(p.stat().st_mtime)))
        else:
            out.append("RED file %s is %s" % (f, "empty" if p.is_file() else "not there"))
    return out


def unsaved(root):
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "."], capture_output=True, text=True)
    if r.returncode != 0:
        return ["WARN not a git folder: nothing here is saved in history"]
    changed = [ln[3:] for ln in r.stdout.splitlines() if ln.strip()]
    if not changed:
        return []
    return ["WARN not committed: %d (%s%s) — commit your own work; tell the USER theirs is left alone"
            % (len(changed), ", ".join(changed[:5]), ", …" if len(changed) > 5 else "")]


def running(root):
    out = []
    for f in sorted((root / proc.STATE).glob("*.json")):
        st = proc._load(f)
        if proc.alive(st):
            until = _stamp(st["deadline"]) if st.get("deadline") else "until stopped"
            out.append("WARN still running: %s %s (stops %s) — tell the USER, or mentat_serve.py stop %s"
                       % (st.get("name"), st.get("url") or "(no address)", until, st.get("name")))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_done.py")
    p.add_argument("--repo", default=".")
    p.add_argument("--url", action="append", default=[])
    p.add_argument("--file", action="append", default=[])
    p.add_argument("--protected", action="append", default=[], help="an address only signed-in people may open")
    p.add_argument("--expect", action="append", default=[], help="with --scheduled: text the output must hold")
    p.add_argument("--scheduled", action="store_true")
    p.add_argument("--output", action="append", default=[], help="with --scheduled: an own job's output file")
    p.add_argument("--hours", type=float, default=26)
    a = p.parse_args(argv)
    root = pathlib.Path(a.repo)
    lines = urls(a.url) + protected(a.protected) + files(root, a.file) + (
        sched.lines(root, a.hours, a.output, a.expect) if a.scheduled else [])
    lines += unsaved(root) + running(root) + secrets.lines(root)
    code, verdict = verdict_of(lines, a)
    print("\n".join(lines + [verdict]))
    return code


def _local(host):
    if host in (None, "", "localhost") or str(host).endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified or ip.is_private or ip.is_link_local


def verdict_of(lines, a):
    """GREEN needs a check where the USER meets it: a non-local address, the real file, the real schedule."""
    tell = sum(ln.startswith("TELL ") for ln in lines)
    first = " — but first tell the USER about the %d TELL line(s)" % tell if tell else ""
    if any(ln.startswith("RED ") for ln in lines):
        return 1, "DONE-CHECK RED — do not call it done" + first
    remote = [u for u in a.url + a.protected if not _local(urllib.parse.urlsplit(u).hostname)]
    if not (remote or a.file or a.scheduled):
        if a.url or a.protected:
            return 2, ("DONE-CHECK LOCAL ONLY — checked on this machine only: tell the USER it works here, "
                       "not yet where they use it (the deployed address)" + first)
        return 2, ("DONE-CHECK NOT VERIFIED — nothing the USER uses was checked: give the address (--url), "
                   "the file (--file) or the schedule (--scheduled); until then do not call it done" + first)
    return 0, "DONE-CHECK GREEN" + first


if __name__ == "__main__":
    sys.exit(main())
