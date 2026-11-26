"""Kézbesítés PR-ként: egy renderelt fájlhalmaz egy új ágon, commit, push, `gh pr create`.

A „mit renderelünk” cserélhető: egy `Renderer` (repó-checkout, térkép, ágens → {relatív út: új szöveg}).
A munka egy ideiglenes git worktree-ben (az origin/<alap> tetején) folyik, a felhasználó checkoutja érintetlen.
A `git` és a `gh` futtatója injektálható (tesztben hamis `gh`). Idempotens: ha a renderelés nem ad
változást, nincs PR; ha az ág tartalma már megegyezik a távolival, nincs push; ha van nyitott PR, a push frissíti.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

class Skip(Exception):
    """A renderelő nem tud (vagy nem szabad) kézbesíteni; az indok a kimenetbe kerül."""


Runner = Callable[[list, Path], tuple]  # (args, cwd) -> (returncode, stdout)
Renderer = Callable[[Path, dict, str], dict]


def sh(args: list, cwd: Path) -> tuple:
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout.rstrip()


def default_base(repo: Path, git: Runner) -> str:
    rc, out = git(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo)
    return out.removeprefix("origin/") if rc == 0 and out else "main"


def labels_for(worktree: Path, changed: list, gh: Runner) -> list:
    """`release:queue` és a változott fájlokra illő sáv (leghosszabb útvonal-előtag) — csak ha a repóban van ilyen címke."""
    rc, out = gh(["gh", "label", "list", "--limit", "200", "--json", "name", "--jq", ".[].name"], worktree)
    have = set(out.split()) if rc == 0 else set()
    want = ["release:queue"]
    try:
        tracks = json.loads((worktree / ".release-agent" / "config.json").read_text()).get("tracks") or {}
    except (OSError, ValueError):
        tracks = {}
    best = max(((len(p), t) for t, c in tracks.items() if isinstance(c, dict)
                for p in c.get("paths", []) if all(f.startswith(p) for f in changed)), default=None)
    if best:
        want.append(f"release:track/{best[1]}")
    return [x for x in want if x in have]


def deliver(repo: Path, fmap: dict, agent: str, render: Renderer, *, branch: str, title: str, body: str,
            base: str | None = None, git: Runner = sh, gh: Runner = sh) -> dict:
    repo = Path(repo)
    git(["git", "fetch", "origin"], repo)
    base = base or default_base(repo, git)
    tmp = Path(tempfile.mkdtemp(prefix="fleet-deliver-"))
    work = tmp / "wt"
    try:
        rc, out = git(["git", "worktree", "add", "-B", branch, str(work), f"origin/{base}"], repo)
        if rc != 0:
            return {"status": "error", "error": f"worktree: {out}"}
        try:
            files = render(work, fmap, agent)
        except Skip as e:
            return {"status": "skipped", "reason": str(e)}
        for rel, text in files.items():
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / rel).write_text(text, encoding="utf-8")
        _, status = git(["git", "status", "--porcelain"], work)
        if not status:
            return {"status": "unchanged"}
        git(["git", "add", "-A"], work)
        changed = git(["git", "diff", "--cached", "--name-only"], work)[1].split()
        rc, out = git(["git", "commit", "-q", "-m", title], work)
        if rc != 0:
            return {"status": "error", "error": f"commit: {out}"}
        _, mine = git(["git", "rev-parse", "HEAD^{tree}"], work)
        rc, theirs = git(["git", "rev-parse", f"origin/{branch}^{{tree}}"], work)
        pushed = not (rc == 0 and theirs == mine)
        if pushed:
            rc, out = git(["git", "push", "--force-with-lease", "origin", branch], work)
            if rc != 0:
                return {"status": "error", "error": f"push: {out}"}
        rc, num = gh(["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number", "--jq", ".[0].number"], work)
        if rc == 0 and num.isdigit():
            return {"status": "updated" if pushed else "up-to-date", "pr": int(num), "files": changed}
        cmd = ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body", body]
        for lab in labels_for(work, changed, gh):
            cmd += ["--label", lab]
        rc, url = gh(cmd, work)
        if rc != 0:
            return {"status": "error", "error": f"gh pr create: {url}"}
        return {"status": "opened", "pr": url, "files": changed}
    finally:
        git(["git", "worktree", "remove", "--force", str(work)], repo)
        shutil.rmtree(tmp, ignore_errors=True)
