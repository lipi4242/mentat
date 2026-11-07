#!/usr/bin/env python3
"""bekotes CLI: elokeszit, leltar [--osszefoglalo], klon, memoria stage|lista|alkalmaz, szerepek, blokk, check, olvas grep|show.

Runs from the reference tree or vendored in .mentat/bin/bekotes/ (with the
manifest modules next to it; see BEKOTES.md step 0).
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.append(str(HERE.parent / "manifest"))  # reference tree; vendored copies win

import blokk  # noqa: E402
import check  # noqa: E402
import fajlszuro  # noqa: E402
import elokeszit  # noqa: E402
import hely  # noqa: E402
import klon  # noqa: E402
import leltar  # noqa: E402
import memoria  # noqa: E402
import mentat_manifest as mm  # noqa: E402
import olvas  # noqa: E402
import osszefoglalo  # noqa: E402
import szerepek  # noqa: E402


def cmd_leltar(a):
    if a.osszefoglalo:
        biz = hely.biz_dir(a.repo, olvas._business(pathlib.Path(a.repo), a.business))
        lel = hely.read_json(biz / "leltar.json")
        if lel is None:
            raise hely.HelyError("nincs leltar.json: %s" % biz)
        print("\n".join(osszefoglalo.summary(lel)))
        return
    if not (a.config and a.out):
        raise hely.HelyError("--config és --out kell (vagy --osszefoglalo)")
    cfg = json.loads(pathlib.Path(a.config).read_text(encoding="utf-8"))
    hely.require_no_dotdot(cfg)
    d = leltar.collect(cfg, a.repo)
    pathlib.Path(a.out).write_text(
        json.dumps(d, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def cmd_stage(a):
    if bool(a.config) != bool(a.name):
        raise ValueError("a --config és a --name csak együtt adható meg")
    src, globs = a.src, ()
    if a.config:
        cfg = json.loads(pathlib.Path(a.config).read_text(encoding="utf-8"))
        found = [s for s in cfg.get("sources") or [] if isinstance(s, dict) and s.get("name") == a.name]
        if not found or found[0].get("kind") != "memory":
            raise ValueError("nincs ilyen memória-forrás a configban: %s" % a.name)
        globs = fajlszuro.globs_of(found[0])
        src = src or leltar.resolve(a.repo, found[0].get("path") or "")
    if not src:
        raise ValueError("--src vagy --config/--name kell")
    memoria.stage(src, a.stage, globs)


def parser():
    ap = argparse.ArgumentParser(prog="bekotes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("leltar")
    l.add_argument("--config")
    l.add_argument("--repo", default=".")
    l.add_argument("--out")
    l.add_argument("--osszefoglalo", action="store_true", help="print the summary of an existing leltar.json")
    l.add_argument("--business")
    e = sub.add_parser("elokeszit")
    e.add_argument("--business", required=True)
    e.add_argument("--repo", default=".")
    m = sub.add_parser("memoria").add_subparsers(dest="sub", required=True)
    s = m.add_parser("stage")
    s.add_argument("--src", help="default: the source's path in --config")
    s.add_argument("--config", help="bekotes.json; with --name its tiltott globs are skipped")
    s.add_argument("--name", help="the memory source's name in --config")
    s.add_argument("--repo", default=".")
    s.add_argument("--stage", required=True)
    li = m.add_parser("lista")
    li.add_argument("--stage", required=True)
    al = m.add_parser("alkalmaz")
    al.add_argument("--stage", required=True)
    al.add_argument("--dest", required=True)
    al.add_argument("--approved", required=True)
    sz = sub.add_parser("szerepek")
    sz.add_argument("--lang", choices=("hu", "en"), help="default: mentat.json agent.language")
    sz.add_argument("--default", required=True)
    sz.add_argument("--install", default="")
    sz.add_argument("--kiado", action="store_true", help="install kiado as well")
    k = sub.add_parser("klon")
    k.add_argument("--config", required=True)
    k.add_argument("--name", required=True)
    k.add_argument("--from", dest="from_", required=True, help="URL or local path")
    k.add_argument("--dest", help="default: the source's path")
    k.add_argument("--repo", default=".")
    o = sub.add_parser("olvas").add_subparsers(dest="osub", required=True)
    og = o.add_parser("grep")
    og.add_argument("pattern")
    og.add_argument("--source")
    osh = o.add_parser("show")
    osh.add_argument("ref", help="<source>:<path>")
    for p in (og, osh):
        p.add_argument("--repo", default=".")
        p.add_argument("--business")
    for name in ("szerepek", "blokk", "check"):
        p = sz if name == "szerepek" else sub.add_parser(name)
        p.add_argument("--repo", default=".")
        p.add_argument("--business", required=True)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        if a.cmd == "leltar":
            cmd_leltar(a)
        elif a.cmd in ("szerepek", "blokk", "check", "olvas", "klon", "elokeszit"):
            mods = {"szerepek": szerepek, "blokk": blokk, "check": check, "olvas": olvas, "klon": klon,
                    "elokeszit": elokeszit}
            return mods[a.cmd].run(a)
        elif a.sub == "stage":
            cmd_stage(a)
        elif a.sub == "lista":
            print(memoria.lista(a.stage))
        else:
            memoria.alkalmaz(a.stage, [x for x in a.approved.split(",") if x], a.dest)
    except (hely.HelyError, mm.ManifestError) as e:
        print("Hiba: %s" % e, file=sys.stderr)
        return 1
    except (ValueError, OSError) as e:
        print("Hiba: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
