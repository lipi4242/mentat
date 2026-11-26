"""`fleet upgrade <repo> --pr [--place] [--rules]`: a generált fájlok PR-ként.
Kilépés: 0 kész / nincs teendő · 1 hiba · 2 nincs térkép.
Alap: --place (a fleet-place blokk). A --rules külön ágon és külön PR-ban megy, mert a szabályfájl a
cél-repó recept szerint más sáv lehet (emberi jóváhagyású sáv nem utazik mással együtt)."""
from __future__ import annotations
import json
from pathlib import Path

from fleet import deliver, fleet_place_file as pf, rules_render
from fleet.fleet_place_cli import _load


def place_renderer(mode: str) -> deliver.Renderer:
    """A fleet-place blokk renderelése az AGENTS.md-be (a cserélhető „mit” egyik példánya)."""
    def render(work: Path, fmap: dict, agent: str) -> dict:
        path = work / "AGENTS.md"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return {"AGENTS.md": pf.place(text, pf.block(fmap, agent, mode))}
    return render


def _agent(a, repo: Path) -> str | None:
    if a.agent:
        return a.agent
    try:
        return json.loads((repo / ".claude" / "fleet.json").read_text())["agent"]
    except (OSError, ValueError, KeyError):
        return None


def run(a, git=deliver.sh, gh=deliver.sh) -> int:
    repo = Path(a.repo).resolve()
    agent = _agent(a, repo)
    if not agent:
        print("fleet: az ágens neve ismeretlen (nincs .claude/fleet.json); add meg: --agent")
        return 1
    jobs = []
    if a.place or not a.rules:
        try:
            fmap, errs = _load()
        except (OSError, ValueError) as e:
            print(f"fleet: {e}")
            return 2
        if errs:
            print(f"fleet: a térkép nem érvényes ({len(errs)} hiba); előbb: fleet map validate")
            return 1
        if agent not in fmap["agents"]:
            print(f"fleet: {agent}: nincs a térképen")
            return 1
        jobs.append(("place", fmap, place_renderer(a.mode), "chore(fleet): fleet-place blokk frissítése",
                     "A flottatérképből generált `fleet-place` blokk (fleet map render). Csak ez a blokk változik."))
    if a.rules:
        jobs.append(("rules", {}, rules_render.render, "chore(fleet): flotta-szabályfájl frissítése",
                     "A `.claude/rules/fleet.md` és a manifest `rules_sha` mezője a telepített sablonra frissül."))
    bad = False
    for kind, fmap, render, title, body in jobs:
        r = deliver.deliver(repo, fmap, agent, render, branch=f"fleet/{kind}-{agent}",
                            title=f"{title} ({agent})", body=body, base=a.base, git=git, gh=gh)
        print(json.dumps(dict(r, kind=kind), ensure_ascii=False))
        bad = bad or r["status"] == "error"
    return 1 if bad else 0
