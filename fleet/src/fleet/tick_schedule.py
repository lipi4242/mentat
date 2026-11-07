"""motor + flotta: a flotta veszi át a tick ütemezését (LG1 spec 5. szabály).

Egy gazda: `components.engine.schedule_owner` = `engine` (a motor saját
`anytime-<név>-<trigger>.timer`-e) vagy `fleet`. Az átvétel idempotens:

  1. a flotta saját `fleet-tick-<ágens>.timer`-e felkerül és AKTÍV (mérve);
  2. a motor timere leáll, le van tiltva, a unit-fájljai törölve;
  3. csak ezután íródik `schedule_owner: fleet`.

A flotta unitja a motor tick-belépőjét hívja (`python3 -m anytime_engine.tick
hourly`, motor 0.3.0). Ha a motor timere létezett, az ExecStart, a
WorkingDirectory, az Environment és az OnCalendar onnan jön át változatlanul
(így megmarad a venv-python és az ütem); különben a mentat.json
`components.engine`-ből épül, óránkénti ütemmel.

`--exec`: ha a mentat.json `components.engine.exec`-et rögzít (motor
#22 óta a tick ezt futtatja, ha nem kap `--exec`-et), a flotta unitja NEM ad
át saját `--exec`-et — az felülírná a rögzített, commitolt végrehajtót. Egy
már átvett unitból is kiveszi (idempotens). Ha nincs `engine.exec`, a
motortól átvett `--exec` marad.
"""
from __future__ import annotations
import re
import shlex
import shutil
from pathlib import Path

from fleet.txn import Txn, StepFailed

_KEEP = re.compile(r"^(ExecStart|WorkingDirectory|Environment)=")


def tick_unit(agent: str) -> str:
    return f"fleet-tick-{agent}"


def _q(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'


def find_engine_timers(unit_dir: Path, repo: Path) -> list[tuple[Path, Path]]:
    """(timer, service) párok, amelyek EZT a repót tickelik (WorkingDirectory)."""
    out = []
    want = str(Path(repo).resolve())
    for timer in sorted(Path(unit_dir).glob("anytime-*.timer")):
        svc = timer.with_suffix(".service")
        try:
            body = svc.read_text()
        except OSError:
            continue
        if f"WorkingDirectory={want}" in body.splitlines():
            out.append((timer, svc))
    return out


def strip_exec(line: str) -> str:
    """Pure: az `ExecStart=` sorból a `--exec X` / `--exec=X` kivéve, a többi
    argumentum (idézéssel együtt) változatlan."""
    if not line.startswith("ExecStart=") or "--exec" not in line:
        return line
    args = shlex.split(line[len("ExecStart="):])
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "--exec":
            skip = True
            continue
        if a.startswith("--exec="):
            continue
        out.append(a)
    # a tokenek a systemd-escape-eket ($$, %%) szó szerint őrzik: csak idézünk, nem escape-elünk újra
    return "ExecStart=" + " ".join(
        a if a == shlex.quote(a) else '"' + a.replace("\\", "\\\\").replace('"', '\\"') + '"' for a in out)


def _from_engine(engine: dict, repo: Path) -> list[str]:
    path = str(engine.get("path") or "anytime_engine")
    if path.startswith("/") or ".." in Path(path).parts:
        raise StepFailed(f"components.engine.path csak repón belüli relatív lehet: {path!r} (3. szabály)")
    pp = (Path(repo).resolve() / path).parent
    env = {"ANYTIME_REPO_ROOT": str(Path(repo).resolve()), "PYTHONPATH": str(pp),
           "ANYTIME_PLUGINS": ",".join(engine.get("plugins") or [])}
    return ([f"WorkingDirectory={Path(repo).resolve()}"]
            + [f"Environment={_q(f'{k}={v}')}" for k, v in env.items()]
            + ["ExecStart=/usr/bin/python3 -m anytime_engine.tick hourly"])


def render(agent: str, repo: Path, engine: dict, found: list[tuple[Path, Path]]) -> dict[str, str]:
    if found:
        timer, svc = found[0]
        body = [ln for ln in svc.read_text().splitlines() if _KEEP.match(ln)]
        if engine.get("exec"):
            body = [strip_exec(ln) for ln in body]
        cal = [ln for ln in timer.read_text().splitlines() if ln.startswith("OnCalendar=")] or ["OnCalendar=hourly"]
        src = f"átvéve: {svc.name}"
    else:
        body, cal, src = _from_engine(engine, repo), ["OnCalendar=hourly"], "a mentat.json-ból"
    u = tick_unit(agent)
    service = (f"# Mentat fleet: a motor tick-belépője, a flotta ütemezésében ({src}).\n"
               f"# Ne szerkeszd: `fleet join` írja (schedule_owner: fleet).\n"
               f"[Unit]\nDescription=anytime tick ({agent}) — fleet-ütemezés\n\n"
               f"[Service]\nType=oneshot\n" + "\n".join(body) + "\n")
    return {f"{u}.service": service, f"{u}.timer": timer_text(agent, cal)}


def timer_text(agent: str, cal: list[str]) -> str:
    """A flotta tick-timerének teljes szövege (a render és a `registry set tick_period_s` is ezt írja)."""
    return (f"[Unit]\nDescription=anytime tick ütem ({agent}) — fleet\n\n[Timer]\n"
            + "\n".join(cal) + f"\nPersistent=true\nUnit={tick_unit(agent)}.service\n\n[Install]\n"
            "WantedBy=timers.target\n")


def take_over(t: Txn, *, agent: str, repo: Path, engine: dict, unit_dir: Path) -> list[str]:
    """Átveszi az ütemezést; StepFailed-et dob, a visszaállítás a hívóé."""
    if shutil.which("systemctl") is None:
        return ["ütemezés: nincs systemd ezen a gépen — a motor ütemezése marad (a boxon futtasd a join-t)"]
    unit_dir = Path(unit_dir)
    found = find_engine_timers(unit_dir, repo)
    notes = []
    own = unit_dir / f"{tick_unit(agent)}.service"
    if found or not own.exists():
        # már átvett ütemezést NEM írunk újra a mentat.json-ból: az elvesztené
        # a motortól átvett ExecStart-ot (venv) — idempotencia
        for name, text in render(agent, repo, engine, found).items():
            if t.write(unit_dir / name, text):
                notes.append(f"ütemezés: {name} írva")
    elif engine.get("exec"):
        old = own.read_text()
        new = "\n".join(strip_exec(ln) for ln in old.splitlines()) + "\n"
        if new != old and t.write(own, new):
            notes.append(f"ütemezés: {own.name} — a saját --exec kivéve (a mentat.json engine.exec-je fut)")
    timer = f"{tick_unit(agent)}.timer"
    t.sh(["systemctl", "--user", "daemon-reload"])
    was = t.try_sh(["systemctl", "--user", "is-active", timer]).stdout.strip() == "active"
    t.sh(["systemctl", "--user", "enable", "--now", timer],
         undo=None if was else ["systemctl", "--user", "disable", "--now", timer])
    if t.try_sh(["systemctl", "--user", "is-active", timer]).stdout.strip() != "active":
        raise StepFailed(f"{timer} nem aktív a bekapcsolás után")
    for etimer, esvc in found:
        t.sh(["systemctl", "--user", "disable", "--now", etimer.name],
             undo=["systemctl", "--user", "enable", "--now", etimer.name])
        t.remove(etimer); t.remove(esvc)
        notes.append(f"ütemezés: a motor timere ({etimer.name}) leállítva és eltávolítva")
    if found:
        t.sh(["systemctl", "--user", "daemon-reload"])
    notes.append(f"ütemezés: a flottáé ({timer} aktív)")
    return notes
