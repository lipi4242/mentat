"""F-41, a flotta prototípusának (ident.py) átvétele. A felhasználó azonosítóinak generált listája és keresése szövegben (F-41).

    load(extra_dirs=()) -> Ids     a gépen talált azonosítók, kódolt alakokkal
    Ids.find(text) -> [str]        a talált azonosítók típusa (soha nem az értékük)

Források (csak a nem-titkos mezők): `git config user.email` (globális és a megadott
repókban), a Claude-konfigok `oauthAccount.emailAddress` mezője, a `gh` fiók publikus
e-mailje, és a csak a felhasználó által írható kiegészítő fájl
(`~/.mentat/identitas.txt`, soronként egy azonosító, `#` megjegyzés).
Kódolt alakok: kis- és nagybetű, URL-kódolás, base64 (mindhárom igazítás), és a
hash-elt e-mail (md5/sha1/sha256 hex), mert a hirdetési trackerek ezt kérik.
"""
import base64
import glob
import hashlib
import json
import os
import re
import subprocess
import urllib.parse

EXTRA = os.path.expanduser("~/.mentat/identitas.txt")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
# Kifejezések, amik futás közben az azonosítót adják (a parancsban nincs ott a cím).
SOURCE_EXPR = re.compile(r"git\s+(-C\s+\S+\s+)?config\s+(--get\s+|--global\s+)*user\.email|"
                         r"%a[en]\b|\$\{?(GIT_AUTHOR_EMAIL|GIT_COMMITTER_EMAIL|EMAIL)\b|"
                         r"oauthAccount|emailAddress|gh\s+api\s+user\b", re.I)


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _claude_emails():
    out = []
    for p in {os.path.expanduser("~/.claude.json"), *glob.glob(os.path.expanduser("~/.claude*/.claude.json")),
              os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", "~"), ".claude.json")}:
        try:
            with open(os.path.expanduser(p), encoding="utf-8", errors="replace") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        acc = doc.get("oauthAccount") if isinstance(doc, dict) else None
        if isinstance(acc, dict) and isinstance(acc.get("emailAddress"), str):
            out.append(acc["emailAddress"])
    return out


def _b64_cores(s):
    """A base64 alak, ami bármely nagyobb, base64-be kódolt szövegben is megjelenik."""
    out, raw = [], s.encode()
    for pad in range(3):  # a cím a 3 bájtos csoporton belül 0., 1. vagy 2. bájton kezdődik
        enc = base64.b64encode(b"\0" * pad + raw).decode()
        core = enc[-(-8 * pad // 6):(8 * (pad + len(raw))) // 6]  # csak a címből számolt jelek
        if len(core) >= 12:
            out += [core, core.replace("+", "-").replace("/", "_")]  # a URL-safe változat is
    return list(dict.fromkeys(out))


def variants(value):
    v = value.strip()
    low = v.lower()
    forms = {"nyers": [low], "url": [urllib.parse.quote(low, safe="").lower()],
             "base64": _b64_cores(v) + _b64_cores(low)}
    if EMAIL.match(v):
        forms["hash"] = [getattr(hashlib, h)(low.encode()).hexdigest() for h in ("md5", "sha1", "sha256")]
    return forms


class Ids:
    def __init__(self, values):
        self.values = sorted({v.strip() for v in values if isinstance(v, str) and len(v.strip()) >= 6})
        self.forms = []  # (kind, needle, case_sensitive)
        for i, v in enumerate(self.values, 1):
            for kind, needles in variants(v).items():
                for n in needles:
                    self.forms.append(("id%d:%s" % (i, kind), n, kind == "base64"))

    def find(self, text):
        low = text.lower()
        hits = [k for k, n, cs in self.forms if n in (text if cs else low)]
        if SOURCE_EXPR.search(text):
            hits.append("forras-kifejezes")
        return list(dict.fromkeys(hits))

    def domains(self):
        return sorted({v.split("@", 1)[1].lower() for v in self.values if EMAIL.match(v)})


def _extra(path=EXTRA):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:  # an odd file never stops the gate
            return [ln.split("#", 1)[0].strip() for ln in f if ln.split("#", 1)[0].strip()]
    except (OSError, ValueError):
        return []


def load(extra_dirs=(), gh=True, extra_file=EXTRA):
    vals = [_run(["git", "config", "--global", "user.email"])]
    vals += [_run(["git", "-C", d, "config", "user.email"]) for d in extra_dirs]
    vals += _claude_emails() + _extra(extra_file)
    if gh:
        vals.append(_run(["gh", "api", "user", "-q", ".email"]))
    return Ids(vals)
