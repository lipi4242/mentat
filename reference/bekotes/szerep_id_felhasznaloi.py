"""Is a verified user-level F-41 gate running in this session? Then the bootstrap gate does not ask
twice (CISO). Decided ONLY from state outside the repo, never from a flag the agent can write:

- the user's settings hook (fleet tarolo.user_gate_active): in CLAUDE_CONFIG_DIR or ~/.claude,
  settings.json PreToolUse, matcher "*" or none, onFailure "block", an existing absolute
  …/identitas-kapu/current/kapu.py followed by --hook;
- the fleet plugin: enabled in that same user settings.json
  (enabledPlugins), its user-scope install only (a project-scope entry belongs to another
  project's sessions), installed outside the repo (plugins/installed_plugins.json installPath), and
  its hooks/hooks.json has the PreToolUse entry ("*", onFailure "block") that runs
  hooks/identitas/kapu.py --hook, which exists.
Stricter than the fleet: a CLAUDE_CONFIG_DIR inside the repo never counts. Known limit: a plugin
enabled only in a project's own settings (the agent can write those) does not count, so there the
USER may be asked twice: once by the plugin, once by this gate.
"""
import json
import os
import re

USER_GATE = re.compile(r"(/\S*identitas-kapu/current/kapu\.py)\s+--hook")
PLUGIN_GATE = re.compile(r"hooks/identitas/kapu\.py\"?\s+--hook")


def _json(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _d(x):
    """A JSON value as a dict, whatever the file holds there (null, a string, a list -> {})."""
    return x if isinstance(x, dict) else {}


def _blocking(pre, rx):
    for e in pre if isinstance(pre, list) else []:
        for h in (e.get("hooks") or []) if isinstance(e, dict) and e.get("matcher") in ("*", None) else []:
            m = rx.search(str(h.get("command", ""))) if isinstance(h, dict) else None
            if m and h.get("onFailure") == "block":
                yield m


def _inside(path, repo):
    p = os.path.realpath(path)
    return p == repo or p.startswith(repo + os.sep)


def _plugin(base, settings, repo):
    installed = _d(_json(os.path.join(base, "plugins", "installed_plugins.json")).get("plugins"))
    for key, on in _d(settings.get("enabledPlugins")).items():
        insts = installed.get(key) if on is True else None
        for inst in insts if isinstance(insts, list) else []:
            if not isinstance(inst, dict) or inst.get("scope") != "user":  # never another project's (CISO #88)
                continue
            home = str(inst.get("installPath") or "")
            if not home or _inside(home, repo):
                continue
            pre = _d(_json(os.path.join(home, "hooks", "hooks.json")).get("hooks")).get("PreToolUse")
            if any(True for _ in _blocking(pre, PLUGIN_GATE)) and \
                    os.path.isfile(os.path.join(home, "hooks", "identitas", "kapu.py")):
                return True
    return False


def user_gate_active(root):
    try:
        return _active(root)
    except Exception:  # noqa: BLE001 - a broken file never makes the gate step back (nor blocks the hook)
        return False


def _active(root):
    base = os.path.realpath(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    repo = os.path.realpath(str(root))
    if _inside(base, repo):
        return False
    settings = _json(os.path.join(base, "settings.json"))
    pre = _d(settings.get("hooks")).get("PreToolUse")
    if any(os.path.isfile(os.path.expanduser(m.group(1))) for m in _blocking(pre, USER_GATE)):
        return True
    return _plugin(base, settings, repo)
