"""The shape of an agent-drafted bug report: the public repo's bug form, as Markdown.

build(fields, env_text) -> (title, body) of a new issue; build_comment(fields, env_text) -> body of
a "+1 with new info" comment. Every field comes in ALREADY redacted. digest(draft) binds the
owner's yes to the exact text: any change to repo, kind, issue number, title, body or the security
flag is a new digest, and post refuses the old one. It cannot prove who said yes (see the skill).
"""
import hashlib
import json
import re

MARKER = "<!-- mentat-bug-report v1 -->"
PARTS = {"brain": "Brain (install, skills, reference tools)", "engine": "Engine (engine/)",
         "fleet": "Fleet (server runtime, Telegram bridge, plugin)", "admin": "Admin (web app and API)",
         "unsure": "Not sure"}
FOOTER = ("---\n_Drafted by a Mentat agent (`bug-report` skill): secrets and personal data removed by "
          "its redaction pass, then read and approved by its owner before posting._\n" + MARKER)


def fence(text, lang=""):
    """A code fence longer than any backtick run inside, so the text cannot close it early."""
    longest = max([len(m) for m in re.findall(r"`+", text)] + [2])
    f = "`" * (longest + 1)
    return "%s%s\n%s\n%s" % (f, lang, text.strip("\n"), f)


def no_mentions(text):
    """@name pings a person on GitHub: in prose it becomes `@name` (code spans do not ping)."""
    return re.sub(r"(?<![\w`])@([A-Za-z0-9][\w-]*)", r"`@\1`", text)


def title_of(summary):
    first = no_mentions(summary.strip().splitlines()[0] if summary.strip() else "bug")
    return first if len(first) <= 80 else first[:77].rstrip() + "..."


def _sections(f, env_text):
    out = [("What happened", no_mentions(f["summary"]) or "_not given_"),
           ("What you expected", no_mentions(f.get("expected") or "") or "_not given_")]
    if f.get("steps"):
        out.append(("Steps to reproduce", fence(f["steps"], "shell")))
    if f.get("error"):
        out.append(("Error output", fence(f["error"], "text")))
    return out, [("Environment", fence(env_text, "text"))]


def build(f, env_text):
    head, tail = _sections(f, env_text)
    meta = [("Mentat version", f["version"]), ("Which part", PARTS[f["part"]]), ("How it runs", f["install"])]
    body = "\n\n".join("### %s\n\n%s" % s for s in head + meta + tail)
    body += ("\n\n### Before you post\n\n- [x] I removed tokens, keys, passwords, e-mail addresses and "
             "personal paths.\n- [x] I searched the existing issues and this is not a duplicate.\n\n" + FOOTER)
    return title_of(f["summary"]), body + "\n"


def build_comment(f, env_text):
    head, tail = _sections(f, env_text)
    body = "Also seen here, on Mentat %s (%s, %s).\n\n" % (f["version"], PARTS[f["part"]], f["install"])
    body += "\n\n".join("#### %s\n\n%s" % s for s in head + tail)
    return body + "\n\n" + FOOTER.replace(MARKER, "").rstrip() + "\n"


def digest(d):
    core = {k: d.get(k) for k in ("repo", "kind", "number", "title", "body", "security")}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
