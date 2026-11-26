"""box-upgrade lépés: mely repók `.claude/rules/fleet.md`-je elavult a cél-kódhoz mérve, és (kérésre) repónként PR.

A terv a CÉL-tag sablonjával mér (`git show <cél-sha>:…`); ha az még nem érhető el (legacy elrendezés a
váltás előtt), kimondja, hogy a mérés a váltás után lehetséges. A PR-nyitás opcionális (`--rules-pr`), az
ÚJ checkout `fleet upgrade <repo> --pr --rules` parancsával történik (alfolyamat), és sosem buktatja a
frissítést: ami nem megy, annak az oka a kimenetben áll.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from fleet import rules_state
from fleet.box_agent_plan import ordered
from fleet.box_ctx import Ctx

TMPL = "fleet/templates/rules/fleet.md.tmpl"
INIT = "fleet/src/fleet/__init__.py"


def _show(ctx: Ctx, sha: str, path: str) -> str | None:
    """A fájl a cél-commitból, szó szerint (a záró újsor is számít a hash-ben)."""
    r = ctx.run(["git", "-C", str(ctx.src), "show", f"{sha}:{path}"])
    return r.stdout if r.returncode == 0 else None


def target(ctx: Ctx) -> tuple | None:
    """(sablon, verzió) a cél-kódból, vagy None, ha még nem mérhető."""
    sha = ctx.state.get("target_sha")
    if not sha:
        return None
    tmpl, init = _show(ctx, sha, TMPL), _show(ctx, sha, INIT)
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init or "")
    return (tmpl, m.group(1)) if tmpl and m else None


def _repo(ctx: Ctx, e: dict) -> Path:
    return Path(str(e.get("workdir") or "").replace("%h", str(ctx.home)))


def measure(ctx: Ctx) -> list | None:
    """[(ágens, repó, state)] az elavultakra; None, ha a cél-sablon még nem érhető el."""
    t = target(ctx)
    if t is None:
        return None
    out = []
    for e in ordered(ctx):
        st = rules_state.state(_repo(ctx, e), e["agent"], template=t[0], version=t[1]) if e.get("workdir") else None
        if st and st["outdated"]:
            out.append((e["agent"], _repo(ctx, e), st))
    return out


def plan(ctx: Ctx) -> list:
    stale = measure(ctx)
    if stale is None:
        return ["szabályfájlok: a mérés a checkout-váltás után lehetséges (cél-sablon még nincs a gépen)"]
    if not stale:
        return ["szabályfájlok: minden repóban naprakész"]
    pr = "PR-t nyit (--rules-pr)" if ctx.state.get("rules_pr") else "PR nincs kérve (--rules-pr)"
    return [f"szabályfájlok: {len(stale)} repóban elavult — {pr}"] + [
        f"  {a}: {rules_state.describe(st)}" + ("" if not st["modified"] else " — PR nem nyitható") for a, _, st in stale]


def rollback(ctx: Ctx) -> list:
    return []   # a PR-ek nem vonhatók vissza ezzel a lépéssel; a szabály-PR egy normál PR


def apply(ctx: Ctx) -> None:
    try:
        _apply(ctx)
    except (Exception, KeyboardInterrupt) as e:  # noqa: BLE001 — ez a lépés sosem buktatja a frissítést
        ctx.say(f"szabályfájlok: nem sikerült ({type(e).__name__}: {e})")


def _apply(ctx: Ctx) -> None:
    stale = measure(ctx)
    if stale is None:
        ctx.say("szabályfájlok: nem mérhető (nincs cél-sablon)")
        return
    for agent, repo, st in stale:
        if not ctx.state.get("rules_pr"):
            ctx.say(f"  {agent}: elavult szabályfájl, PR nincs kérve (--rules-pr): {rules_state.describe(st)}")
        elif st["modified"]:
            ctx.say(f"  {agent}: nem nyitok PR-t — helyi módosítás a fleet.md-ben")
        else:
            r = ctx.run([str(ctx.new_fleet), "upgrade", str(repo), "--pr", "--rules", "--agent", agent])
            ctx.say(f"  {agent}: " + _outcome(r))


def _outcome(r) -> str:
    for line in reversed((r.stdout or "").strip().splitlines()):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        return f"{d.get('status')}" + (f" (PR {d['pr']})" if d.get("pr") else "") + (f" — {d.get('reason') or d.get('error')}" if d.get("reason") or d.get("error") else "")
    return f"nem nyitottam PR-t — kód {r.returncode}: {((r.stderr or r.stdout or '').strip().splitlines() or ['nincs kimenet'])[-1]}"
