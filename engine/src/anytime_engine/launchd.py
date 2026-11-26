"""launchd — the macOS schedule: a per-user LaunchAgent that ticks hourly while the Mac
is awake (StartInterval; a Mac that slept runs one tick at wake) and once at login
(RunAtLoad). No flock on macOS: the tick takes its own lock (`tick --lock`).

schedule.py calls this when the platform is darwin. Every launchctl call goes through
RUNNER, so a test never loads a real LaunchAgent.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

RUNNER: Callable[[Sequence[str]], int] = lambda cmd: subprocess.run(list(cmd)).returncode
INTERVAL = 3600


def label(unit: str) -> str:
    return f"ai.mentat.{unit}"


def folder(unit_dir: str | None) -> Path:
    return Path(unit_dir) if unit_dir else Path.home() / "Library" / "LaunchAgents"


def render(unit: str, root: Path, argv: list[str], env: dict[str, str]) -> bytes:
    log = str(root / "data" / "logs" / "anytime-tick.log")
    return plistlib.dumps({
        "Label": label(unit), "ProgramArguments": argv, "EnvironmentVariables": env,
        "WorkingDirectory": str(root), "RunAtLoad": True, "StartInterval": INTERVAL,
        "StandardOutPath": log, "StandardErrorPath": log, "ProcessType": "Background",
    })


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _bootout(unit: str) -> int:
    return RUNNER(["launchctl", "bootout", f"{_domain()}/{label(unit)}"])


def show(unit: str, folder: Path, body: bytes) -> None:
    path = folder / f"{label(unit)}.plist"
    print(f"# --- {path}\n{body.decode()}")
    print(f"# then:\nlaunchctl bootstrap {_domain()} {path}")


def install(unit: str, folder: Path, root: Path, body: bytes, enable: bool) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    (root / "data" / "logs").mkdir(parents=True, exist_ok=True)   # launchd does not create it
    path = folder / f"{label(unit)}.plist"
    path.write_bytes(body)
    print(f"wrote {path}")
    if not enable:
        return 0
    _bootout(unit)                           # a re-install replaces the loaded agent
    rc = RUNNER(["launchctl", "bootstrap", _domain(), str(path)])
    if rc != 0:
        print(f"launchctl bootstrap failed ({rc}): {path} written, not loaded", file=sys.stderr)
        return 1
    print(f"enabled {label(unit)} — check: launchctl print {_domain()}/{label(unit)}")
    return 0


def run(args, unit: str, root: Path, rendered: dict[str, str]) -> int:
    """schedule.main on macOS: print the agent (dry run) or install it."""
    if args.trigger != "hourly":
        print("refusing: on macOS only the hourly trigger is scheduled", file=sys.stderr)
        return 2
    body = next(iter(rendered.values())).encode()
    if not args.install:
        show(unit, folder(args.unit_dir), body)
        return 0
    return install(unit, folder(args.unit_dir), root, body, enable=not args.no_enable)


def uninstall(unit: str, where: Path) -> int:
    """Unload and delete; an agent that is not loaded or not there is already gone."""
    _bootout(unit)
    path = where / f"{label(unit)}.plist"
    if path.exists():
        path.unlink()
        print(f"removed {path}")
    else:
        print(f"nothing to remove: {path}")
    return 0
