"""A térkép egy ágens-bejegyzésének mezőszintű ellenőrzése (szabályok 5, 6, 7)."""
from __future__ import annotations

ROLES = ("asszisztens", "fejleszto", "consultant", "pm", "kiado", "flottamenedzser", "custom")
MODES = ("owns", "contributes")
LANGS = ("hu", "en")


def is_name(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _role_items(name, key, items, mk):
    out = []
    if not isinstance(items, list):
        return [mk("bad-field", f"{name}.{key}: lista kell", agent=name)]
    for i, r in enumerate(items):
        if isinstance(r, dict):
            if not is_name(r.get("custom")):
                out.append(mk("custom-role-missing", f"{name}.{key}[{i}]: a custom elemnek kell nem üres \"custom\" szöveg", agent=name))
        elif r == "custom":
            out.append(mk("custom-role-missing", f"{name}.{key}[{i}]: a bare \"custom\" helyett {{\"custom\": \"név\"}} kell", agent=name))
        elif r not in ROLES:
            out.append(mk("unknown-role", f"{name}.{key}[{i}]: ismeretlen szerep: {r!r}", agent=name))
    return out


def _list_of_dicts(name, key, items, mk, check):
    if not isinstance(items, list):
        return [mk("bad-field", f"{name}.{key}: lista kell", agent=name)]
    out = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            out.append(mk("bad-field", f"{name}.{key}[{i}]: objektum kell", agent=name))
        else:
            out += check(f"{name}.{key}[{i}]", it)
    return out


def check_agent(name, e, ids, mk) -> list:
    if not isinstance(e, dict):
        return [mk("bad-field", f"{name}: a bejegyzésnek objektumnak kell lennie", agent=name)]
    out = []

    def bad(msg):
        out.append(mk("bad-field", f"{name}.{msg}", agent=name))

    role = e.get("main_role")
    if not is_name(role):
        bad("main_role: kötelező szöveg")
    elif role not in ROLES:
        out.append(mk("unknown-role", f"{name}.main_role: ismeretlen szerep: {role!r}", agent=name))
    elif role == "custom" and not is_name(e.get("custom_role")):
        out.append(mk("custom-role-missing", f"{name}: main_role custom, de nincs custom_role", agent=name))
    if "extra_roles" not in e:
        bad("extra_roles: kötelező lista (lehet üres)")
    else:
        out += _role_items(name, "extra_roles", e["extra_roles"], mk)
    if not is_name(e.get("responsibility")):
        bad("responsibility: kötelező, nem üres mondat")
    rt = e.get("reports_to")
    if not is_name(rt):
        bad("reports_to: kötelező (ágensnév vagy human:<név>)")
    elif rt.startswith("human:") and not rt[6:].strip():
        bad("reports_to: a human: után név kell")
    if e.get("lang") not in LANGS:
        bad("lang: hu vagy en")
    home = e.get("home")
    if not isinstance(home, dict) or not (is_name(home.get("repo")) or is_name(home.get("url"))):
        bad("home: kell {repo vagy url, path?}")
    elif "path" in home and not isinstance(home["path"], str):
        bad("home.path: szöveg kell")

    def talk(label, it):
        r = []
        if not is_name(it.get("agent")) or not is_name(it.get("about")):
            r.append(mk("bad-field", f"{label}: kell agent és about", agent=name))
        elif it["agent"] not in ids:
            r.append(mk("dangling-ref", f"{label}: {it['agent']} nem létező ágens", agent=name))
        return r

    def repo(label, it):
        r = []
        if not is_name(it.get("repo")) or it.get("mode") not in MODES:
            r.append(mk("bad-field", f"{label}: kell repo és mode (owns|contributes)", agent=name))
        if "path" in it and not isinstance(it["path"], str):
            r.append(mk("bad-field", f"{label}.path: szöveg kell", agent=name))
        return r

    for key, chk in (("talks_to", talk), ("repos", repo)):
        if key not in e:
            bad(f"{key}: kötelező lista (lehet üres)")
        else:
            out += _list_of_dicts(name, key, e[key], mk, chk)
    return out
