#!/usr/bin/env python3
"""Semi-automatic bug report to the public Mentat repo: the agent drafts, the OWNER decides.

    python3 -I .mentat/bin/mentat_bugreport.py draft --summary TEXT [--expected TEXT]
        [--steps TEXT | --steps-file F] [--error TEXT | --error-file F] [--part brain|engine|fleet|admin|unsure]
        [--install desktop|code|server|other] [--comment-on N] [--names-file F ...] [--offline] [--repo .]
    python3 -I .mentat/bin/mentat_bugreport.py post DIR --approve CODE --owner-said "<the owner's reply>" [--dry-run]

draft writes nothing public: it collects versions (never hosts, paths, accounts), redacts every
field, refuses when anything secret-shaped is left (exit 2) or the error looks like a security
problem (exit 5: private advisory, never a public issue), looks for duplicates with the redacted
words, and writes DIR/draft.md + draft.json with an approval CODE (a digest of the exact text).
post publishes only with that CODE and an affirmative owner reply (else exit 3), through the
owner's own `gh` (none: exit 4, the draft stays for a manual post), at most 3 a day (exit 6).
"""
import argparse
import datetime
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE))  # at the END: with `python3 -I` a planted module here cannot shadow the stdlib
import mentat_bugreport_draft as shape  # noqa: E402
import mentat_bugreport_env as env  # noqa: E402
import mentat_bugreport_gh as gh  # noqa: E402
import mentat_bugreport_redact as red  # noqa: E402

PUBLIC = "lipi4242/mentat"
ADVISORY = "https://github.com/%s/security/advisories/new" % PUBLIC
NEW_ISSUE = "https://github.com/%s/issues/new?template=bug_report.yml" % PUBLIC
SECURITY = re.compile(r"(?i)\b(vulnerab\w*|exploit\w*|leak\w*|exposed|bypass\w*|injection|privilege|cve-\d|"
                      r"rce|xss|csrf|sandbox escape|unauthori[sz]ed|sérülékeny\w*|szivárg\w*|megkerül\w*)")
# The whole reply must be a yes (an optional "post it"-style tail, punctuation): "yes, but only save
# a draft" or "igen, de várj" is NOT a yes. Anything else asks again.
_YES_WORD = r"(yes|yep|ok|okay|sure|go ahead|igen|oké|oke|mehet|jó|jo)"
_YES_TAIL = r"(post it|send it|go ahead|please|mehet|küldd|kuldd|tedd fel|rakd fel|igen)"
YES = re.compile(r"(?i)^\s*%s(\s*[,!.]?\s*%s)*\s*[.!]*\s*$" % (_YES_WORD, _YES_TAIL))
DAILY_LIMIT = 3


def _text(value, path, tail=60):
    t = pathlib.Path(path).read_text(encoding="utf-8", errors="replace") if path else (value or "")
    return "\n".join(t.strip("\n").splitlines()[-tail:])[-6000:]


def cmd_draft(a):
    repo = pathlib.Path(a.repo).resolve()
    names = env.private_names(repo, a.names_file or [])
    facts = env.facts(repo, HERE, a.install)
    raw = {"summary": a.summary, "expected": a.expected or "", "steps": _text(a.steps, a.steps_file, 40),
           "error": _text(a.error, a.error_file)}
    fields = {k: red.redact(v, names)[0] for k, v in raw.items()}
    fields.update(version=red.redact(facts["version"], names)[0], part=a.part, install=facts["install"])
    env_text = red.redact(env.environment_text(facts), names)[0]
    kind = "comment" if a.comment_on else "new"
    if kind == "comment":
        title, body = "", shape.build_comment(fields, env_text)
    else:
        title, body = shape.build(fields, env_text)
    left = red.residue(title + "\n" + body, names)
    if left:
        print("STOP: after redaction the draft still carries: %s. Nothing written; tell the owner." % ", ".join(left))
        return 2
    security = a.security or (not a.not_security and any(SECURITY.search(v) for v in raw.values()))
    d = {"repo": PUBLIC, "kind": kind, "number": a.comment_on, "title": title, "body": body,
         "security": security, "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    d["digest"] = shape.digest(d)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = repo / ".mentat/bug-reports" / stamp
    out.mkdir(parents=True, exist_ok=True)
    (out.parent / ".gitignore").write_text("*\n", encoding="utf-8")
    (out / "draft.json").write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "draft.md").write_text(("# %s\n\n" % title if title else "") + body, encoding="utf-8")
    print("DRAFT %s\n" % out)
    print(("TITLE: %s\n\n" % title if title else "COMMENT on #%s\n\n" % a.comment_on) + body)
    if security:
        print("SECURITY: this looks like a security problem. Do NOT post it. Tell the owner to report it "
              "privately: %s (the draft above can be pasted there)." % ADVISORY)
        return 5
    if kind == "new" and not a.offline:
        why = gh.available()
        dups = [] if why else gh.duplicates(PUBLIC, title, fields["error"] + " " + fields["summary"])
        if why:
            print("DUPLICATES: not checked (%s)" % why)
        for dup in dups:
            print("POSSIBLE DUPLICATE #%s (%s, score %.2f): %s %s" % (dup["number"], dup["state"], dup["score"],
                                                                      dup["title"], dup["url"]))
        if dups:
            print("ASK the owner first: add the new details to #%s instead (draft --comment-on %s ...)?"
                  % (dups[0]["number"], dups[0]["number"]))
    print("\nASK the owner on your normal channel, showing the draft above word for word: post it to %s? "
          "Only on a clear yes run:\n  post %s --approve %s --owner-said \"<their reply>\"" % (PUBLIC, out, d["digest"]))
    return 0


def _posted_today(log):
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    try:
        return sum(1 for l in log.read_text(encoding="utf-8").splitlines() if l.startswith(today))
    except OSError:
        return 0


def cmd_post(a):
    out = pathlib.Path(a.dir)
    d = json.loads((out / "draft.json").read_text(encoding="utf-8"))
    if d.get("security"):
        print("REFUSED: a security problem is never posted in public. Report it privately: %s" % ADVISORY)
        return 5
    if d.get("repo") != PUBLIC or a.approve != d.get("digest") or shape.digest(d) != d.get("digest"):
        print("NOT APPROVED: the code does not match this exact draft. Show the owner the current draft and ask again.")
        return 3
    said = a.owner_said or ""
    if not YES.match(said):
        print("NOT APPROVED: the owner's reply is not a clear yes (%r). Nothing posted." % said[:40])
        return 3
    names = env.private_names(pathlib.Path(a.repo).resolve(), a.names_file or [])
    left = red.residue(d["title"] + "\n" + d["body"], names)
    if left:
        print("STOP: the draft carries %s. Nothing posted; draft it again." % ", ".join(left))
        return 2
    log = out.parent / "posted.log"
    if not a.dry_run and _posted_today(log) >= DAILY_LIMIT:
        print("LIMIT: %d reports were posted today already. Nothing posted." % DAILY_LIMIT)
        return 6
    why = None if a.dry_run else gh.available()
    if why:
        print("NOT POSTED: %s. The draft is in %s/draft.md: the owner can paste it at %s" % (why, out, NEW_ISSUE))
        return 4
    body_file = out / "body.md"
    body_file.write_text(d["body"], encoding="utf-8")
    rc, msg = gh.post(d["repo"], d["kind"], d["title"], body_file, d.get("number"), dry_run=a.dry_run)
    print(("DRY RUN, would run: %s" if a.dry_run else ("POSTED: %s" if rc == 0 else "FAILED: %s")) % msg)
    if rc == 0 and not a.dry_run:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        (out / "approval.json").write_text(json.dumps({"at": now, "owner_said": said, "url": msg}) + "\n")
        with log.open("a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (now, msg))
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    dr = sub.add_parser("draft")
    dr.add_argument("--summary", required=True)
    dr.add_argument("--expected")
    for f in ("steps", "error"):
        g = dr.add_mutually_exclusive_group()
        g.add_argument("--" + f)
        g.add_argument("--%s-file" % f)
    dr.add_argument("--part", choices=sorted(shape.PARTS), default="unsure")
    dr.add_argument("--install", choices=sorted(env.INSTALLS))
    dr.add_argument("--comment-on", type=int)
    dr.add_argument("--security", action="store_true", help="the owner says it is a security problem")
    dr.add_argument("--not-security", action="store_true",
                    help="the owner read the draft and says it is NOT a security problem (a word like 'leak' matched)")
    dr.add_argument("--offline", action="store_true", help="no duplicate search")
    po = sub.add_parser("post")
    po.add_argument("dir")
    po.add_argument("--approve", required=True)
    po.add_argument("--owner-said", required=True)
    po.add_argument("--dry-run", action="store_true")
    for p in (dr, po):
        p.add_argument("--repo", default=".")
        p.add_argument("--names-file", action="append")
    a = ap.parse_args(argv)
    return cmd_draft(a) if a.cmd == "draft" else cmd_post(a)


if __name__ == "__main__":
    sys.exit(main())
