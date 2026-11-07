"""`fleet secrets move|copy --name KULCS --from <ágens|út> --to <ágens|út> --approval <id>`.

Az érték csak ebben a folyamatban él: nem kerül argv-be, kimenetbe, hibaüzenetbe. A cél atomikusan,
0600-zal íródik (mint claude_auth.store_token), symlinket nem hoz létre és symlinkre nem ír.
env-kulcs: a cél env-fájl `KULCS=` sora cserélődik vagy bekerül, a többi sor marad. Egész fájl
(json, pem, ismeretlen): `--name '*'`, a forrásfájl neve marad. move: a forrásból kikerül — de
csak dormant donorból: amíg a donor visszaállítható (retire, zár), copy kell, különben a
visszaállított donor kulcs nélkül indulna.
Nyugta: ~/.mentat/titkok/nyugtak.jsonl (név, honnan, hova, hash8, jóváhagyás, idő) — érték nélkül.
"""
from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path

from fleet import titok_formatum as F, titok_hely as H, titok_jovahagy as J
from fleet.titok_jovahagy import Refused

WHOLE = "*"


def _inventory(home: Path) -> list[dict]:
    try:
        return [f for f in json.loads(H.inventory_path(home).read_text()).get("files", [])
                if f.get("class") != "atirat"]
    except (OSError, ValueError):
        raise Refused("nincs titok-leltár: előbb `fleet secrets scan --agent <ágens>`") from None


def _is_path(x: str) -> bool:
    return "/" in x or x.startswith(("~", "."))


def source_file(spec: str, name: str, home: Path) -> Path:
    if _is_path(spec):
        p = Path(os.path.expanduser(spec))
        if not p.is_file():
            raise Refused(f"a forrásfájl nem létezik: {spec}")
        return p
    hits = [f for f in _inventory(home) if f.get("agent") == spec and
            (name == WHOLE or name in [k["name"] for k in f.get("keys", [])])]
    live = [f for f in hits if not re.search(r"\.(bak|prev|old|orig)([.-]|$)", Path(f["path"]).name)]
    hits = live if len(live) == 1 else hits
    if len(hits) != 1:
        raise Refused(f"a(z) {name} kulcs {len(hits)} fájlban van a(z) {spec} leltárában: add meg a fájl útját")
    return Path(hits[0]["path"])


def dest_file(spec: str, src: Path, name: str, home: Path) -> Path:
    if _is_path(spec):
        p = Path(os.path.expanduser(spec))
        return p / src.name if p.is_dir() else p
    if name == WHOLE:
        return home / ".config" / spec / src.name
    envs = [f for f in _inventory(home) if f.get("agent") == spec and f.get("class") == "env"]
    if len(envs) > 1:
        raise Refused(f"a(z) {spec} ágensnek {len(envs)} env-fájlja van: add meg a cél útját")
    return Path(envs[0]["path"]) if envs else home / ".config" / spec / f"{spec}.env"


def _lines_without(path: Path, name: str) -> list[str]:
    if not path.exists():
        return []
    return [ln for ln in path.read_text().splitlines()
            if (F.ENV_LINE.match(ln) or [None, None])[1] != name]


def _write_env(path: Path, name: str, value: str) -> None:
    if "\n" in value or "\r" in value:
        raise Refused(f"a(z) {name} értéke többsoros: env-sorba nem írható, vidd egész fájlként (--name '*')")
    H.write_atomic(path, "\n".join(_lines_without(path, name) + [f"{name}={value}"]) + "\n")


def owner_agent(spec: str, src: Path, home: Path) -> str | None:
    """Kié a forrás: ágensnév, vagy a leltár szerinti gazdája, vagy a ~/.config/<ágens>/ mappa."""
    if not _is_path(spec):
        return spec
    try:
        for f in _inventory(home):
            if Path(f.get("path", "")).resolve() == src.resolve() and f.get("agent"):
                return f["agent"]
    except Refused:
        pass
    rel = src.resolve().parts
    cfg = (home / ".config").resolve().parts
    return rel[len(cfg)] if rel[:len(cfg)] == cfg and len(rel) > len(cfg) + 1 else None


def guard_move(agent: str | None, is_dormant=None) -> None:
    """move csak dormant ágensből; ismeretlen gazda vagy olvashatatlan registry → elutasít (copy kell)."""
    if agent is None:
        raise Refused("move: a forrás gazdája nem állapítható meg — használj copy-t (a forrás marad)")
    try:
        from fleet.registry import get_agent, is_dormant as _dormant
        entry = get_agent(agent)
        dormant = (is_dormant or _dormant)(entry) if entry else False
    except Exception:  # noqa: BLE001 — sérült/beállítatlan registry: a biztonságos oldal a copy
        dormant = False
    if not dormant:
        raise Refused(f"move: a(z) {agent} nem dormant (visszaállítható még) — használj copy-t; "
                      "move csak a lezárás (registry dormant) után")


def run(op: str, name: str, src_spec: str, dst_spec: str, approval: str, home: Path | None = None) -> dict:
    home = Path(home or Path.home())
    J.check(approval, op, name, src_spec, dst_spec, home)
    src = source_file(src_spec, name, home)
    if op == "move":
        guard_move(owner_agent(src_spec, src, home))
    dst = dest_file(dst_spec, src, name, home)
    if dst.exists() and src.resolve() == dst.resolve():
        raise Refused("a forrás és a cél ugyanaz a fájl")
    if dst.is_symlink():
        raise Refused(f"a cél symlink: {dst} — symlinkre nem írok")
    if name == WHOLE:
        raw = src.read_bytes()
        H.write_atomic(dst, raw)
        h8 = F.fp(raw)
        if op == "move":
            src.unlink()
    else:
        vals = F.values(src) if F.kind(src.read_bytes())[0] == "env" else {}
        if name not in vals:
            raise Refused(f"a(z) {name} kulcs nincs a forrás env-fájljában ({src.name}); "
                          "json/pem fájlt egészben vigyél (--name '*')")
        _write_env(dst, name, vals[name])
        h8 = F.fp(vals[name])
        if op == "move":
            mode = src.stat().st_mode & 0o777
            H.write_atomic(src, "\n".join(_lines_without(src, name)) + "\n", mode)
    J.consume(approval, op, name, src_spec, dst_spec, home)
    receipt = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "op": op, "name": name, "from": src_spec,
               "to": dst_spec, "src_path": str(src), "dest_path": str(dst), "hash8": h8, "approval": approval}
    H.append_line(H.receipts_path(home), json.dumps(receipt, ensure_ascii=False))
    return receipt
