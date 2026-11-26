"""Térkép-szabályok, amelyek több ágensen átnyúlnak: a jelentési lánc (3)
és a repók gazdái (4). Csak a szerkezetileg épp bejegyzéseket nézik."""
from __future__ import annotations


def check_reports(entries: dict, mk) -> list:
    out = []
    for start in entries:
        seen, cur = [start], start
        while True:
            rt = entries[cur].get("reports_to")
            if not isinstance(rt, str) or not rt.strip():
                break  # hiányzó mezőt a schema már jelezte
            if rt.startswith("human:"):
                break
            if rt in seen:
                cyc = seen[seen.index(rt):] + [rt]
                if start == min(cyc[:-1]):  # egy kör egyszer legyen jelentve
                    out.append(mk("reports-cycle", "jelentési kör: " + " -> ".join(cyc), agent=start))
                break
            if rt not in entries:
                out.append(mk("reports-not-human",
                              f"{start}: a jelentési lánc {cur} -> {rt} ponton nem emberben végződik (az {rt} nincs a térképen)",
                              agent=start))
                break
            seen.append(rt)
            cur = rt
    return out


def check_repos(entries: dict, mk) -> list:
    owners: dict[tuple, list] = {}
    for name, e in entries.items():
        repos = e.get("repos")
        for r in repos if isinstance(repos, list) else []:
            if not isinstance(r, dict) or not isinstance(r.get("repo"), str) or r.get("mode") not in ("owns", "contributes"):
                continue
            key = (r["repo"], r.get("path") or "")
            owners.setdefault(key, [])
            if r["mode"] == "owns":
                owners[key].append(name)
    out = []
    for (repo, path), who in sorted(owners.items()):
        label = repo + (f" ({path})" if path else "")
        if not who:
            out.append(mk("repo-no-owner", f"repo {label}: nincs owns gazdája"))
        elif len(who) > 1:
            out.append(mk("repo-multi-owner", f"repo {label}: több gazda: {', '.join(sorted(who))}"))
    return out
