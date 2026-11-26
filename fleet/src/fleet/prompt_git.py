"""Kiadott állapotú-e egy prompt-fájl: git-követett, és a munkafa-bájtok, az index és a HEAD
blobja ugyanaz; a HEAD rajta van-e az origin alapágán.

Repó-konfigban megadott parancs nem futhat: a `git status` a .gitattributes szerinti
`filter.<x>.clean` paranccsal hashelné újra a munkafa-fájlt. Ezért csak az indexet és a
HEAD-et olvassuk (ls-files -s, rev-parse HEAD:<út>), a munkafa-fájlt a biztonságos
olvasással olvassuk be, és szűrő nélkül hasheljük (hash-object --no-filters --stdin).
Szűrős vagy sorvég-konverziós repóban ez eltérést ad: az csak jelzés, nem restart.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

from fleet.prompt_safe_read import read_bytes

GIT_TIMEOUT_S = 20


def _git(wd: Path, *args: str, run=subprocess.run) -> list[str] | None:
    try:
        # core.fsmonitor=false: a repó-lokális fsmonitor egy tetszőleges parancsot futtatna a reconcile alatt
        r = run(["git", "-C", str(wd), "-c", "core.fsmonitor=false", *args],
                capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return [x for x in r.stdout.split("\0") if x] if r.returncode == 0 else None


def _base_ref(wd: Path, run) -> str | None:
    """Az origin alapága: origin/HEAD, különben origin/main vagy origin/master; nincs = None.
    Az origin/HEAD csak refs/remotes/origin/ alá mutathat: ha máshová (pl. egy helyi ágra), None."""
    head = _git(wd, "symbolic-ref", "-q", "refs/remotes/origin/HEAD", run=run)
    if head and not head[0].strip().startswith("refs/remotes/origin/"):
        return None
    cands = [head[0].strip()] if head else []
    cands += ["refs/remotes/origin/main", "refs/remotes/origin/master"]
    for ref in cands:
        if _git(wd, "rev-parse", "-q", "--verify", ref + "^{commit}", run=run):
            return ref
    return None


def released(wd: Path, run=subprocess.run) -> bool:
    """A HEAD rajta van-e az origin alapágán (helyi fetch-állapot szerint; hálózat nincs)."""
    ref = _base_ref(Path(wd), run)
    return ref is not None and _git(wd, "merge-base", "--is-ancestor", "HEAD", ref, run=run) is not None


def _blob_id(wd: Path, data: bytes, run) -> str | None:
    """A bájtsor blob-azonosítója a repó objektum-formátumában; szűrő, attribútum nem fut."""
    try:
        r = run(["git", "-C", str(wd), "-c", "core.fsmonitor=false", "hash-object", "--no-filters", "--stdin"],
                input=data, capture_output=True, timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.decode("ascii", "replace").strip() if r.returncode == 0 else None


def _index(wd: Path, paths: list[str], run) -> dict[str, tuple[str, str]] | None:
    """Út → (mód, blob) a 0-s stage-ből; ütközéses (nem 0-s stage) út: ('', '')."""
    rows = _git(wd, "ls-files", "-s", "-z", "--", *paths, run=run)
    if rows is None:
        return None
    out: dict[str, tuple[str, str]] = {}
    for row in rows:
        meta, _, path = row.partition("\t")
        mode, sha, stage = (meta.split(" ") + ["", "", ""])[:3]
        out[path] = (mode, sha) if stage == "0" and path not in out else ("", "")
    return out


def _matches_head(wd: Path, p: str, idx: tuple[str, str], run) -> bool:
    head = _git(wd, "rev-parse", "-q", "--verify", f"HEAD:./{p}", run=run)
    if not head or not idx[1] or head[0].strip() != idx[1]:
        return False                             # nincs a HEAD-ben, vagy az index eltér tőle
    _, data = read_bytes(wd / p)
    return data is not None and _blob_id(wd, data, run) == idx[1]


def git_problems(wd: Path, paths: list[str], run=subprocess.run) -> list[str]:
    """A munkakönyvtáron belüli utak közül azok, amelyek nem kiadott állapotúak."""
    if not paths:
        return []
    idx = _index(wd, paths, run)
    if idx is None:
        return list(paths)                       # nem git-repó / a git nem válaszol
    return [p for p in paths if (p in idx and not _matches_head(wd, p, idx[p], run))
            or (p not in idx and os.path.lexists(wd / p))]
