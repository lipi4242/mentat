"""Mi kerül a titok-leltárba (titok_leltar.py) — POZITÍV bizonyítékkal, a fájlmód egyedül soha.

    classify(p) -> "titok" | "atnezendo" | None

11-07 (11-07): a régi szabály minden 0600/0700-as fájlt titoknak vett. A motor mkstemp-pel ír
(→ 0600), a szkriptek gyakran 0700-asok, így a leltárba került a motor állapota, a review-state,
a travel-budget, egy útiterv, a `jobs/todo_poll.py` — és a titok-kapu megtagadta a futtatásukat.
A #48 csak a data/state/*.json-t vette ki (tünet). Most titok az, aminek
- a NEVE az (STRONG: *.env, *.pem, id_*, service-account, credentials; WORD: *key*, *token*,
  *secret*, *credential*, *passw* — kódon és SQL-en kívül),
- a TARTALMA az: privátkulcs-blokk, vagy titok-jellegű nevű kulcs/mező nem triviális értékkel
  (env, JSON, kódban literál `API_KEY = "…"`).
A privát, de bizonyíték nélküli fájl „átnézendő": a leltár kiírja, a kapu NEM tiltja. A unitok
`EnvironmentFile=` fájljai feltétel nélkül titkok (titok_leltar.scan veszi fel őket).
"""
from __future__ import annotations
import re
from pathlib import Path

from fleet import titok_formatum as F

STRONG = re.compile(r"^(\.env.*|.*\.env(\..*)?|.*\.(pem|key|p12|pfx)|id_[a-z0-9]+|.*service[-_]?account.*\.json|"
                    r"\.?credentials.*)$", re.I)
WORD = re.compile(r"key|token|secret|credential|passw", re.I)
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".md", ".rst", ".sh", ".go", ".rs", ".rb",
            ".java", ".html", ".css", ".txt", ".lock", ".sql"}
CODE_SECRET = re.compile(r"""^\s*(?:export\s+)?[A-Za-z_]*(?:key|token|secret|passw|credential)[A-Za-z_]*"""
                         r"""\s*[:=]\s*["'][^"'\s$]{8,}["']""", re.I | re.M)
#: A futásidejű állapot lease-azonosítója, nem hitelesítő (heartbeat `owner_token`).
LEASE_FIELDS = {"owner_token", "lease_token"}
MIN_VALUE = 8


def _shebang(p: Path) -> bool:
    try:
        with open(p, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def _secret_kv(data: dict) -> bool:
    """Titok-jellegű nevű kulcs, nem triviális szöveges értékkel (a lease-azonosító nem az)."""
    return any(F.SECRET_FIELD.search(str(k)) and k not in LEASE_FIELDS and isinstance(v, str)
               and len(v.strip()) >= MIN_VALUE and " " not in v.strip() for k, v in data.items())


def evidence(p: Path) -> tuple[bool, str]:
    """(van-e bizonyíték, formátum-osztály): privát kulcs, vagy titok-nevű kulcs/mező értékkel.
    Érték nem jön ki a függvényből."""
    try:
        raw = p.read_bytes()[:F.MAX]
    except OSError:
        return False, "olvashatatlan"
    cls, data = F.kind(raw)
    if cls == "pem":
        return True, cls
    if cls in ("env", "json") and isinstance(data, dict) and (_secret_kv(data) or "private_key" in data):
        return True, cls
    return bool(CODE_SECRET.search(raw.decode("utf-8", "replace"))), cls


def classify(p: Path) -> str | None:
    name = re.sub(r"\.(bak|prev|old|orig)([.-].*)?$", "", p.name)
    if name.endswith((".example", ".sample", ".template", ".pub")):
        return None
    try:
        private = (p.stat().st_mode & 0o077) == 0
    except OSError:
        return None
    if STRONG.match(name):
        return "titok"
    code = Path(name).suffix.lower() in CODE_EXT or _shebang(p)
    if not code and WORD.search(name):
        return "titok"
    hidden_cfg = p.parent.name in (".mentat", ".thufir") or p.parent.parent.name == ".config"
    if not (private or hidden_cfg):
        return None
    hit, cls = evidence(p)
    if hit:
        return "titok"
    return "atnezendo" if private and not code and cls in ("ismeretlen", "olvashatatlan") else None
