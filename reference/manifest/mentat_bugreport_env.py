"""What a bug report says about the install, and which private names it must never carry.

facts(repo, tools) -> {version, components, installed, parts, install, os, python, node, claude}:
versions and kinds only (no host, path, account or endpoint). private_names(repo, extra_files) ->
the names redaction removes: the OS user, the short host name, git user.name / user.email, the
agent's name, the brain's people/ file names, and every line of the given name files (the default
one is ~/.config/mentat/scrub-names.txt when it exists).
"""
import getpass
import json
import os
import pathlib
import platform
import re
import socket
import subprocess

INSTALLS = {"desktop": "Claude Desktop", "code": "Claude Code on a computer",
            "server": "Server (fleet)", "other": "Other"}
DEFAULT_NAMES = pathlib.Path.home() / ".config/mentat/scrub-names.txt"
PEOPLE_DIRS = ("people", "emberek")
NOT_NAMES = ("root", "user", "localhost", "mentat", "agent", "runner", "ubuntu")


def _json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _out(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"\d+\.\d+(\.\d+)?", p.stdout) if p.returncode == 0 else None
    return m.group(0) if m else None


def _server_checkout():
    src = pathlib.Path(os.environ.get("MENTAT_SRC") or pathlib.Path.home() / "src/mentat")
    return _json(src / "release.json")


def guess_install(local, server):
    entry = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    if local.get("fleet") or server or os.environ.get("FLEET_AGENT"):
        return "server"
    if "desktop" in entry:
        return "desktop"
    if entry or os.environ.get("CLAUDECODE"):
        return "code"
    return "other"


def facts(repo, tools, install=None):
    repo, tools = pathlib.Path(repo), pathlib.Path(tools)
    release, local = _json(tools / "release.json"), _json(repo / ".mentat/local.json")
    manifest, server = _json(repo / "mentat.json"), _server_checkout()
    return {
        "version": release.get("version") or server.get("version") or "unknown",
        "components": {k: v for k, v in (release.get("components") or {}).items() if isinstance(v, str)},
        "server_checkout": server.get("version"),
        "installed": {k: v for k, v in (local.get("installed") or {}).items() if isinstance(v, str)},
        "parts": sorted((manifest.get("components") or {}).keys()),
        "install": INSTALLS.get(install or guess_install(local, server), "Other"),
        "os": "%s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
        "python": platform.python_version(),
        "node": _out(["node", "--version"]),
        "claude": _out(["claude", "--version"]),
    }


def environment_text(f):
    lines = ["Mentat: %s" % f["version"]]
    if f["components"]:
        lines.append("components: " + ", ".join("%s %s" % kv for kv in sorted(f["components"].items())))
    if f["installed"]:
        lines.append("installed: " + ", ".join("%s %s" % kv for kv in sorted(f["installed"].items())))
    if f["server_checkout"]:
        lines.append("server checkout: %s" % f["server_checkout"])
    if f["parts"]:
        lines.append("parts in this agent: " + ", ".join(f["parts"]))
    lines.append("OS: %s · Python %s · Node %s · Claude Code %s"
                 % (f["os"], f["python"], f["node"] or "-", f["claude"] or "-"))
    return "\n".join(lines)


def _git(repo, key):
    try:
        p = subprocess.run(["git", "-C", str(repo), "config", key], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout.strip() or None


def private_names(repo, extra_files=()):
    repo = pathlib.Path(repo)
    names = set()
    try:
        names.add(getpass.getuser())
    except (KeyError, OSError):
        pass
    names.add(socket.gethostname().split(".")[0])
    for key in ("user.name", "user.email"):
        v = _git(repo, key)
        if v:
            names.update([v, v.split("@")[0]])
    manifest = _json(repo / "mentat.json")
    if (manifest.get("agent") or {}).get("name"):
        names.add(manifest["agent"]["name"])
    root = ((manifest.get("components") or {}).get("brain") or {}).get("root") or "brain"
    for d in PEOPLE_DIRS:
        folder = repo / root / d
        for p in sorted(folder.glob("*.md")) if folder.is_dir() else []:
            if not p.name.startswith("_"):
                names.add(p.stem)
    for f in list(extra_files) + ([DEFAULT_NAMES] if DEFAULT_NAMES.is_file() else []):
        try:
            names.update(l.strip() for l in pathlib.Path(f).read_text(encoding="utf-8").splitlines()
                         if l.strip() and not l.lstrip().startswith("#"))
        except OSError:
            continue
    return sorted(n for n in names if n and n.lower() not in NOT_NAMES)
