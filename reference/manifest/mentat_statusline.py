#!/usr/bin/env python3
"""The Mentat status line: who, model, context, usage, folder, tip. Stdlib, no network; missing data = no field.

    python3 mentat_statusline.py               # Claude Code statusLine: JSON on stdin, one line out
    python3 mentat_statusline.py --whoami      # the same, several lines (for /whoami on Desktop)
"""
import json
import os
import pathlib
import sys
for _s in (sys.stdin, sys.stdout, sys.stderr):  # Windows: a pipe is the ANSI code page, not UTF-8
    getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")

ROLES = {"hu": {"asszisztens": "asszisztens", "fejleszto": "fejlesztő", "consultant": "consultant",
                "backlog-manager": "PM", "kiado": "kiadó", "flottamenedzser": "flottamenedzser"},
         "en": {"asszisztens": "assistant", "fejleszto": "developer", "consultant": "consultant",
                "backlog-manager": "PM", "kiado": "release agent", "flottamenedzser": "fleet manager"}}
_cmd = lambda root, name: (root / ".claude" / "commands" / name).is_file()  # noqa: E731
TIPS = (("/mentat", lambda r, f: _cmd(r, "mentat.md")), ("/whoami", lambda r, f: _cmd(r, "whoami.md") and not
        _cmd(r, "mentat.md")), ("/fleet:roster", lambda r, f: f))  # installed only; /mentat supersedes /whoami
TEXT = {"hu": {"pa": "személyi asszisztens", "fleet": "%s flottája",
               "labels": ("Ágens", "Szerep", "Flotta", "Modell", "Kontextus", "Keret", "Mappa", "Tipp")},
        "en": {"pa": "personal assistant", "fleet": "%s's fleet",
               "labels": ("Agent", "Role", "Fleet", "Model", "Context", "Usage", "Folder", "Tip")}}


def _json(path):
    try:
        got = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def _find_root(start):
    p = pathlib.Path(start)
    for d in [p, *p.parents][:6]:
        if (d / "mentat.json").is_file():
            return d
    return p


def _registry(env=os.environ, home=None):
    """fleet.registry_dir() without importing fleet: FLEET_REGISTRY, then ~/.config/fleet/registry."""
    if env.get("FLEET_REGISTRY", "").strip():
        return pathlib.Path(env["FLEET_REGISTRY"].strip()).expanduser()
    try:
        raw = (pathlib.Path(home or pathlib.Path.home()) / ".config/fleet/registry").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return pathlib.Path(raw).expanduser() if raw else None


def _fleet_entry(fmap, name, root):
    agents = fmap.get("agents") if isinstance(fmap.get("agents"), dict) else {}
    for key, e in agents.items():
        home = (e.get("home") or {}) if isinstance(e, dict) else {}
        if key.lower() == (name or "").lower() or str(home.get("repo", "")).split("/")[-1] == root.name:
            return key, e
    return None, None


def _role(r, lang):
    return r.get("custom") if isinstance(r, dict) else ROLES[lang].get(r, r)


def _branch(start):
    """(branch, worktree name) from .git without running git."""
    for d in [pathlib.Path(start), *pathlib.Path(start).parents][:8]:
        g = d / ".git"
        if g.is_dir() or g.is_file():
            gitdir, wt = (g, None) if g.is_dir() else (None, d.name)
            if gitdir is None:
                line = g.read_text(encoding="utf-8", errors="replace").strip()
                gitdir = (d / line[8:]).resolve() if line.startswith("gitdir: ") else None
            try:
                head = (gitdir / "HEAD").read_text(encoding="utf-8").strip() if gitdir else ""
            except OSError:
                head = ""
            return (head[16:] if head.startswith("ref: refs/heads/") else head[:7] or None), wt
    return None, None


def facts(data, env=os.environ, home=None):
    cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd") or os.getcwd()
    root = _find_root((data.get("workspace") or {}).get("project_dir") or cwd)
    manifest = _json(root / "mentat.json")
    lang = {"en": "en"}.get((manifest.get("agent") or {}).get("language"), "hu")
    name = (manifest.get("agent") or {}).get("name")
    roles = manifest.get("roles") if isinstance(manifest.get("roles"), dict) else {}
    names = [roles.get("default")] + [r for r in roles.get("installed") or [] if r != roles.get("default")]
    out = {"lang": lang, "name": name, "roles": [_role(r, lang) for r in names if r]}
    reg = _registry(env, home)
    fmap = _json(reg / "fleet-map.json") if reg else {}
    key, entry = _fleet_entry(fmap, name, root)
    if entry:
        out["name"] = name or key
        fleet_roles = [entry.get("custom_role") if entry.get("main_role") == "custom" else entry.get("main_role")]
        fleet_roles += entry.get("extra_roles") or []
        out["roles"] += [x for x in (_role(r, lang) for r in fleet_roles if r) if x and x not in out["roles"]]
        out["fleet"] = TEXT[lang]["fleet"] % fmap["owner"] if fmap.get("owner") else None
    out["roles"] = out["roles"][:3] or [TEXT[lang]["pa"]]
    model = data.get("model") or {}
    out["model"] = model.get("display_name") or model.get("id")
    ctx = (data.get("context_window") or {}).get("used_percentage")
    out["context"] = "ctx %d%%" % round(ctx) if isinstance(ctx, (int, float)) else None
    limits = data.get("rate_limits") or {}
    usage = ["%s %d%%" % (k, round(w["used_percentage"])) for k, w in (("5h", limits.get("five_hour")),
             ("7d", limits.get("seven_day"))) if isinstance(w, dict) and isinstance(w.get("used_percentage"), (int, float))]
    out["usage"] = " · ".join(usage) or None
    wt = data.get("worktree") or {}
    branch, wt_name = _branch(cwd)
    branch, wt_name = wt.get("branch") or branch, wt.get("name") or wt_name
    out["folder"] = _short(cwd, home) + (" (%s)" % " · ".join(x for x in (branch, wt_name and "wt:" + wt_name) if x)
                                         if branch or wt_name else "")
    out["tip"] = " · ".join(cmd for cmd, here in TIPS if here(root, bool(entry))) or None
    return out


def _short(path, home=None):
    p, h = str(path), str(home or pathlib.Path.home())
    p = "~" + p[len(h):] if p == h or p.startswith(h + os.sep) else p
    parts = p.split(os.sep)
    return p if len(p) <= 32 or len(parts) <= 3 else os.sep.join(["…"] + parts[-2:])


def line(f):
    who = " · ".join(x for x in (f["name"], "+".join(f["roles"]), f.get("fleet")) if x)
    return " │ ".join(x for x in (who, f["model"], f["context"], f["usage"], f["folder"], f["tip"]) if x)


def whoami(f):
    labels = TEXT[f["lang"]]["labels"]
    values = (f["name"], "+".join(f["roles"]), f.get("fleet"), f["model"], f["context"], f["usage"], f["folder"], f["tip"])
    return "\n".join("%s: %s" % (k, v) for k, v in zip(labels, values) if v)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        data = {} if "--whoami" in argv else json.loads(sys.stdin.read() or "{}")
    except ValueError:
        data = {}
    try:  # a status line never fails the session: at worst it prints nothing, exit 0
        f = facts(data if isinstance(data, dict) else {})
        print(whoami(f) if "--whoami" in argv else line(f))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
