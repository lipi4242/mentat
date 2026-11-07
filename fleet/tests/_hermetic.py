"""Hermetikus tesztfutás: a valódi HOME nem írható célpont.

Minden tesztmodul ELSŐ importja (a `fleet` előtt), mert a `fleet` több
útvonala importkor számolódik (`CONFIG_DIR`, `install.UNIT_DIR`,
`reconcile.STATE_DIR`, …). Az első import a teljes futásra tmp-re állítja a
HOME-ot és az XDG_CONFIG_HOME-ot, és lefényképezi a valódi (indulás előtti)
HOME `.config/fleet` fáját — a `test_zz_hermetic_guard` ezzel veti össze.

2026-10-18: a Mac valódi `~/.config/fleet/registry`-je egy tesztből jött
létre, egy tmp `registry.d`-re mutatva.
"""
from __future__ import annotations
import atexit
import os
import shutil
import tempfile
from pathlib import Path

REAL_HOME = Path(os.environ.get("_FLEET_TEST_REAL_HOME") or os.path.expanduser("~")).resolve()
os.environ["_FLEET_TEST_REAL_HOME"] = str(REAL_HOME)


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Útvonal → (méret, mtime_ns) a `root` alatt; csak olvas."""
    out = {}
    for p in sorted(root.rglob("*")) if root.is_dir() else []:
        try:
            st = p.lstat()
        except OSError:
            continue
        out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return out


def changed(before: dict, after: dict) -> list[str]:
    """What the run changed under GUARDED. The live box's own writers are not test
    writes and are ignored: `state/**/*.lock` (the fleet-reconcile timer rewrites
    reconcile.lock), `maintenance/*` (an operator's `fleet lock`) and `auth-ok/*`
    (the reconcile's auth stamp). 11-07: a kapu a box élő átállása közben futott,
    és ezeket a test írásának vélte — a fleet-sáv minden PR-je piros lett."""
    def live(k: str) -> bool:
        return ((k.startswith("state/") and k.endswith(".lock"))
                or k.split("/", 1)[0] in ("maintenance", "auth-ok"))
    return sorted(k for k in set(after) | set(before) if after.get(k) != before.get(k) and not live(k))


GUARDED = REAL_HOME / ".config" / "fleet"
BEFORE = snapshot(GUARDED)


def claude_settings_stat(paths=None) -> dict[str, tuple[int, int]]:
    """A valódi Claude-gyökerek settings*.json-jainak (méret, mtime_ns)-e — csak stat, tartalmat nem
    olvas. 2026-10-29: egy teszt a fejlesztő ~/.claude-personal/settings.json-jába telepítette a
    titok-kaput egy tmp útvonallal; a tmp törlése után minden Bash/Read hívás elakadt."""
    if paths is None:
        roots = set(REAL_HOME.glob(".claude*"))
        if os.environ.get("CLAUDE_CONFIG_DIR"):  # a pop előtt: a fejlesztő valódi gyökere is
            roots.add(Path(os.environ["CLAUDE_CONFIG_DIR"]).expanduser())
        paths = [p for r in roots if r.is_dir() for p in r.glob("settings*.json")]
    out = {}
    for p in paths:
        try:
            st = Path(p).stat()
            out[str(p)] = (st.st_size, st.st_mtime_ns)
        except OSError:
            out[str(p)] = (-1, -1)
    return out


CLAUDE_BEFORE = claude_settings_stat()

# Every temp folder of the run (tempfile here and TMPDIR for child processes) lands in one
# per-run folder, removed at exit (2026-10-23: test leftovers filled the shared tmp quota).
REAL_TMP = tempfile.gettempdir()
_run_tmp = tempfile.mkdtemp(prefix="fleet-test-tmp-")
atexit.register(shutil.rmtree, _run_tmp, True)
os.environ["TMPDIR"] = tempfile.tempdir = _run_tmp

if not os.environ.get("_FLEET_TEST_HOME"):
    _tmp = tempfile.mkdtemp(prefix="fleet-test-home-")
    atexit.register(shutil.rmtree, _tmp, True)
    os.environ["_FLEET_TEST_HOME"] = _tmp
TEST_HOME = Path(os.environ["_FLEET_TEST_HOME"]).resolve()
os.environ["HOME"] = str(TEST_HOME)
os.environ["XDG_CONFIG_HOME"] = str(TEST_HOME / ".config")
# A fejlesztő saját Claude-konfigja (pl. ~/.claude-personal) se legyen írható célpont: a
# `fleet install/join/...` oda linkelné az operátor-skilleket (fleet.operator_skills),
# és a `fleet secrets scan` / `setup` oda telepítené a titok-kaput (2026-10-29: így is lett).
os.environ.pop("CLAUDE_CONFIG_DIR", None)
