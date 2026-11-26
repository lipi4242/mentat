"""`fleet secrets put --name KULCS --to <ágens|út> --approval <id>` — egy kulcs értéke stdin-ről.

Gépek közti átadás: `<kiadó parancs> | ssh box 'fleet secrets put --name K --to gurney --approval ID'`.
Az érték kizárólag a stdin-en jön: argv-ben, env-ben, kimenetben, hibaüzenetben, nyugtában nincs.
Terminálról (tty) nem olvas, mert a begépelt érték a képernyőre és a görgetési előzménybe kerülne.
Legfeljebb 64 KB, egy sor (a záró sortörés lekerül); üres stdin = elutasítás. A jóváhagyás tétele
`put:NÉV:stdin:HOVA:MIÉRT` (titok_jovahagy: ≤60 perc, egyszer használható). Az írás a titok_mozgat
útja: env-sor csere/beszúrás, 0600, atomikus, symlinkre nem ír. Nyugta: név, hova, HMAC-lenyomat (boxonkénti sóval), jóváhagyás.
"""
from __future__ import annotations
import re
import sys
import time
from pathlib import Path

from fleet import titok_formatum as F, titok_hely as H, titok_jovahagy as J, titok_mozgat as M
from fleet.titok_jovahagy import Refused

MAX_BYTES = 64 * 1024
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SRC = "stdin"


def read_value(stream) -> str:
    """A stdin egyetlen értéke; minden hiba érték nélküli Refused."""
    if stream is None or stream.isatty():
        raise Refused("a put az értéket csak csőből olvassa (`<kiadó> | fleet secrets put …`), terminálról nem")
    raw = getattr(stream, "buffer", stream).read(MAX_BYTES + 1)
    raw = raw.encode() if isinstance(raw, str) else raw
    if len(raw) > MAX_BYTES:
        raise Refused(f"a stdin több mint {MAX_BYTES // 1024} KB — ez nem egy kulcs értéke")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("a stdin nem UTF-8 szöveg") from None
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    if not text.strip():
        raise Refused("üres stdin: nincs mit beírni")
    if "\n" in text or "\r" in text:
        raise Refused("a stdin többsoros: egy env-sorba egy sor fér")
    return text


def run(name: str, dst_spec: str, approval: str, stream, home: Path | None = None) -> dict:
    home = Path(home or Path.home())
    if not NAME_RE.match(name or ""):
        raise Refused("a kulcsnév betű/szám/aláhúzás (pl. API_TOKEN)")
    J.check(approval, "put", name, SRC, dst_spec, home)
    value = read_value(stream)
    dst = M.dest_file(dst_spec, Path(name), name, home)
    under_home = [p for p in dst.parents if home in p.parents]  # a HOME fölötti rendszer-symlink (pl. /var) nem számít
    if dst.is_symlink() or any(p.is_symlink() for p in under_home):
        raise Refused(f"a cél (vagy egy szülőmappája) symlink: {dst} — symlinkre nem írok")
    M.check_env_value(name, value)  # előbb: a visszautasított érték nem használja el a jóváhagyást
    digest = F.mac(value, H.receipt_salt(home))  # írás előtt: a só hibája után a cél érintetlen
    J.claim(approval, "put", name, SRC, dst_spec, home)
    M._write_env(dst, name, value, home)
    J.consume(approval, "put", name, SRC, dst_spec, home)
    receipt = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "op": "put", "name": name, "from": SRC,
               "to": dst_spec, "dest_path": str(dst), "hmac": digest, "approval": approval}
    M.record(home, receipt)
    return receipt


def cmd_put(a) -> int:
    try:
        r = run(a.name, a.dst, a.approval, sys.stdin)
    except Refused as e:
        print(f"fleet secrets: {e}", file=sys.stderr)
        return 2
    except M.ReceiptFailed as e:
        print(f"fleet secrets: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"fleet secrets: fájlhiba ({type(e).__name__}); a cél nem változott", file=sys.stderr)
        return 1
    print(f"put {r['name']}: stdin → {r['to']} (hmac {r['hmac'][:16]}, nyugta: ~/.mentat/titkok/nyugtak.jsonl)")
    return 0


def add_parser(ss) -> None:
    x = ss.add_parser("put", help="egy kulcs értéke stdin-ről, jóváhagyással (put:NÉV:stdin:HOVA:MIÉRT); "
                                  "érték nem kerül argv-be, kimenetbe, nyugtába")
    x.add_argument("--name", required=True, help="env-kulcsnév")
    x.add_argument("--to", dest="dst", required=True, metavar="ÁGENS|ÚT")
    x.add_argument("--approval", required=True)
    x.set_defaults(fn=cmd_put)
