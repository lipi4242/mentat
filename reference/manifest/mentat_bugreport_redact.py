"""Redaction for a public bug report: what may leave the machine, never the value of a secret.

redact(text, names) -> (clean text, {kind: count}). Every rule replaces a match with a <placeholder>;
a value already a placeholder is never matched again. residue(text, names) -> [kinds] runs the
same rules on the FINAL report: anything left is a stop, never a post (fail-closed). Reuses the
secret shapes of mentat_secret_scan.py and adds what a log line carries: URL credentials, bearer
and bot tokens, JWTs, secret headers, key/value pairs in every shape a log carries (JSON with
either quote, escaped once or twice, plural keys, a secret name/value pair, YAML, env, query strings, --flags, prose "password is X" / "jelszó: X")
for secret keys AND id-ish keys (chat_id, user, handle ...), e-mail, home paths (/home, /Users,
/root, ~user, C:\\Users), IPv4 and IPv6 addresses, UUIDs, long hex or token-like strings, IBAN, phone and long numeric ids (chat ids),
and the private names the caller passes (whole word, any case). Known limit: patterns, not proof;
the owner reads the draft before anything is posted. Shapes known to pass with a short, human-chosen
value (C-02 remainder, documented, not handled): a YAML block scalar (`|`, `>-`), an XML tag, a tab-
or table-row layout, `key => value` (only the `>` is replaced), smart quotes, `&quot;` and URL-encoded
quotes, `mysql -pX` / `sshpass -p X`, and the "X is my password" word order.
"""
import ipaddress
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE))  # at the END: with `python3 -I` a planted module here cannot shadow the stdlib
import mentat_secret_scan as scan  # noqa: E402

PLACEHOLDERS = ("redacted", "token", "credentials", "user", "id", "email", "name", "ip", "number")
# only a placeholder this module writes is left alone; any other "<value>" is input and gets redacted
NOT_PH = r"(?!<(?:%s)>(?![\w-]))" % "|".join(PLACEHOLDERS)
SECRET_WORDS = (r"(?:token|secret|password|passwd|passphrase|pass|pwd|api[_-]?key|apikey|key|auth(?:orization|entication)?"
                r"|cookie|session|credentials?|private[_-]?key|jelsz[oó]\w*|kulcs\w*|titok\w*)")
CAMEL = r"(?-i:[a-z][a-zA-Z0-9]*(?:Token|Secret|Password|Passwd|Key|Auth|Cookie|Session|Credentials?|Id))"
ID_KEYS = (r"(?:(?:chat|user|channel|group|account|owner|from|sender|tg|telegram|customer|client|member|guild|team"
           r"|org|tenant|device|phone)[_-]?(?:id|number|num)|uid|id|user(?:[_-]?name)?|login|handle|e-?mail|phone)")
# A key, quoted or not (JSON "k", YAML k, env K, query k=, escaped JSON \"k\"), then : or =, or prose
# ("password is", "jelszó:"), then the value: quoted (either quote, escaped, multi-line) or bare.
Q = r"(?:\\{1,3})?[\"']?"
SEP = r"(\s*[:=]\s*|\s+(?:is|was|are|set to|=|értéke|legyen|lett)\s*[:=]?\s*)"
VALUE = (r"(\[[^\]\r\n]{0,2000}\]|(?:\\{1,3})?\"(?:[^\"\\]|\\.){0,2000}?(?:\\{1,3})?\"|(?:\\{1,3})?'(?:[^'\\]|\\.){0,2000}?(?:\\{1,3})?'|" + NOT_PH
         + r"[^\s,;&}\]\)\"']+)")


def _pair(words):
    # KeyError: 'x' / TokenExpiredError: ... are exception names, not keys: a traceback keeps them
    key = (r"(?:\b(?![\w.-]*(?:Error|Exception|Warning)\b)(?:[\w-]*[_.-])?" + words + r"s?(?:[_.-][\w.-]*)?\b|"
           + CAMEL + r")")
    return re.compile(r"(?i)(" + Q + key + Q + ")" + SEP + "(?=" + NOT_PH + ")" + VALUE)


RULES = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S),
     "<private key>"),
    ("secret header", re.compile(r"(?im)^(\s*(?:proxy-)?(?:authorization|cookie|set-cookie|x-[\w-]*(?:token|key|secret|auth)"
                                 r"[\w-]*)\s*:\s*)" + NOT_PH + r"(?!<redacted>\s*$)\S.*$"), r"\1<redacted>"),
    ("url credentials", re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)" + NOT_PH + r"[^/\s:@<]+:[^/\s@]+@"), r"\1<credentials>@"),
    ("bearer token", re.compile(r"(?i)\b(bearer|basic)(\s+)" + NOT_PH + r"[A-Za-z0-9._~+/=-]{4,}"), r"\1\2<token>"),
    ("token word", re.compile(r"(?i)\b(token)(\s+)" + NOT_PH + r"(?=\S*\d)[A-Za-z0-9._~+/=-]{12,}"), r"\1\2<token>"),
    ("bot token", re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}"), "<bot token>"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"), "<jwt>"),
] + [(kind, rx, "<%s>" % kind) for kind, rx in scan.SHAPES if kind != "password or key"] + [
    ("api key", re.compile(r"\b(?:lin_api_|xai-|gsk_|hf_|npm_|pypi-|glpat-|dop_v1_|re_)[A-Za-z0-9_-]{16,}"), "<api key>"),
    ("e-mail", re.compile(r"(?:\"(?:[^\"\\\r\n]|\\.)+\"|[\w.%+-]+)@[\w.-]+\.[^\W\d_]{2,}"), "<email>"),
    ("secret pair", _pair(SECRET_WORDS), r"\1\2<redacted>"),
    # a secret as a name/value pair: {"name": "API_KEY", "value": "..."} and YAML - name: X / value: ...
    ("secret name/value", re.compile(r"(?i)(" + Q + r"name" + Q + r"\s*[:=]\s*" + Q + r"(?:[\w-]*[_.-])?" + SECRET_WORDS
                                     + r"s?(?:[_.-][\w.-]*)?" + Q + r"\s*,?\s*(?:-\s*)?" + Q + r"value" + Q
                                     + r"\s*[:=]\s*)" + NOT_PH + VALUE), r"\1<redacted>"),
    ("secret flag", re.compile(r"(?i)(?<![\w-])(--?[a-z-]*" + SECRET_WORDS + r"[a-z-]*(?:=|\s+))" + NOT_PH + VALUE), r"\1<redacted>"),
    ("account id", _pair(ID_KEYS), r"\1\2<id>"),
    ("id flag", re.compile(r"(?i)(?<![\w-])(--?(?:[a-z]+-)*(?:id|uid|user|username|handle|login|e?mail|account|chat|phone)(?:=|\s+))"
                           + NOT_PH + VALUE), r"\1<id>"),
    ("labelled id", re.compile(r"(?i)\b((?:chat|user|channel|group|account|sender|telegram|tg|tenant|customer|client)"
                               r"[ _-]?id\s*#?\s*)" + NOT_PH + r"(-?\d+)\b"), r"\1<id>"),
    ("prose id", re.compile(r"(?i)\b((?:chat|user|channel|group|account|sender|telegram|tg)(?:[ _-]?id)?\s*#?\s*)"
                            + NOT_PH + r"(-?\d{5,})\b"), r"\1<id>"),
    ("home path", re.compile(r"(?i)((?:[a-z]:)?[\\/]+(?:users|home|var[\\/]+home)[\\/]+|(?<![\w.])[\\/]root[\\/]+|"
                             r"(?<![\w/])~(?=[A-Za-z]))" + NOT_PH + r"((?:[^/\\\s'\"<>:]+ )+[^/\\\s'\"<>:]+(?=[\\/])|[^/\\\s'\"<>:]+)"),
     r"\1<user>"),
    ("uuid", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    ("long hex", re.compile(r"\b[0-9a-fA-F]{24,}\b"), "<hex>"),
    ("long token", re.compile(r"(?<![\w/.-])(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{32,}"), "<long value>"),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?\b"), "<iban>"),
    ("tax id", re.compile(r"\b\d{8}-\d-\d{2}\b"), "<tax id>"),
    ("phone", re.compile(r"(?<![\w.])\+\d[\d ()-]{7,}\d"), "<phone>"),
    ("long number", re.compile(r"(?<![\w.-])-?\d{9,}(?![\w.])"), "<number>"),
]
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
IPV6 = re.compile(r"(?<![0-9A-Fa-f:.])\[?((?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?:%[\w.]+)?)\]?(?![\w:])")
DOC_NETS = [ipaddress.ip_network(n) for n in ("127.0.0.0/8", "0.0.0.0/32", "192.0.2.0/24",
                                              "198.51.100.0/24", "203.0.113.0/24", "::1/128", "::/128",
                                              "2001:db8::/32")]


def _ip6(m):
    try:
        ip = ipaddress.ip_address(m.group(1).split("%")[0])
    except ValueError:
        return m.group(0)  # 12:34:56 is a time, not an address
    return m.group(0) if any(ip in n for n in DOC_NETS if n.version == 6) else "<ip>"


def _ip(m):
    try:
        ip = ipaddress.ip_address(m.group(0))
    except ValueError:
        return m.group(0)  # 1.2.3.999 is a version string, not an address
    return m.group(0) if any(ip in n for n in DOC_NETS) else "<ip>"


def _name_rx(name):
    parts = [re.escape(p) for p in re.split(r"[\s_.-]+", name.strip()) if p]
    return re.compile(r"(?<!\w)" + r"[\s_.-]*".join(parts) + r"(?!\w)", re.I) if parts else None


# A PART of a name that is an ordinary word is not private: "media-agent" must not make "agent" in
# the footer a stop. Whole names still match; an e-mail's domain keeps its own label ("example-family"
# of example-family.com) but not its TLD or a mail provider ("com", "gmail" would stop every report).
COMMON_PARTS = {"agent", "assistant", "mentat", "bot", "admin", "server", "box", "user", "root", "home",
                "dev", "main", "test", "the", "and", "for", "you", "mail", "fleet", "brain", "engine",
                "gmail", "googlemail", "outlook", "hotmail", "yahoo", "icloud", "proton", "protonmail", "live",
                "gmx", "freemail", "citromail", "users", "noreply"}


def _parts(name):
    local, _, domain = name.partition("@")
    labels = re.split(r"[\s_.-]+", local) + (domain.split(".")[:-1] if domain else [])
    return {p for p in labels if p.lower() not in COMMON_PARTS}


def name_patterns(names):
    """Whole-word patterns, longest first; names under 3 characters would wreck ordinary words."""
    out = []
    every = {n.strip() for n in names if n} | {part for n in names if n for part in _parts(n)}
    for n in sorted({n for n in every if len(n) >= 3}, key=len, reverse=True):
        rx = _name_rx(n)
        if rx:
            out.append(rx)
    return out


def redact(text, names=()):
    counts = {}
    for kind, rx, repl in RULES:
        text, n = rx.subn(repl, text)
        if n:
            counts[kind] = counts.get(kind, 0) + n
    before = text.count("<ip>")
    text = IPV6.sub(_ip6, IPV4.sub(_ip, text))
    if text.count("<ip>") > before:
        counts["ip address"] = text.count("<ip>") - before
    for rx in name_patterns(names):
        text, n = rx.subn("<name>", text)
        if n:
            counts["private name"] = counts.get("private name", 0) + n
    return text, counts


def residue(text, names=()):
    """Kinds still present after redaction (a non-empty list = do not post)."""
    left = [kind for kind, rx, _ in RULES if rx.search(text)]
    if any(_ip(m) == "<ip>" for m in IPV4.finditer(text)) or any(_ip6(m) == "<ip>" for m in IPV6.finditer(text)):
        left.append("ip address")
    if any(rx.search(text) for rx in name_patterns(names)):
        left.append("private name")
    return left
