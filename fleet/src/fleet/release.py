"""A telepített release-tuple: melyik commit, melyik híd- és plugin-verzió fut
ezen a boxon. A Codex F0-review 5. pontja: egy mutálódó checkoutból csak
akkor tudjuk, mi fut, ha valaki felírta.
"""
from __future__ import annotations
import datetime
import json
import subprocess

from fleet import __version__, REPO_ROOT, CONFIG_DIR, PLUGIN_DIR
from fleet.bridge import bridge_version

RELEASE_PATH = CONFIG_DIR / "release.json"


def git_sha() -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True)
        return r.stdout.strip() or None
    except OSError:
        return None


def plugin_version() -> str | None:
    try:
        return json.loads((PLUGIN_DIR / ".claude-plugin" / "plugin.json").read_text()).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def current_tuple() -> dict:
    return {"fleet": __version__, "sha": git_sha(), "bridge": bridge_version(),
            "plugin": plugin_version(),
            "recorded_at": datetime.datetime.now().isoformat(timespec="seconds")}


def record_release() -> dict:
    t = current_tuple()
    RELEASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RELEASE_PATH.write_text(json.dumps(t, indent=2) + "\n")
    return t


def read_release() -> dict | None:
    try:
        return json.loads(RELEASE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
