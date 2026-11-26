"""Test fixtures for the upgrade: the install kinds, made from scratch (no real repo's content).

pre05(root): a brain from before the .mentat/ layout, shaped like the ones in the wild: its own
AGENTS.md without product blocks, CLAUDE.md, the notes in docs/ with _meta.md indexes, business
data and code of its own, a SessionStart hook of its own, a vendored anytime_engine/ 0.2.2 with
VENDORED.md (including a module the 0.3 engine retired), no mentat.json, no .mentat/.
fake_source(dir, tag): a Mentat source repo whose engine/ is this monorepo's real engine release.
"""
import json
import os
import pathlib
import shutil
import subprocess

_UP = pathlib.Path(__file__).resolve().parents
# the engine release: engine/release/ in the dev monorepo, engine/ at the root of the public tree
ENGINE = next((p for p in (_UP[4] / "engine" / "release", _UP[2] / "engine") if (p / "sync-to.sh").is_file()),
              _UP[2] / "engine")
AGENTS = """# Próbaterem — asszisztens

Egy kis próbatermet segítek: két szoba, órás foglalás. A tulajdonossal beszélek.

## Amit NEM csinálok

- Nem írok ügyfélnek. Megfogalmazom, a tulajdonos küldi.

## Hol mi van

| Hol | Mi |
|---|---|
| `docs/decisions/` | Az eldöntött kérdések |
| `data/rules.yaml` | A foglalási szabályok |
"""
FILES = {
    "AGENTS.md": AGENTS,
    "CLAUDE.md": "@AGENTS.md\n",
    ".gitignore": ".env\n__pycache__/\n",
    "docs/_meta.md": "# docs/\n\nA tudástár.\n",
    "docs/decisions/_meta.md": "# döntések\n",
    "docs/decisions/001-lemondas.md": "# 001 — Lemondás\n\nA lemondási határidő 48 óra. Kód: KEKCSIGA-48.\n",
    "docs/business/_meta.md": "# üzlet\n",
    "docs/business/szobak.md": "# Szobák\n\nA nagy terem 55 nm.\n",
    "data/rules.yaml": "lemondas_ora: 48\n",
    "scripts/booking/rules.py": "LEMONDAS = 48\n",
    ".claude/settings.json": json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": "bash .claude/hooks/session-start.sh"}]}]}}, indent=2) + "\n",
    ".claude/hooks/session-start.sh": "#!/usr/bin/env bash\necho helyzet\n",
    "anytime_engine/__init__.py": '"""old vendored engine"""\n__version__ = "0.2.2"\n',
    "anytime_engine/reducer.py": "def reduce():\n    return []\n",
    "anytime_engine/calendar_reconcile.py": "X = 1\n",
    "anytime_engine/VENDORED.md": "# VENDOROLT MÁSOLAT — NE SZERKESZD KÉZZEL\n\nVerzió: 0.2.2\nSync: 2026-08-26\n",
}


def git(root, *args, env=None):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")


def write(root, files):
    for rel, text in files.items():
        p = pathlib.Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def commit(root, msg="state", env=None):
    git(root, "add", "-A", "--", ".", ":!.mentat", env=env)  # an old brain never had .mentat/
    git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", msg, env=env)


def init(root, env=None):
    """A repo with its own git identity: the gate's empty HOME has none."""
    git(root, "init", "-q", env=env)
    git(root, "config", "user.name", "Teszt", env=env)
    git(root, "config", "user.email", "teszt@example.com", env=env)


def pre05(root, env=None, engine=True):
    init(root, env)
    write(root, {k: v for k, v in FILES.items() if engine or not k.startswith("anytime_engine/")})
    commit(root, "old brain", env)
    return root


def install_tools(root, manifest_dir, version):
    """What step 2 of UPGRADE.md leaves: the tools in .mentat/bin/ (dev tree: no release.json list)."""
    dst = pathlib.Path(root) / ".mentat" / "bin"
    shutil.copytree(manifest_dir, dst, ignore=shutil.ignore_patterns("test_*", "__pycache__", "_*"))
    bek = pathlib.Path(manifest_dir).parent / "bekotes"
    shutil.copytree(bek, dst / "bekotes", ignore=shutil.ignore_patterns("test_*", "__pycache__"))
    for f in ("mentat_roles.py", "mentat_manifest.py", "mentat_rules.py"):
        shutil.copy(pathlib.Path(manifest_dir) / f, dst / "bekotes" / f)
    return dst


def fake_source(where, tag, env=None):
    """A git repo laid out like the public one (engine/ = engine/release), tagged."""
    src = pathlib.Path(where) / "mentat"
    shutil.copytree(ENGINE, src / "engine", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    for f in ("LICENSE", "NOTICE"):
        if not (src / "engine" / f).exists():
            (src / f).write_text(f + "\n", encoding="utf-8")
    git(src, "init", "-q", env=env)
    commit(src, "release", env)
    git(src, "tag", tag, env=env)
    return src


def isolated_env(home):
    env = dict(os.environ, HOME=str(home), GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.path.join(str(home), "gitconfig"))
    for k in ("CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR", "CLAUDECODE"):
        env.pop(k, None)
    return env
