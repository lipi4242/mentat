"""schedule — a durable schedule for the tick (systemd user timer, a macOS LaunchAgent,
or a cron line).

    python3 -m anytime_engine.schedule --plugins myagent.concerns,myagent.providers
    python3 -m anytime_engine.schedule ... --install     # write + enable the timer
    python3 -m anytime_engine.schedule ... --cron        # print a crontab line instead
    python3 -m anytime_engine.schedule --uninstall      # macOS: unload + delete the agent

On macOS the schedule is a LaunchAgent (launchd.py), with the tick's own --lock.

Without --install it only PRINTS what it would install (dry run). Run it from the
agent's repo root (or set ANYTIME_REPO_ROOT); the python running it is the one
the timer will use, so run it with the agent's venv python if it has one.

Why not a session cron (Claude Code `/loop`, CronCreate): it only fires while
that session's window is open, expires after 7 days, and a resumed session comes
back with no schedule. Use one as a supplement, never as the schedule.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from . import config, launchd
from . import engine_manifest
from . import mentat_manifest as mm

# Agent config that must reach the tick when systemd/cron runs it, not your shell.
_CARRIED_ENV = ("ANYTIME_REVIEW_TIMES", "ANYTIME_REVIEW_WINDOWS", "ANYTIME_STATE_PATH",
                "ANYTIME_TZ", "ANYTIME_CASES_MORNING")
PLATFORM: str | None = None   # tests pin it; None = this machine


def platform() -> str:
    return PLATFORM or sys.platform


def _systemd_quote(arg: str) -> str:
    esc = arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
    return f'"{esc}"'


def _env(root: Path, plugins: str) -> dict[str, str]:
    env = {"ANYTIME_REPO_ROOT": str(root), "ANYTIME_PLUGINS": plugins}
    env.update({k: os.environ[k] for k in _CARRIED_ENV if os.environ.get(k)})
    return env


def _tick_argv(trigger: str, exec_cmd: str | None, lock: bool = False) -> list[str]:
    argv = [sys.executable, "-m", "anytime_engine.tick", trigger] + (["--lock"] if lock else [])
    return argv + (["--exec", exec_cmd] if exec_cmd else [])


def unit_name(name: str, trigger: str) -> str:
    return f"anytime-{name}-{trigger}"


def render_systemd(name: str, trigger: str, on_calendar: str, plugins: str,
                   exec_cmd: str | None = None) -> dict[str, str]:
    """{filename: content} for the .service and .timer units."""
    root = config.repo_root().resolve()
    unit = unit_name(name, trigger)
    env_lines = "".join(f"Environment={_systemd_quote(f'{k}={v}')}\n"
                        for k, v in _env(root, plugins).items())
    python, *rest = _tick_argv(trigger, exec_cmd)
    # systemd wants a plain absolute path as the executable; quote the arguments.
    exec_start = " ".join([python] + [_systemd_quote(a) for a in rest])
    service = (
        f"[Unit]\nDescription=Mentat engine {trigger} tick ({name})\n\n"
        f"[Service]\nType=oneshot\nWorkingDirectory={root}\n{env_lines}"
        f"ExecStart={exec_start}\n"
    )
    timer = (
        f"[Unit]\nDescription=Mentat engine {trigger} tick schedule ({name})\n\n"
        f"[Timer]\nOnCalendar={on_calendar}\n"
        "# Persistent: a tick missed while the box was off runs at next boot.\n"
        f"Persistent=true\nUnit={unit}.service\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )
    return {f"{unit}.service": service, f"{unit}.timer": timer}


def render_launchd(name: str, trigger: str, plugins: str,
                   exec_cmd: str | None = None) -> dict[str, str]:
    """{filename: content} for the macOS LaunchAgent; the tick takes its own lock."""
    root = config.repo_root().resolve()
    unit = unit_name(name, trigger)
    body = launchd.render(unit, root, _tick_argv(trigger, exec_cmd, lock=True), _env(root, plugins))
    return {f"{launchd.label(unit)}.plist": body.decode()}


def render_cron(trigger: str, cron_spec: str, plugins: str,
                exec_cmd: str | None = None) -> str:
    """One crontab line. A slow tick is skipped, never doubled: flock -n, or on macOS
    (no flock there) the tick's own --lock."""
    root = config.repo_root().resolve()
    env = " ".join(f"{k}={shlex.quote(v)}" for k, v in _env(root, plugins).items())
    mac = platform() == "darwin"
    lock = "" if mac else f"flock -n {shlex.quote(str(root / 'data' / 'state' / 'tick.lock'))} "
    log = shlex.quote(str(root / "data" / "logs" / "anytime-tick.log"))
    tick = " ".join(shlex.quote(a) for a in _tick_argv(trigger, exec_cmd, lock=mac))
    return (f"{cron_spec} cd {shlex.quote(str(root))} && mkdir -p data/state data/logs && "
            f"{env} {lock}{tick} >> {log} 2>&1")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m anytime_engine.schedule",
                                description="Durable schedule for the anytime tick.")
    p.add_argument("--plugins", default=os.environ.get("ANYTIME_PLUGINS", ""),
                   help="concern/provider packages (default: $ANYTIME_PLUGINS, "
                        "else mentat.json components.engine.plugins)")
    p.add_argument("--name", default=None, help="agent name (default: repo dir name)")
    p.add_argument("--trigger", default="hourly", choices=("hourly", "review"))
    p.add_argument("--on-calendar", default="hourly", help="systemd OnCalendar=")
    p.add_argument("--cron-spec", default="0 * * * *")
    p.add_argument("--exec", dest="exec_cmd", help="executor command passed to the tick")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--print", "--dry-run", dest="install", action="store_const",
                      const=False, help="show what would be installed (default)")
    mode.add_argument("--install", action="store_true",
                      help="write the units and enable the timer")
    mode.add_argument("--cron", action="store_true", help="print a crontab line instead")
    mode.add_argument("--uninstall", action="store_true",
                      help="macOS: unload and delete the LaunchAgent")
    p.add_argument("--unit-dir", default=None, help="default: ~/.config/systemd/user, "
                   "on macOS ~/Library/LaunchAgents")
    p.add_argument("--no-enable", action="store_true", help="with --install: only write")
    p.set_defaults(install=False)
    args = p.parse_args(argv)
    mac = platform() == "darwin"
    if args.uninstall:
        if not mac:
            print("refusing: --uninstall is for the macOS LaunchAgent", file=sys.stderr)
            return 2
        return launchd.uninstall(unit_name(args.name or config.repo_root().resolve().name,
                                           args.trigger), launchd.folder(args.unit_dir))
    try:
        owner = engine_manifest.schedule_owner()
        if not args.plugins:
            args.plugins = ",".join(engine_manifest.plugins())
    except mm.ManifestError as e:   # rule 6: diagnostics only, nothing installed
        print(f"refusing: {e}", file=sys.stderr)
        return 2
    if owner == "fleet":            # rule 5: one schedule owner
        msg = ("mentat.json: components.engine.schedule_owner is 'fleet' — the fleet runs "
               "this agent's tick; the engine will not install a second schedule")
        if args.install:
            print(f"refusing: {msg}", file=sys.stderr)
            return 2
        print(f"# NOTE: {msg}")
    if not args.plugins:
        p.error("--plugins (or ANYTIME_PLUGINS) is required: the timer must know your concerns")
    name = args.name or config.repo_root().resolve().name

    if args.cron:
        print(render_cron(args.trigger, args.cron_spec, args.plugins, args.exec_cmd))
        return 0
    if mac:
        rc = launchd.run(args, unit_name(name, args.trigger), config.repo_root().resolve(),
                         render_launchd(name, args.trigger, args.plugins, args.exec_cmd))
        if rc == 0 and args.install:
            engine_manifest.record_install([s.strip() for s in args.plugins.split(",") if s.strip()])
        return rc
    args.unit_dir = args.unit_dir or str(Path.home() / ".config/systemd/user")
    units = render_systemd(name, args.trigger, args.on_calendar, args.plugins, args.exec_cmd)
    timer = f"{unit_name(name, args.trigger)}.timer"
    enable = [["systemctl", "--user", "daemon-reload"],
              ["systemctl", "--user", "enable", "--now", timer]]
    if not args.install:
        for fname, body in units.items():
            print(f"# --- {Path(args.unit_dir) / fname}\n{body}")
        print("# then:\n" + "\n".join(" ".join(c) for c in enable))
        print("# headless box (no login session): loginctl enable-linger $USER")
        return 0
    unit_dir = Path(args.unit_dir)
    unit_dir.mkdir(parents=True, exist_ok=True)
    for fname, body in units.items():
        (unit_dir / fname).write_text(body)
        print(f"wrote {unit_dir / fname}")
    if not args.no_enable:
        for cmd in enable:
            subprocess.run(cmd, check=True)
        print(f"enabled {timer} — check: systemctl --user list-timers {timer}")
    engine_manifest.record_install([s.strip() for s in args.plugins.split(",") if s.strip()])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
