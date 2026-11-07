#!/usr/bin/env python3
"""F-41: a suggested first-party list (~/.mentat/elsofel.txt), so the identity gate does not ask
about the USER's own places. Nothing is written without the USER's yes.

    python3 .mentat/bin/bekotes/szerep_id_javaslat.py [--repo .]           the suggested lines + source
    python3 .mentat/bin/bekotes/szerep_id_javaslat.py --write LINE [LINE ...]   append the named ones

Sources: the hosts of this repo's git remotes (a GitHub remote becomes `github:<owner>`), the
hosts named in the brain's connectors/ notes, the agent's own deploy places (routes and custom
domains in any wrangler.toml/.json/.jsonc, workers.dev / pages.dev addresses in README, AGENTS
and STATUS files, the admin and fleet host in .mentat/local.json), and the USER's own machines
(Host and HostName in ~/.ssh/config, plain names in ~/.ssh/known_hosts). These only SUGGEST: an
ssh host, a LAN address or a gh login is first party only once the USER approves its line (ciso,
2026-10-24: the agent can write those files). Hosts that are already first party are left out. `--write` is asked from the
USER by the guard (interactive) and denied headless: their yes is the approval, and the lines are
named on the command line, so the USER sees exactly what goes in. Only suggested lines are written.
"""
import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import szerep_id as ident  # noqa: E402
import szerep_id_bash as bash_net  # noqa: E402
import szerep_id_elsofel as elsofel  # noqa: E402

OWN_URL = re.compile(r"\b([a-z0-9][a-z0-9.-]*\.(?:workers\.dev|pages\.dev))\b", re.I)
TOML_HOST = re.compile(r"(?:pattern|custom_domain|zone_name)\s*=\s*\"([^\"/*]+)", re.I)
JSON_HOST = re.compile(r"\"(?:pattern|custom_domain|zone_name)\"\s*:\s*\"([^\"/*]+)\"", re.I)
GH_OWNER = re.compile(r"github\.com[:/]([A-Za-z0-9_.-]+)/")
WRANGLER = {"wrangler.toml", "wrangler.json", "wrangler.jsonc"}
DOCS = {"README.md", "AGENTS.md", "STATUS.md"}
SKIP = {"node_modules", "dist", "build", "vendor", "__pycache__"}


def _d(x):
    return x if isinstance(x, dict) else {}


def _read(p, limit=256 * 1024):
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit] if p.is_file() else ""
    except OSError:
        return ""


def _files(root, names, depth=4):
    """Files with one of `names` under the repo, at most `depth` deep, without build/vendor folders."""
    out = []
    for d, dirs, files in os.walk(root):
        rel = pathlib.Path(d).relative_to(root)
        dirs[:] = sorted(x for x in dirs if x not in SKIP and not x.startswith(".") and len(rel.parts) < depth)
        out += [pathlib.Path(d) / f for f in sorted(files) if f in names]
    return out


def _ssh_hosts(path="~/.ssh/config"):
    """The USER's own machines: `Host` aliases and `HostName`s of ~/.ssh/config (no wildcards)."""
    out = []
    for ln in _read(pathlib.Path(os.path.expanduser(path))).splitlines():
        key, _, rest = ln.strip().partition(" ")
        if key.lower() in ("host", "hostname"):
            out += [h for h in rest.split() if not set(h) & set("*?!") and h.lower() != "github.com"]
    return out


def _known_hosts(path="~/.ssh/known_hosts"):
    """Machines the USER already logged in to (plain known_hosts names; hashed lines stay unknown)."""
    first = [ln.split()[0] for ln in _read(pathlib.Path(os.path.expanduser(path))).splitlines() if ln.strip()[:1] not in ("", "#", "|", "@")]
    hosts = [h[1:].split("]")[0] if h.startswith("[") else h for f in first for h in f.split(",")]
    return [h for h in dict.fromkeys(hosts) if h.lower() not in ("github.com", "gitlab.com", "bitbucket.org")]


def _brain(root):
    try:
        doc = json.loads(_read(root / "mentat.json"))
        b = _d(_d(_d(doc).get("components")).get("brain")).get("root")
    except ValueError:
        b = None
    b = b if isinstance(b, str) else None
    return b or next((d for d in ("agy", "brain") if (root / d).is_dir()), "agy")


def suggest(root):
    """[(line, source)] in a stable order, without what is already first party."""
    root = pathlib.Path(root)
    out = []
    remotes = ident._run(["git", "-C", str(root), "config", "--get-regexp", r"^remote\..*\.url$"]).split()[1::2]
    out += [("github:" + m.group(1).lower(), "git remote") for u in remotes for m in [GH_OWNER.search(u)] if m]
    out += [(h, "git remote") for h in bash_net._git_hosts(str(root))]
    for p in sorted((root / _brain(root) / "connectors").glob("*.md")):
        out += [(h.lower(), "connectors/" + p.name) for h in bash_net.URL.findall(_read(p))]
    for p in _files(root, WRANGLER):
        out += [(h.lower(), str(p.relative_to(root))) for h in TOML_HOST.findall(_read(p)) + JSON_HOST.findall(_read(p))]
    for p in _files(root, DOCS) + [root / ".mentat" / "local.json"]:
        out += [(h.lower(), str(p.relative_to(root))) for h in OWN_URL.findall(_read(p))]
    try:
        loc = _d(json.loads(_read(root / ".mentat" / "local.json") or "{}"))
    except ValueError:
        loc = {}
    url, host = _d(loc.get("admin")).get("url"), _d(loc.get("fleet")).get("host")
    out += [(h.lower(), ".mentat/local.json admin") for h in bash_net.URL.findall(url if isinstance(url, str) else "")]
    out += [(host.lower(), ".mentat/local.json fleet")] if isinstance(host, str) and host else []
    out += [(h.lower(), "~/.ssh/config") for h in _ssh_hosts()] + [(h.lower(), "~/.ssh/known_hosts") for h in _known_hosts()]
    have = elsofel.Allow.load(ident.load(extra_dirs=[str(root)], gh=False))
    seen, keep = set(), []
    for line, src in out:
        if line not in seen and not have.host_ok(line):
            seen.add(line)
            keep.append((line, src))
    return keep


def write(lines, path=elsofel.FILE):
    old = set(elsofel._lines(path))
    new = [x for x in lines if x not in old]
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as f:
        f.writelines(x + "\n" for x in new)
    return new


def main(argv=None):
    p = argparse.ArgumentParser(prog="szerep_id_javaslat.py")
    p.add_argument("--repo", default=".")
    p.add_argument("--write", nargs="+", metavar="LINE")
    a = p.parse_args(argv)
    got = suggest(a.repo)
    if a.write is None:
        for line, src in got:
            print("%s    # %s" % (line, src))
        print("%d javasolt sor; a FELHASZNÁLÓ igenje után: --write <sor> [<sor> ...]" % len(got))
        return 0
    pick = [x for x, _ in got if x in a.write]
    skipped = [x for x in a.write if x not in pick]
    print("beírva: %s" % (", ".join(write(pick)) or "semmi új"))
    if skipped:
        print("STOP nem javasolt sor, kihagyva: %s" % ", ".join(skipped))
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
