"""`elokeszit`: one call for steps 2-4 — clone missing repos, inventory, memory stage, report.

Idempotent: an existing clone is kept, the inventory is deterministic and the memory
stage is rebuilt. The report is compact (no file contents): the leltar summary, the
memory approval list and the next command. Exit 1 only on a bad config.
"""
import argparse
import contextlib
import io
import json
import pathlib

import fajlszuro as fs
import hely
import klon
import leltar
import memoria
import osszefoglalo

MAX_LIST = 25


def _clone(repo, cfg_path, src):
    path = leltar.resolve(repo, src.get("path") or "")
    if not src.get("from") or (path.exists() and any(path.iterdir())):
        return None
    buf = io.StringIO()
    ns = argparse.Namespace(config=str(cfg_path), name=src["name"], from_=src["from"], dest=None, repo=str(repo))
    try:
        with contextlib.redirect_stdout(buf):
            rc = klon.run(ns)
    except (hely.HelyError, OSError, ValueError) as e:
        return "klón hiba: %s — %s" % (src["name"], e)
    return "klónozva: %s" % src["name"] if rc == 0 else "klón: %s — %s" % (src["name"], buf.getvalue().strip())


def _memory(repo, biz, src):
    stage = pathlib.Path(".bekotes/stage") / src["name"]
    try:
        memoria.stage(leltar.resolve(repo, src.get("path") or ""), pathlib.Path(repo) / stage, fs.globs_of(src))
        lines = memoria.lista(pathlib.Path(repo) / stage).splitlines()
    except (OSError, ValueError) as e:
        return ["Memória (%s): nem olvasható — %s" % (src["name"], type(e).__name__)]
    shown = lines[:MAX_LIST] + (["  … (+%d sor)" % (len(lines) - MAX_LIST)] if len(lines) > MAX_LIST else [])
    dest = (biz / "memoria").relative_to(pathlib.Path(repo).resolve()) if biz.is_absolute() else biz / "memoria"
    return (["Memória-jóváhagyás (%s) — mutasd meg szó szerint a FELHASZNÁLÓnak:" % src["name"]] + shown
            + ["Jóváhagyás után: $BK memoria alkalmaz --stage %s --dest %s --approved <fájl1,fájl2>" % (stage, dest)])


def run(a):
    repo = pathlib.Path(a.repo)
    biz = hely.biz_dir(repo, a.business)
    cfg_path = biz / "bekotes.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        sources = [s for s in cfg["sources"] if isinstance(s, dict) and s.get("name")]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise hely.HelyError("hibás vagy hiányzó %s (%s)" % (cfg_path, type(e).__name__))
    hely.require_no_dotdot(cfg)
    notes = [n for n in (_clone(repo, cfg_path, s) for s in sources
                         if s.get("kind") == "repo" and not s.get("state")) if n]
    lel = leltar.collect(cfg, str(repo))
    (biz / "leltar.json").write_text(json.dumps(lel, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                                     encoding="utf-8")
    report = notes + osszefoglalo.summary(lel)
    state = {s.get("name"): s.get("state") for s in lel.get("sources") or []}
    for s in sources:  # the INVENTORY state decides, not the config
        if s.get("kind") == "memory" and state.get(s["name"]) == "elérhető":
            report += _memory(repo, biz, s)
    report.append("Következő: tudástérkép a fenti összefoglaló alapján (5. lépés); a nyers leltar.json-t ne olvasd, "
                  "részletért: $BK olvas grep|show.")
    print("\n".join(report))
    return 0
