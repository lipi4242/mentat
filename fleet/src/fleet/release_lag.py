"""11-07: kiadás-lemaradás — régebbi-e a box checkoutja a legújabb publikált kiadásnál.

    check(home=None, run=subprocess.run, now=None) -> (figyelmeztetés | None, nem-mérhető | None, tény | None)

11-07: a boxok 0.5.0-n futottak, miközben a javítások kiadatlanul álltak; senki nem látta. A helyi
oldal `git -C <checkout> describe --tags`; a távoli a publikus repó legnagyobb `v*` tagje
(`git ls-remote --tags`), CACHE_S-ig gyorsítótárazva. Hálózati hiba vagy tag nélküli checkout:
„nem mérhető", soha nem piros. A lemaradás teendő (⚠), nem üzemzavar.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import time
from pathlib import Path

from fleet import REPO_ROOT

CACHE_S = 6 * 3600
TIMEOUT_S = 15
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _ver(tag: str) -> tuple[int, int, int] | None:
    m = TAG.match(tag)
    return tuple(int(x) for x in m.groups()) if m else None


def latest_tag(ls_remote_out: str) -> str | None:
    """Pure: a `git ls-remote --tags` kimenetéből a legnagyobb vX.Y.Z (a ^{} sorok nélkül)."""
    tags = {ln.split("refs/tags/", 1)[1] for ln in ls_remote_out.splitlines() if "refs/tags/" in ln}
    vs = sorted((v, t) for t in tags if not t.endswith("^{}") and (v := _ver(t)))
    return vs[-1][1] if vs else None


def _remote(home: Path, run, now: float) -> str | None:
    from fleet.plugin_source import public_repo
    cache = home / ".config" / "fleet" / "state" / "release-lag.json"
    try:
        c = json.loads(cache.read_text())
        if now - c["at"] < CACHE_S and c.get("latest"):
            return c["latest"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    url = f"https://github.com/{public_repo()}.git"
    try:
        r = run(["git", "ls-remote", "--tags", url], capture_output=True, text=True, timeout=TIMEOUT_S,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired):
        return None
    latest = latest_tag(r.stdout) if r.returncode == 0 else None
    if latest:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"at": now, "latest": latest}))
    return latest


def describe(checkout: Path | None = None, run=subprocess.run) -> str:
    """A checkout `git describe --tags`-e (pl. v0.5.1-3-gabc); hiba vagy tag nélkül ''."""
    try:
        r = run(["git", "-C", str(checkout or REPO_ROOT.parent), "describe", "--tags", "--match", "v*"],
                capture_output=True, text=True, timeout=TIMEOUT_S)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def cached_latest(home: Path | None = None) -> str | None:
    """A legutóbb látott legnagyobb publikus tag, hálózat nélkül (a check gyorsítótárából)."""
    try:
        return json.loads((Path(home or Path.home()) / ".config/fleet/state/release-lag.json").read_text()).get("latest")
    except (OSError, ValueError, AttributeError):
        return None


def check(home: Path | None = None, run=subprocess.run, now: float | None = None,
          checkout: Path | None = None) -> tuple[str | None, str | None, str | None]:
    home, now = Path(home or Path.home()), time.time() if now is None else now
    checkout = checkout or REPO_ROOT.parent
    here = describe(checkout, run)
    base = here.split("-")[0] if here else ""
    if not _ver(base):
        return None, f"kiadás-lemaradás: a checkoutnak ({checkout}) nincs v* tagje — nem mérhető", None
    latest = _remote(home, run, now)
    if not latest:
        return None, "kiadás-lemaradás: a publikus repó tagjei most nem olvashatók — nem mérhető", None
    if _ver(base) < _ver(latest):
        return (f"a box checkoutja ({here}) régebbi a legújabb kiadásnál ({latest}) — a javítások nincsenek "
                f"itt; frissítés: `fleet box-upgrade --to {latest} --dry-run`, utána élesben"), None, None
    return None, None, f"kiadás: {here} (legújabb publikált: {latest})"
