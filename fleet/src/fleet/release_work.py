"""Mi számít munkának egy kiadó ágensnél — EGY definíció, tiszta függvényekkel.

Két szint (a kiadó ágensek saját listája, 11-08):

- AKTIVITÁS (a sűrű ütemet tartja, LLM nélkül): nem-draft PR a `release:queue`-ban, élő
  👍-jegy, idegen todo-esemény;
- BEKÜLDÉS (LLM-kör indul): új PR vagy új head-commit a sorban az utolsó beküldés óta, a
  sorból kikerült PR (merge/címke le: a merge utáni lépéseket a tick viszi), a következő
  intervallumon belül lejáró 👍-jegy, idegen todo-esemény, esedékes napi kör.

A változatlanul álló PR (napok óta 👍-ra vár) aktivitás, de nem beküldés: a bejövő 👍-t a
híd azonnal beviszi. Ezért a szöveg sosem kerül ide: csak azonosító, head-SHA, időbélyeg.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

APPROVAL_TTL_H = 36   # a kiadó ágensek lib/approval.py TTL_HOURS-a


def _ts(v) -> float | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _ci(p: dict) -> str:
    nodes = ((p.get("commits") or {}).get("nodes") or [{}])
    roll = ((nodes[-1] or {}).get("commit") or {}).get("statusCheckRollup") or {}
    return str(roll.get("state") or "-")


def fingerprints(prs: list[dict]) -> list[str]:
    """`owner/repo#szám@head:ci:review` a nem-draft, sorban álló PR-okra, rendezve. A CI- és a
    review-állapot benne van: egy változatlan head-en LEFUTÓ CI is munka (Codex, 11-08)."""
    out = set()
    for p in prs:
        if not isinstance(p, dict) or p.get("isDraft"):
            continue
        repo = ((p.get("repository") or {}).get("nameWithOwner") or "").lower()
        if repo and isinstance(p.get("number"), int):
            out.add(f"{repo}#{p['number']}@{p.get('headRefOid') or '?'}:{_ci(p)}:{p.get('reviewDecision') or '-'}")
    return sorted(out)


def queue_reasons(current: list[str], seen: list[str]) -> list[str]:
    """Új / megváltozott PR és a sorból kikerült PR (azonos szám más head-del: egyszer, újként)."""
    cur, old = set(current), set(seen)
    new = sorted(cur - old)
    nums = {f.split("@", 1)[0] for f in cur}
    gone = sorted({f.split("@", 1)[0] for f in old - cur} - nums)
    return [f"új/változott PR: {f}" for f in new] + [f"kikerült a sorból: {g}" for g in gone]


def approvals(state: dict, now: float, horizon_s: float, ttl_h: int = APPROVAL_TTL_H
              ) -> tuple[int, list[str]]:
    """(élő jegyek száma, a horizonton belül lejáró jegyek kulcsai `repo#pr@requested_at`).
    A kulcs a kérdés idejét is viszi: egy jegy egy kérdésére EGYSZER ébresztünk (a hívó
    jegyzi meg, mit jelzett már), az újrakérdezés új kulcs."""
    live, expiring = 0, []
    for repo, rec in ((state or {}).get("repos") or {}).items():
        for pr, j in ((rec or {}).get("approvals") or {}).items():
            if not isinstance(j, dict) or j.get("_csonk") or j.get("consumed") or j.get("approved_by"):
                continue
            at = _ts(j.get("requested_at"))
            if at is None:
                continue
            live += 1
            if at + ttl_h * 3600 <= now + horizon_s:
                expiring.append(f"{repo}#{pr}@{j.get('requested_at')}")
    return live, expiring


def lease_held(state: dict, now: float, ttl_min: int) -> bool:
    """Él-e a kiadó ágens lease-e (egy futó kör tartja): ilyenkor nem küldünk be."""
    rec = (state or {}).get("lease")
    if not isinstance(rec, dict):
        return False
    at = _ts(rec.get("renewed_at") or rec.get("acquired_at"))
    return at is not None and now - at <= ttl_min * 60


def daily_due(daily_at: list[str], tz: str, last_tick_at: float | None, now: float) -> str | None:
    """A legutóbbi esedékes napi kör (ÓÓ:PP), ha azóta nem volt tick; különben None.
    Helyi idő (`tz`), így a nyári/téli átállás nem tolja el."""
    if not daily_at:
        return None
    z = ZoneInfo(tz)
    local = datetime.fromtimestamp(now, z)
    best = None
    for hhmm in daily_at:
        h, m = int(hhmm[:2]), int(hhmm[3:])
        t = local.replace(hour=h, minute=m, second=0, microsecond=0)
        if t > local:
            t -= timedelta(days=1)
        if best is None or t > best[0]:
            best = (t, hhmm)
    if last_tick_at is None or last_tick_at < best[0].timestamp():
        return best[1]
    return None


def foreign(events: list[dict], me: str | None) -> list[dict]:
    """A todo-események, amiket nem az ágens maga írt."""
    return [e for e in events if isinstance(e, dict) and (me is None or e.get("actor_id") != me)]
