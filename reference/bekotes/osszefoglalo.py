"""Compact summary of a leltar.json — what the map needs, instead of the raw inventory."""
import fnmatch

KEY_DOCS = ("AGENTS.md", "CLAUDE.md", "README*", "docs/_meta.md", "*/_meta.md")
MAX_PATHS = 8
MAX_SOURCES = 15
MAX_GAPS = 8


def _cap(items, n=MAX_PATHS):
    items = list(items)
    return ", ".join(items[:n]) + (" (+%d)" % (len(items) - n) if len(items) > n else "")


def _key_docs(src):
    docs = [d for d in src.get("docs") or [] if any(fnmatch.fnmatch(d, p) for p in KEY_DOCS)]
    return sorted(set(docs + list(src.get("configs") or [])))


def _detail(src):
    kind = src.get("kind")
    if kind == "repo":
        rel = "; van .release-agent/" if src.get("release_agent") else ""
        return ["    %d fájl, %d commit, dirty=%s%s" % (len(src.get("files") or []), len(src.get("commits") or []),
                                                     str(bool(src.get("dirty"))).lower(), rel),
                "    kulcsfájlok: %s" % (_cap(_key_docs(src)) or "-")]
    if kind == "memory":
        files = src.get("files") or []
        flagged = sum(1 for f in files if f.get("flagged"))
        hidden = sum(1 for f in files if f.get("tiltott") or f.get("symlink"))
        return ["    %d fájl (gyanús: %d, tiltott/symlink: %d)" % (len(files), flagged, hidden)]
    if kind == "linear":
        return ["    %d jegy, teljes export: %s" % (len(src.get("issues") or []),
                                                     "igen" if src.get("complete") else "nem")]
    return []


def summary(lel):
    """Lines of the compact summary (deterministic, no file contents, capped)."""
    out = ["Leltár: %s" % lel.get("business"), "Források:"]
    sources = lel.get("sources") or []
    for s in sources[:MAX_SOURCES]:
        reason = s.get("reason") if s.get("state") != "elérhető" and s.get("reason") else ""
        out.append("- %s (%s): %s%s" % (s.get("name"), s.get("kind"), s.get("state"),
                                        " — %s" % str(reason)[:80] if reason else ""))
        if s.get("state") == "elérhető":
            out += _detail(s)
    if len(sources) > MAX_SOURCES:
        out.append("… +%d további forrás (újra: $BK leltar --osszefoglalo)" % (len(sources) - MAX_SOURCES))
    gaps = lel.get("hianylista") or []
    shown = "; ".join("%s (%s: %s)" % (g.get("name"), g.get("state"), str(g.get("reason"))[:60])
                      for g in gaps[:MAX_GAPS])
    more = " (+%d további)" % (len(gaps) - MAX_GAPS) if len(gaps) > MAX_GAPS else ""
    out.append("hianylista: %s%s" % (shown or "üres", more))
    out.append("kiado_alapnak: %s" % str(bool(lel.get("kiado_alapnak"))).lower())
    return out
