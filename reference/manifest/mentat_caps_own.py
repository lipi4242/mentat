"""The agent's own capabilities, read from the inventories that already exist: projects/,
the brain's connectors/ and procedures/, the helper inventory (subagents _meta.md table),
its own engine concern packs, and the MCP servers in .mcp.json (external). No code header
is required: what a file already says (title, first line, tags) is the description.
"""
import json
import pathlib
import re

SUITE_PACKS = {"anytime_cases", "anytime_bekotes", "anytime_calendar"}
HELPERS = ("subagentek", "subagents")


def _read(p):
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _describe(text, fallback):
    head = text.split("\n---", 1)[1] if text.startswith("---") and "\n---" in text else text
    meta = text.split("\n---", 1)[0] if text.startswith("---") else ""
    title = re.search(r"^title: *(.+)$", meta, re.M) or re.search(r"^# +(.+)$", head, re.M)
    tags = re.search(r"^tags: *\[([^\]]*)\]", meta, re.M)
    body = next((ln.strip() for ln in head.splitlines()
                 if ln.strip() and not ln.lstrip().startswith(("#", "---", "<!--"))), "")
    return ((title.group(1).strip().strip('"') if title else fallback),
            [t.strip() for t in tags.group(1).split(",") if t.strip()] if tags else [], body[:200])


def _entry(cid, kind, title, words, desc, path, provenance="own"):
    text = "%s — %s" % (title, desc) if desc else title
    return {"id": cid, "category": kind, "provenance": provenance, "lifecycle": "active",
            "scope": "agent", "summary": {"hu": text, "en": text},
            "intents": {"hu": [title] + words, "en": []}, "own_text": desc,
            "requires": [], "probe": {"own": path}, "entry": path, "enable_steps": [],
            "limits": [], "extends": path, "docs": path}


def _notes(root, brain, folder, kind):
    out = []
    for p in sorted((root / brain / folder).glob("*.md")):
        if p.name != "_meta.md":
            title, tags, desc = _describe(_read(p), p.stem)
            out.append(_entry("own.%s.%s" % (kind, p.stem), "own", title, tags, desc,
                              str(p.relative_to(root))))
    return out


def _names(d):
    """package.json name/description and the wrangler name of one folder."""
    try:
        pkg = json.loads(_read(d / "package.json") or "{}")
        out = [str(pkg.get("description") or ""), str(pkg.get("name") or "")]
    except ValueError:
        out = []
    out += re.findall(r'^\s*name\s*=\s*"([^"]+)"', _read(d / "wrangler.toml"), re.M)
    return out + re.findall(r'"name"\s*:\s*"([^"]+)"', _read(d / "wrangler.jsonc") + _read(d / "wrangler.json"))


def _without_readme(base, d):
    """What a project says about itself without a README: its line in projects/_meta.md, the
    package.json / pyproject.toml description, the wrangler name, and its top folder names."""
    bits = [ln.split(")", 1)[-1].strip(" -—:") for ln in _read(base / "_meta.md").splitlines()
            if "](%s" % d.name in ln]
    bits += re.findall(r'^\s*(?:description|name)\s*=\s*"([^"]+)"', _read(d / "pyproject.toml"), re.M)
    subs = [x for x in sorted(d.iterdir()) if x.is_dir() and not x.name.startswith((".", "_"))
            and x.name not in ("node_modules", "dist", "build")][:8]
    for x in [d] + subs:  # a frontend/ + worker/ project names itself one level down
        bits += _names(x)
    bits += [x.name for x in subs]
    return "; ".join(b.replace("-", " ") for b in bits if b)[:300]


def _projects(root):
    out = []
    base = root / "projects"
    for d in sorted(base.iterdir()) if base.is_dir() else []:
        if d.is_dir() and not d.name.startswith("."):
            doc = next((d / n for n in ("README.md", "_meta.md", "index.md") if (d / n).is_file()), None)
            title, tags, desc = _describe(_read(doc), d.name) if doc else (d.name, [], _without_readme(base, d))
            out.append(_entry("own.project." + d.name, "own", title, [d.name] + tags, desc,
                              "projects/%s/" % d.name))
    return out


def _helpers(root, brain):
    out = []
    for folder in HELPERS:
        for ln in _read(root / brain / folder / "_meta.md").splitlines():
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0] and not set(cells[0]) <= set("-: ") and cells[0] not in ("név", "name"):
                out.append(_entry("own.subagent." + cells[0], "own", cells[0], [cells[2]],
                                  "%s (%s)" % (cells[2], cells[1]), "%s/%s/%s/" % (brain, folder, cells[0])))
    return out


def _concerns(root):
    """Own concern packs: listed in mentat.json, plus a top-level concerns/ (the older layout)."""
    try:
        plugins = json.loads(_read(root / "mentat.json"))["components"]["engine"]["plugins"]
    except (ValueError, KeyError, TypeError):
        plugins = []
    plugins = list(plugins) if isinstance(plugins, list) else []
    if (root / "concerns").is_dir() and "concerns" not in plugins:
        plugins.append("concerns")
    out = []
    for pkg in plugins:
        if pkg in SUITE_PACKS or not isinstance(pkg, str):
            continue
        src = "".join(_read(p) for p in sorted((root / pkg.replace(".", "/")).glob("*.py")))
        found = re.findall(r"Concern\(\s*name\s*=\s*[\"']([^\"']+)[\"'](?:.*?description\s*=\s*[\"']([^\"']*))?",
                           src, re.S)
        desc = "; ".join("%s (%s)" % (n, d) if d else n for n, d in found)
        out.append(_entry("own.concerns." + pkg, "own", pkg, [n.replace("_", " ") for n, _ in found],
                          desc, pkg.replace(".", "/") + "/"))
    return out


def _mcp(root):
    try:
        servers = json.loads(_read(root / ".mcp.json")).get("mcpServers") or {}
    except (ValueError, AttributeError):
        return []
    return [_entry("external.mcp." + n, "external", n, [], "MCP server (.mcp.json)", ".mcp.json", "external")
            for n in sorted(servers)]


def inventory(root, brain):
    root = pathlib.Path(root)
    return (_projects(root) + _notes(root, brain, "connectors", "connector")
            + _notes(root, brain, "procedures", "procedure") + _helpers(root, brain)
            + _concerns(root) + _mcp(root))
