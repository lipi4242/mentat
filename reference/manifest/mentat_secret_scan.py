"""Credentials in files git tracks: where and what kind, never the value.

found(root) -> [(path, line or 0, kind)] over `git ls-files` (at most MAX files, each under 1 MB):
a secret-shaped file name (.env, a private key file, credentials.json) or a line that looks like
a key (private key block, AWS/GitHub/Slack/Google/OpenAI/Anthropic-style tokens, `password=` /
`api_key: "…"` with a long value). lines(root) -> the TELL lines mentat_done.py and the install
print: the agent tells the USER plainly where, and that the key needs to be replaced (moving it
out of the file does not remove it from the history). Known limits: patterns, not proof; a
secret of an unknown shape is not seen, and a placeholder that looks real is reported.
"""
import pathlib
import re
import subprocess

MAX = 3000
NAMES = re.compile(r"(^|/)(\.env(\.[\w-]+)?|id_(rsa|dsa|ecdsa|ed25519)|[\w-]+\.(pem|p12|pfx|key)|"
                   r"credentials\.json|\.netrc|\.npmrc|\.pypirc)$", re.I)
SAFE = re.compile(r"\.env\.(example|sample|template|dist)$", re.I)
SHAPES = [("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
          ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
          ("GitHub token", re.compile(r"\bgh[opsu]_[A-Za-z0-9]{36}\b|\bgithub" r"_pat_[A-Za-z0-9_]{40,}")),
          ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
          ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
          ("API key", re.compile(r"\bsk-(ant-|proj-|or-)?[A-Za-z0-9_-]{20,}")),
          ("password or key", re.compile(r"(?i)\b(pass(word)?|secret|api[_-]?key|token)\b\s*[:=]\s*['\"]?"
                                         r"(?!<|\$|\{|your|xxx|change)[A-Za-z0-9/+_=.-]{16,}"))]


def found(root):
    root = pathlib.Path(root)
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", "."], capture_output=True)
    out = []
    for rel in [x for x in r.stdout.decode("utf-8", "replace").split("\0") if x][:MAX]:
        if NAMES.search(rel) and not SAFE.search(rel):
            out.append((rel, 0, "secret file"))
            continue
        p = root / rel
        try:
            if not p.is_file() or p.stat().st_size > 1_000_000:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            kind = next((k for k, rx in SHAPES if rx.search(line)), None)
            if kind:
                out.append((rel, n, kind))
                break  # one per file is enough to tell
    return out


def lines(root):
    return ["TELL credential (%s) in a file git keeps: %s%s — tell the USER now, in plain words (where, what kind, "
            "never the value), and that it must be replaced with a new one: taking it out of the file does "
            "not take it out of the history" % (kind, rel, ":%d" % n if n else "") for rel, n, kind in found(root)]
