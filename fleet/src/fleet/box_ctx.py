"""A `fleet box-upgrade` közös állapota és apró segédei.

Egy futás egy `Ctx`: a lépések ebbe írnak (előző sha, elrendezés, ágens-
eredmények), és ebből olvas a nyugta. Semmi nem a futó Python-checkoutból
dolgozik a váltás után: az ágensenkénti munkát az ÚJ checkout `bin/fleet`-je
végzi alfolyamatként (lásd box_agents) — a futó processz moduljai a régi kódból
jöttek, és a checkout alattuk cserélődik.
"""
from __future__ import annotations
import contextlib
import datetime
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from fleet.plugin_source import PUBLIC_REPO
from fleet.txn import StepFailed, run_cmd

PUBLIC_URL = f"https://github.com/{PUBLIC_REPO}"
#: a felügyelet timerei: a checkout cseréje alatt állnak (runbook 3. lépés)
TIMERS = ("fleet-reconcile.timer", "fleet-reconcile-fast.timer")
#: ennél frissebb transzkript = dolgozik; ilyen ágenst nem indítunk újra
BUSY_S = 600
#: a reconcile --observe sora, ha beavatkozna (reconcile.py)
WOULD_ACT = "(nem hajtom végre)"


#: a lassú, csak olvasó hívások (doctor, reconcile --observe) felső korlátja
SLOW_TIMEOUT_S = 300


def run_timeout(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", f"időtúllépés ({timeout:.0f} s)")
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


def safe_print(line: str) -> None:
    """Egy megszakadt ssh után a stdout halott: a kiírás ne állítsa meg a visszaállítást."""
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        pass


@contextlib.contextmanager
def private():
    """A nyugta csak a tulajdonosé (0700/0600): doctor-kimenet, utak, ágensnevek."""
    old = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old)


class Halt(StepFailed):
    """Bukás, ami után a korábbi lépések NEM állnak vissza (pl. a kanári utáni
    ágens bukik: a már frissített ágensek és a checkout maradnak)."""


@dataclass
class Ctx:
    home: Path
    tag: str
    url: str = PUBLIC_URL
    dry_run: bool = False
    canary: str | None = None
    only: list[str] = field(default_factory=list)
    last: list[str] = field(default_factory=list)
    run: Callable[[list[str]], subprocess.CompletedProcess] = run_cmd
    run_t: Callable[[list[str], float], subprocess.CompletedProcess] = run_timeout
    say: Callable[[str], None] = safe_print
    now: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    stamp: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    state: dict = field(default_factory=dict)        # a lépések közös jegyzetei
    agents: list[dict] = field(default_factory=list)  # ágensenkénti eredmény (nyugta)
    rolled_back: list[str] = field(default_factory=list)
    not_rolled_back: list[str] = field(default_factory=list)

    @property
    def src(self) -> Path:            # az új elrendezés checkoutja
        return self.home / "src" / "mentat"

    @property
    def link(self) -> Path:           # amit a unitok és a ~/.local/bin/fleet lát
        return self.home / "fleet-leader"

    @property
    def backup(self) -> Path:         # a régi (legacy) checkout helye a váltás után
        return self.home / "fleet-leader.pre-mentat"

    @property
    def new_fleet(self) -> Path:      # az ÚJ kód CLI-je
        return self.src / "fleet" / "bin" / "fleet"

    @property
    def unit_dir(self) -> Path:
        return self.home / ".config" / "systemd" / "user"

    @property
    def receipt_dir(self) -> Path:
        return self.home / ".config" / "fleet" / "upgrades" / self.stamp


def sh(ctx: Ctx, cmd: list[str], *, what: str = "") -> str:
    """Futtat; nem-nulla kódra `StepFailed` a kimenet végével. Visszaad: stdout."""
    r = ctx.run([str(c) for c in cmd])
    if r.returncode != 0:
        tail = " | ".join(((r.stderr or "") + (r.stdout or "")).strip().splitlines()[-4:])
        raise StepFailed(f"{what or ' '.join(map(str, cmd))} → kód {r.returncode}" + (f": {tail}" if tail else ""))
    return r.stdout or ""


def git(ctx: Ctx, repo: Path, *args: str) -> str:
    return sh(ctx, ["git", "-C", str(repo), *args]).strip()


def git_try(ctx: Ctx, repo: Path, *args: str) -> str | None:
    r = ctx.run(["git", "-C", str(repo), *args])
    return r.stdout.strip() if r.returncode == 0 else None
