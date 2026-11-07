"""Test fixture: an agent repo with a brain, one business and the VENDORED tools.

The tools are copied exactly as BEKOTES.hu.md step 0 downloads them, so the
tests also prove that the curl list is complete.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE.parent
BIZ = "agy/business/zoldag"
CITED = {
    "terkep.md": "# Térkép\n\n- A webshop forrása a zoldag-web (forrás: zoldag-web:README.md)\n",
    "business.md": "# Business\n\n- Kertészet, domain a régi memóriából (forrás: memoria:projekt-domain.md)\n",
    "rendszerek.md": "# Rendszerek\n\n- Dokumentáció (forrás: zoldag-web:docs/a.md)\n",
    "emberek.md": "# Emberek\n\n- A jegyeket Bea viszi (forrás: linear:ZOL-1)\n",
}


def git(repo, *a, env=None):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@example.com",
                    *a], check=True, capture_output=True, env=env)


def vendor_list(lang="hu"):
    text = (HERE / ("BEKOTES.%s.md" % lang)).read_text(encoding="utf-8")
    m = re.search(r"^for f in (.+?); do$", text, re.M | re.S)
    return m.group(1).replace("\\\n", " ").split()


def step0(lang="hu"):
    text = (HERE / ("BEKOTES.%s.md" % lang)).read_text(encoding="utf-8")
    return re.search(r"^## 0\..*?```bash\n(.*?)```", text, re.M | re.S).group(1)


def vendor(root, lang="hu"):
    """Run BEKOTES step 0 verbatim in its local-tree mode (REF set: cp, no curl)."""
    fake = root / ".nocurl"
    fake.mkdir(exist_ok=True)
    (fake / "curl").write_text("#!/bin/sh\necho curl-called >&2\nexit 1\n")
    (fake / "curl").chmod(0o755)
    env = dict(os.environ, REF=str(REF), PATH="%s:%s" % (fake, os.environ.get("PATH", "")))
    r = subprocess.run(["bash", "-c", step0(lang)], cwd=root, env=env, capture_output=True, text=True)
    shutil.rmtree(fake)
    assert r.returncode == 0 and not r.stderr and ": " not in r.stdout, r.stdout + r.stderr


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def make_agent(sources_extra=None):
    root = pathlib.Path(tempfile.mkdtemp())
    e = env(root)
    (root / ".home").mkdir()
    git(root, "init", "-q", env=e)
    subprocess.run([sys.executable, str(REF / "manifest" / "mentat_cli.py"), "init-brain",
                    "--name", "zoldag", "--language", "hu", "--brain-root", "agy",
                    "--version", "0.2.0", "--repo", str(root)], check=True, capture_output=True, env=e)
    write(root, ".gitignore", ".mentat/\nmunka/\n.home/\n")
    origin = root / ".home" / "origin" / "zoldag-web"  # the business repo; cloned with $BK klon below
    write(root, ".home/origin/zoldag-web/README.md", "# Zöldág web\n")
    write(root, ".home/origin/zoldag-web/docs/a.md", "doksi\n")
    write(root, ".home/origin/zoldag-web/ugyfelek/private.json", '{"x": 1}\n')
    git(origin, "init", "-q", env=e)
    git(origin, "add", "-A", env=e)
    git(origin, "commit", "-q", "-m", "első", env=e)
    write(root, "munka/regi-memoria/projekt-domain.md", "---\ndescription: domain\n---\nzoldag.example\n")
    write(root, BIZ + "/memoria/projekt-domain.md", "---\ndescription: domain\n---\nzoldag.example\n")
    write(root, "munka/linear.json", json.dumps({
        "exported_at": "2026-01-02T00:00:00Z", "complete": True,
        "issues": [{"id": "1", "identifier": "ZOL-1", "title": "Első", "state": "Todo",
                    "updatedAt": "2026-01-01T00:00:00Z"}]}))
    sources = [
        {"name": "zoldag-web", "kind": "repo", "path": "munka/zoldag-web",
         "tiltott": ["ugyfelek/private.json", "foto-001.jpg"]},
        {"name": "memoria", "kind": "memory", "path": "munka/regi-memoria"},
        {"name": "linear", "kind": "linear", "export": "munka/linear.json", "team": "ZOL"},
        {"name": "levelezes", "kind": "mail", "state": "tiltott", "reason": "csak kérésre"},
    ] + (sources_extra or [])
    write(root, BIZ + "/bekotes.json", json.dumps(
        {"schema": 1, "business": "zoldag", "name": "Zöldág Kertészet", "sources": sources},
        ensure_ascii=False))
    vendor(root)
    r = bk(root, "klon", "--config", BIZ + "/bekotes.json", "--name", "zoldag-web", "--from", str(origin))
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def env(root):
    e = {k: v for k, v in os.environ.items() if k not in ("MENTAT_ROLE", "CLAUDE_PROJECT_DIR", "MENTAT_HEADLESS",
                                                       "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CONFIG_DIR")}
    e["HOME"] = str(root / ".home")
    return e


def bk(root, *args):
    return subprocess.run([sys.executable, str(root / ".mentat/bin/bekotes/bekotes.py"), *args],
                          capture_output=True, text=True, cwd=root, env=env(root))


def leltar(root):
    return bk(root, "leltar", "--config", BIZ + "/bekotes.json", "--out", BIZ + "/leltar.json")


def szerepek(root, *extra):
    return bk(root, "szerepek", "--repo", ".", "--business", "zoldag",
              "--default", "asszisztens", "--install", "backlog-manager,fejleszto", *extra)


def fill_map(root, files=CITED):
    for name, text in files.items():
        write(root, BIZ + "/" + name, text)


def commit_all(root):
    git(root, "add", "-A", env=env(root))
    git(root, "commit", "-q", "--allow-empty", "-m", "bekötés", env=env(root))


def done(root):
    """The whole procedure up to the check: leltar, roles, block, map, commit."""
    for r in (leltar(root), szerepek(root), bk(root, "blokk", "--repo", ".", "--business", "zoldag")):
        assert r.returncode == 0, r.stdout + r.stderr
    fill_map(root)
    commit_all(root)
