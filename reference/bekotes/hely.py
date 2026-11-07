"""Where things live: brain root, business folder, the two JSON files, the hook command."""
import json
import pathlib
import re

import mentat_manifest as mm
import mentat_rules as rules

from szerep_hook import GUARD, GUARD_PRE, GUARD_START, HINT  # noqa: E402,F401
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class HelyError(Exception):
    pass


def brain_root(repo):
    root = rules._get(mm.load(repo), "components", "brain", "root")
    if not rules.path_inside_repo(root):
        raise HelyError("nincs érvényes agy-gyökér a mentat.json-ban (components.brain.root)")
    return root


def biz_dir(repo, business):
    if not NAME.fullmatch(business or ""):
        raise HelyError("érvénytelen business-név: %r" % business)
    return pathlib.Path(repo) / brain_root(repo) / "business" / business


def read_json(path):
    """dict, or None if the file is missing or unreadable."""
    try:
        d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def dotdot_errors(cfg):
    """`name.field` for every path field (path, from, export) that climbs with '..';
    the supported forms are ~/… (home-relative) and repo-relative (or a URL for from)."""
    bad = []
    for s in (cfg or {}).get("sources") or [] if isinstance(cfg, dict) else []:
        for field in ("path", "from", "export"):
            v = s.get(field) if isinstance(s, dict) else None
            if isinstance(v, str) and ".." in v.replace("\\", "/").split("/"):
                bad.append("%s.%s" % (s.get("name"), field))
    return bad


def require_no_dotdot(cfg):
    bad = dotdot_errors(cfg)
    if bad:
        raise HelyError("'..' tilos az útvonalban (~/… vagy repó-relatív kell): %s" % ", ".join(bad))


def config(repo, business):
    return read_json(biz_dir(repo, business) / "bekotes.json")


def leltar(repo, business):
    return read_json(biz_dir(repo, business) / "leltar.json")


def language(repo):
    return rules._get(mm.load(repo), "agent", "language") or "hu"
