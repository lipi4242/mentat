"""Tranzakció a telepítéshez: minden fájl-írás előtt mentés a
memóriába, minden külső hívás visszatérési kódja ellenőrizve, hiba esetén
visszaállítás az előző állapotra.

Miért kell: az elfogadási teszt egy friss boxon `fleet install` után inaktív
unitot, hiányzó timereket és NÉMA kimenetet mért. A régi kód a `systemctl`
eredményét eldobta, így egy bukott `enable` is „kész" volt.

Használat:
    t = Txn()
    try:
        t.write(path, text); t.sh(["systemctl", "--user", "daemon-reload"])
    except StepFailed:
        t.rollback(); raise
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path


class StepFailed(RuntimeError):
    """Egy lépés nem sikerült; az üzenet emberi olvasatú, a kimenettel."""


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:  # nincs ilyen bináris: ez is hiba, nem csend
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


class Txn:
    def __init__(self, run=run_cmd):
        self._run = run
        self._saved: dict[Path, bytes | None] = {}   # útvonal → régi tartalom / None = nem létezett
        self._undo: list[list[str]] = []             # visszaállításkor futó parancsok (fordított sorrend)
        self._dirs: list[Path] = []                  # az általunk létrehozott könyvtárak
        self.log: list[str] = []

    # ── fájlok ────────────────────────────────────────────────────────────
    def _remember(self, path: Path) -> None:
        path = Path(path)
        if path not in self._saved:
            self._saved[path] = path.read_bytes() if path.exists() else None

    def guard(self, path: Path) -> None:
        """Egy MÁS által (pl. zárral) írt fájl állapotának megjegyzése, hogy a
        visszaállítás azt is visszahozza."""
        self._remember(Path(path))

    def write(self, path: Path, text: str) -> bool:
        """Atomikus írás; True, ha változott."""
        path = Path(path)
        if path.exists() and path.read_text() == text:
            return False
        self._remember(path)
        if not path.parent.exists():
            self._dirs.append(path.parent)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.fleet-tmp")
        tmp.write_text(text)
        os.replace(tmp, path)
        self.log.append(f"írva: {path}")
        return True

    def remove(self, path: Path) -> bool:
        path = Path(path)
        if not path.exists():
            return False
        self._remember(path)
        path.unlink()
        self.log.append(f"törölve: {path}")
        return True

    # ── külső hívások ─────────────────────────────────────────────────────
    def sh(self, cmd: list[str], *, undo: list[str] | None = None) -> subprocess.CompletedProcess:
        """Futtat, és nem-nulla kódra `StepFailed`. Az `undo` parancs a
        visszaállításkor fut (pl. enable → disable)."""
        r = self._run(cmd)
        if r.returncode != 0:
            out = ((r.stderr or "") + (r.stdout or "")).strip()
            raise StepFailed(f"`{' '.join(cmd)}` → kód {r.returncode}" + (f": {out}" if out else ""))
        if undo:
            self._undo.append(undo)
        self.log.append(" ".join(cmd))
        return r

    def try_sh(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Futtat, a kódot NEM ellenőrzi (pl. `is-active`, ahol a nem-nulla válasz adat)."""
        return self._run(cmd)

    # ── visszaállítás ─────────────────────────────────────────────────────
    def rollback(self) -> list[str]:
        """Visszaállít minden fájlt és lefuttatja az undo-parancsokat. A
        visszaállítás hibái nem nyelődnek el: a visszatérő listában vannak."""
        notes = []
        # Két fázis, mert mindkét sorrend bukik valamin (élesben mérve): egy
        # ÚJ unit letiltásához a fájlnak még meg kell lennie, egy VISSZAÁLLÍTOTT
        # timer engedélyezéséhez pedig már meg kell lennie (és reload kell).
        # Ezért: parancsok → fájlok + reload → a bukott parancsok még egyszer.
        retry = [cmd for cmd in reversed(self._undo) if self._run(cmd).returncode != 0]
        for path, old in self._saved.items():
            try:
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(old)
            except OSError as e:
                notes.append(f"visszaállítás: {path}: {e}")
        if self._saved:
            r = self._run(["systemctl", "--user", "daemon-reload"])
            if r.returncode != 0:
                notes.append(f"visszaállítás: daemon-reload → kód {r.returncode}")
        for d in reversed(self._dirs):
            try:
                d.rmdir()          # csak ha üres: más tartalmához nem nyúlunk
            except OSError:
                pass
        for cmd in retry:
            r = self._run(cmd)
            if r.returncode != 0:
                notes.append(f"visszaállítás: `{' '.join(cmd)}` → kód {r.returncode}")
        self._saved.clear()
        self._undo.clear()
        self._dirs.clear()
        return notes

    def touched(self) -> list[str]:
        return [str(p) for p in self._saved]
