"""PII/secret filter for memory export. Patterns follow scripts/release_check.py (copied)."""
import ipaddress
import re

DOC_NETS = [ipaddress.ip_network(n) for n in
            ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "127.0.0.0/8")]

# Order matters: longer / more specific patterns first.
PATTERNS = {
    "titok": re.compile(
        r"(?:-{5}BEGIN [A-Z ]*PRIVATE KEY-{5}[\s\S]*?-{5}END [A-Z ]*PRIVATE KEY-{5}\s?|gh[po]_\w+|github_pa[t]_\w+|xox[abp]-[\w-]+|AKIA[0-9A-Z]{16}|sk-ant-[\w-]+"
        r"|sk-[A-Za-z0-9]{20,}|-{5}BEGIN [A-Z ]*PRIVATE KEY[\s\S]*"  # no END line: to the end of text
        r"|\b[A-Z_]*(?:KEY|TOKEN|SECRET)=\S+)"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b"),
    "adoszam": re.compile(r"\b\d{8}-\d-\d{2}\b"),
    "telefon": re.compile(
        r"(?<![\w-])(?:(?:\+\d{1,3}|06)[ -]?\d{1,2}[ -]?\d{3}[ -]?\d{3,4}"
        r"|\d{2,3}[ -]\d{3}[ -]\d{3,4})(?![\w-])"),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "home": re.compile(r"/(?:Users|home)/[^/\s]+"),
}

SUSPICIOUS = re.compile(
    r"ignore (?:all|previous)|hagyd figyelmen kívül|küldd el|send .* to"
    r"|push .* (?:main|master)|\.env", re.I)


def _ip_keep(m):
    try:
        return any(ipaddress.ip_address(m) in n for n in DOC_NETS)
    except ValueError:
        return True


def redact(text):
    """Return (redacted text, {kind: count}); hits never hold values."""
    hits = {}
    for kind, rx in PATTERNS.items():
        def sub(m, kind=kind):
            if kind == "ip" and _ip_keep(m.group(0)):
                return m.group(0)
            hits[kind] = hits.get(kind, 0) + 1
            return "<%s>" % kind
        text = rx.sub(sub, text)
    return text, hits


def suspicious(text):
    return bool(SUSPICIOUS.search(text))
