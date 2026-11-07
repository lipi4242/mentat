"""A felügyelet felhúzása a telepítés részeként.

Egy vezérlő: a `fleet-reconcile.timer`. A régi `agent-liveness.timer` (a
második vezérlő, ami maga is írta a heartbeatet) itt kerül le a boxról —
a funkciói a reconcile-ba olvadtak (`fleet.upkeep`).

A sablonok checkout-útvonala nem fix: a `%h/fleet-leader` (régi sablon) és
a `@@FLEET_ROOT@@` (új sablon) is a tényleges checkoutra cserélődik.
"""
from __future__ import annotations
import os
from pathlib import Path

from fleet import TEMPLATES_DIR
from fleet.txn import Txn, StepFailed

RECONCILE_UNITS = ("fleet-reconcile.service", "fleet-reconcile.timer")
RECONCILE_TIMER = "fleet-reconcile.timer"
#: A gyors út (reconcile --fast): a leállt processz ~1 percen belüli indítása.
#: Opcionális: csak akkor kerül fel, ha a checkout sablonjai között van.
FAST_UNITS = ("fleet-reconcile-fast.service", "fleet-reconcile-fast.timer")
FAST_TIMER = "fleet-reconcile-fast.timer"
LEGACY_UNITS = ("agent-liveness.timer", "agent-liveness.service")


def render_supervision(name: str, fleet_root: str, *, templates: Path | None = None) -> str:
    text = ((templates or TEMPLATES_DIR) / "systemd" / name).read_text()
    return text.replace("@@FLEET_ROOT@@", fleet_root).replace("%h/fleet-leader", fleet_root)


def remove_legacy_liveness(t: Txn, unit_dir: Path) -> list[str]:
    """A második vezérlő eltávolítása. Idempotens: ha nincs, nem csinál semmit."""
    done = []
    timer = unit_dir / LEGACY_UNITS[0]
    if timer.exists() or (unit_dir / LEGACY_UNITS[1]).exists():
        # a disable nem-nulla kódja itt sem csend: ha nem tudjuk leállítani,
        # két vezérlő maradna, és pont ezt kell megszüntetni
        t.sh(["systemctl", "--user", "disable", "--now", LEGACY_UNITS[0]],
             undo=["systemctl", "--user", "enable", "--now", LEGACY_UNITS[0]])
        for n in LEGACY_UNITS:
            if t.remove(unit_dir / n):
                done.append(f"eltávolítva: {n} (beolvadt a reconcile-ba)")
    return done


def ensure_controller(t: Txn, config_dir: Path) -> str:
    """A tulajdonjog-fájl. Csak akkor írjuk, ha NINCS: egy meglévő, más
    tartalmú fájl (pl. egy cutover közepén) emberi döntés, nem a miénk."""
    p = config_dir / "controller"
    if not p.exists():
        t.write(p, "reconcile\n")
        return "controller: reconcile (új box)"
    cur = p.read_text().strip()
    if cur != "reconcile":
        return f"FIGYELEM: a controller-fájl tartalma {cur!r} — a reconcile csak megfigyel, amíg ez nem `reconcile`"
    return "controller: reconcile"


def ensure_registry_pointer(t: Txn, config_dir: Path, registry: Path) -> str | None:
    """A timer nem látja a shell `FLEET_REGISTRY`-jét: ha a mutató-fájl
    hiányzik, megírjuk ugyanarra a registryre, amit a telepítés használt."""
    p = config_dir / "registry"
    if p.exists():
        return None
    t.write(p, str(registry) + "\n")
    return f"registry-mutató: {p} → {registry}"


def _ensure_fast(t: Txn, unit_dir: Path, fleet_root: str) -> list[str]:
    notes = [f"felügyelet: {n} írva" for n in FAST_UNITS if t.write(unit_dir / n, render_supervision(n, fleet_root))]
    t.sh(["systemctl", "--user", "daemon-reload"])
    was = t.try_sh(["systemctl", "--user", "is-active", FAST_TIMER]).stdout.strip() == "active"
    t.sh(["systemctl", "--user", "enable", "--now", FAST_TIMER],
         undo=None if was else ["systemctl", "--user", "disable", "--now", FAST_TIMER])
    return notes + [f"felügyelet: {FAST_TIMER} (gyors út: leállt processz ~1 percen belül)"]


def ensure_supervision(t: Txn, *, unit_dir: Path, config_dir: Path, fleet_root: str,
                       registry: Path) -> list[str]:
    """Felhúzza a reconcile-timert, leveszi a liveness-timert. Minden lépés
    kódja ellenőrizve; az aktív timer a végén MÉRVE, nem feltételezve."""
    notes = remove_legacy_liveness(t, unit_dir)
    for n in RECONCILE_UNITS:
        if t.write(unit_dir / n, render_supervision(n, fleet_root)):
            notes.append(f"felügyelet: {n} írva")
    if all((TEMPLATES_DIR / "systemd" / n).is_file() for n in FAST_UNITS):
        notes += _ensure_fast(t, unit_dir, fleet_root)
    notes.append(ensure_controller(t, config_dir))
    ptr = ensure_registry_pointer(t, config_dir, registry)
    if ptr:
        notes.append(ptr)
    t.sh(["systemctl", "--user", "daemon-reload"])
    was_active = t.try_sh(["systemctl", "--user", "is-active", RECONCILE_TIMER]).stdout.strip() == "active"
    t.sh(["systemctl", "--user", "enable", "--now", RECONCILE_TIMER],
         undo=None if was_active else ["systemctl", "--user", "disable", "--now", RECONCILE_TIMER])
    state = t.try_sh(["systemctl", "--user", "is-active", RECONCILE_TIMER]).stdout.strip()
    if state != "active":
        raise StepFailed(f"{RECONCILE_TIMER} nem aktív a bekapcsolás után ({state or 'nincs válasz'})")
    notes.append(f"felügyelet: {RECONCILE_TIMER} aktív")
    linger = t.try_sh(["loginctl", "show-user", os.environ.get("USER", ""), "-p", "Linger", "--value"])
    if linger.returncode == 0 and linger.stdout.strip() == "no":
        notes.append("FIGYELEM: a linger ki van kapcsolva — kijelentkezés után a timerek leállnak "
                     "(`sudo loginctl enable-linger $USER`)")
    return notes
