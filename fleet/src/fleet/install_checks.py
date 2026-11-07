"""A telepítés előtti és a bukás utáni ellenőrzések: amit egy
emberi olvasónak meg kell kapnia, ha a claude el sem indulhat, vagy azonnal
kilépett."""
from __future__ import annotations
import os
import shutil
from pathlib import Path

from fleet import claude_auth
from fleet.registry import is_dormant
from fleet.txn import run_cmd

CLAUDE_BIN = Path.home() / ".local" / "bin" / "claude"   # a unit-sablon ezt hívja
TMUX_BIN = Path("/usr/bin/tmux")                          # a unit-sablon ezt hívja


def tmux_install_hint() -> str:
    for pm, cmd in (("apt-get", "sudo apt-get update && sudo apt-get install -y tmux"), ("dnf", "sudo dnf install -y tmux"),
                    ("apk", "sudo apk add tmux"), ("pacman", "sudo pacman -S --noconfirm tmux")):
        if shutil.which(pm):
            return cmd
    return "telepítsd a tmux csomagot a rendszer csomagkezelőjével"


def tmux_problem(tmux_bin: Path = TMUX_BIN) -> list[str]:
    """A unit a /usr/bin/tmux-ot hívja; nélküle a unit `failed`, a claude el sem indul."""
    if tmux_bin.is_file() and os.access(tmux_bin, os.X_OK):
        return []
    return [f"hiányzik a tmux ({tmux_bin}) — a unit ebben futtatja a claude-ot. Telepítsd: `{tmux_install_hint()}`"]


def account_env(entry: dict) -> list[str]:
    acc = entry.get("claude_account") or "shared"
    return [] if acc == "shared" else [f"CLAUDE_CONFIG_DIR={Path.home() / f'.claude-{acc}'}"]


def precheck(entry: dict, *, host: str | None, claude_bin: Path, run=run_cmd,
             home: Path | None = None, warnings: list | None = None,
             tmux_bin: Path = TMUX_BIN, run_env=claude_auth.run_env,
             environ: dict | None = None) -> list[str]:
    """Ami miatt az ágens el sem indulhat — még írás ELŐTT."""
    out = []
    want = entry.get("host")
    if host is None:
        out.append("ez a gép nincs a boxes.json-ban, és nincs FLEET_HOST / ~/.config/fleet/host — "
                   "nem tudom, ez-e az ágens gépe")
    elif want and want != host:
        out.append(f"a registry szerint az ágens a(z) {want!r} gépen fut, ez a(z) {host!r} — "
                   "két helyen futó ágens kettős választ ad")
    if is_dormant(entry):
        return out
    home = home or Path.home()
    out += tmux_problem(tmux_bin)
    env = env_file_check(entry, home=home)
    out += env["errors"]
    if warnings is not None:
        warnings += env["warnings"]
    if not (claude_bin.is_file() and os.access(claude_bin, os.X_OK)):
        out.append(f"hiányzik a claude bináris: {claude_bin} (a unit ezt indítja)")
        return out
    # a unit szemével: a telepítő shelljének tokenje nem bizonyíték (06-flotta)
    problems, notes = claude_auth.ensure_auth(entry, claude_bin=claude_bin, home=home,
                                              environ=environ, run=run_env, sysrun=run)
    out += problems
    if warnings is not None:
        warnings += notes
    return out


def journal_tail(unit: str, run=run_cmd, n: int = 20) -> list[str]:
    r = run(["journalctl", "--user", "-u", unit, "-n", str(n * 3), "--no-pager", "-o", "cat"])
    # a KillMode=none deprecációs figyelmeztetés minden reloadnál ismétlődik, és
    # kiszorítaná a lényeget (élesben mérve: 4 sor a 7-ből)
    lines = [ln for ln in (r.stdout or "").strip().splitlines() if "KillMode=none" not in ln]
    return lines[-n:] or [f"(a journal üres vagy nem olvasható, kód {r.returncode})"]


def claude_says(entry: dict, claude_bin: Path, run=run_cmd) -> list[str]:
    """Bukás után: mit mond a claude egy nem-interaktív hívásra ugyanazzal a
    fiókkal. A tmux-pane a kilépéssel eltűnik, a journalba a claude nem ír —
    ez az egyetlen hely, ahol az ok (login, kredit) szövegesen látszik.
    Csak bukáskor fut; bejelentkezett fióknál egy apró kérés."""
    r = run(["timeout", "45", "env", *account_env(entry), str(claude_bin), "-p", "ping"])
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return [f"claude -p: {ln}" for ln in out[-3:]] or [f"claude -p: nincs kimenet (kód {r.returncode})"]


def env_file_check(entry: dict, *, home: Path, unit_text: str | None = None) -> dict:
    """Élesben mérve (friss Ubuntu, 2026-10-15): a unit pane-shellje (`/bin/sh`
    = dash) `. <env-fájl> 2>/dev/null` sorral tölti az env-fájlt; ha a fájl
    nincs meg, a dash a `.` hibájára AZONNAL kilép (kód 2), a 2>/dev/null pedig
    elnyeli az üzenetet. A claude el sem indul, és sehol nincs nyoma.

    Ezért a TELEPÍTENDŐ unit szövege dönt: őrizetlen betöltésnél (`. F 2>/dev/null`)
    a hiányzó fájl hiba; őrzöttnél (`if [ -r F ]`) csak figyelmeztetés — így a
    sablonjavítás előtt és után is igazat mond. {"errors": [...], "warnings": [...]}"""
    out = {"errors": [], "warnings": []}
    if unit_text is None:
        from fleet import install
        try:
            unit_text = install.unit_text_for(entry)
        except (OSError, ValueError):
            return out
    rel = f".config/{entry['agent']}/{entry['env_file']}"
    if (home / rel).exists():
        return out
    if f". %h/{rel} 2>/dev/null;" in unit_text:
        out["errors"].append(f"hiányzik az env-fájl: ~/{rel} — a unit shellje enélkül azonnal kilép, a claude "
                             f"el sem indul. Hozd létre (akár üresen): `install -m600 /dev/null ~/{rel}`")
    elif f"[ -r %h/{rel} ]" in unit_text:
        out["warnings"].append(f"FIGYELEM: nincs env-fájl (~/{rel}) — a unit enélkül is indul, de ha az "
                               "ágensnek titok/beállítás kell belőle (pl. a híd tokenje), hozd létre (0600)")
    return out


def env_file_problem(entry: dict, *, home: Path, unit_text: str | None = None) -> list[str]:
    """Csak a hibák (a telepítést megállító eset)."""
    return env_file_check(entry, home=home, unit_text=unit_text)["errors"]
