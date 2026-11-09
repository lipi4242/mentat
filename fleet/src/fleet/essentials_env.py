"""11-07: egy ágens futásidejű előfeltételei — kulcsNEVEK, érték soha.

    workdir(entry, home)            a registry `workdir`-je, %h → HOME
    unit_env_files(entry, home)     a TELEPÍTETT unit (és drop-injei) `EnvironmentFile=` fájljai;
                                    None, ha a unit nincs a boxon
    token_problem(entry, home)      (hiba, nem-mérhető): hidas ágens unitjának env-jében nincs
                                    TELEGRAM_BOT_TOKEN (név szerint) → a send.mjs-nek nincs tokenje
    sourcing_warnings(entry, home)  ágens-szkript, ami leltárban lévő fájlt `.`/`source`-szal tölt be
    send_failures(entry, home)      a send.mjs „missing_token" notice-ai a kézbesítési naplóban (24 óra)

Miért a szkript-lint: a titok-kapu csak a Bash-hívás SZÖVEGÉT elemzi, a meghívott szkript
tartalmát nem (`bash bin/valasz-kuld.sh` átmegy, akkor is, ha a szkript a telegram.env-et
`.`-tal tölti be). Ez ma működik, de a token így nem a unit env-jéből jön, és ha a sor egyszer a
parancsba kerül (vagy a szkript a leltárba), az ágens némán elveszti a küldést.
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path

from fleet import titok_hely as H
from fleet.titok_formatum import ENV_LINE

TOKEN = "TELEGRAM_BOT_TOKEN"
SOURCE = re.compile(r"""^\s*(?:set\s+-a\s*;\s*)?(?:\.|source)\s+["']?([^"'\s;]+)""", re.M)
SCRIPT_DIRS = ("bin", "scripts")
MAX_SCRIPTS = 200


def workdir(entry: dict, home: Path) -> Path:
    return Path(str(entry.get("workdir") or home).replace("%h", str(home)))


def bridged(entry: dict) -> bool:
    return bool((entry.get("bridge") or {}).get("unit"))


def unit_env_files(entry: dict, home: Path) -> list[Path] | None:
    udir = home / ".config" / "systemd" / "user"
    unit = udir / entry["unit"]
    if not unit.is_file():
        return None
    out = []
    for u in [unit] + sorted((udir / f"{entry['unit']}.d").glob("*.conf")):
        for line in u.read_text(errors="replace").splitlines():
            m = H.ENVFILE.match(line)
            if m:
                out.append(Path(m.group(1).replace("%h", str(home)).replace("${HOME}", str(home))))
    return out


def key_names(path: Path) -> set[str]:
    """Csak a `NÉV=` bal oldala; az érték nem kerül változóba."""
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return set()
    return {m.group(1) for m in map(ENV_LINE.match, lines) if m}


def token_problem(entry: dict, home: Path) -> tuple[str | None, str | None]:
    if not bridged(entry):
        return None, None
    files = unit_env_files(entry, home)
    if files is None:
        return None, f"a unit ({entry['unit']}) nincs telepítve: a token-előfeltétel nem mérhető"
    if any(TOKEN in key_names(f) for f in files):
        return None, None
    shown = ", ".join("~/" + str(f.relative_to(home)) if f.is_relative_to(home) else str(f) for f in files)
    return (f"a unit env-jében nincs {TOKEN} (betöltve: {shown or 'semmi'}) — a send.mjs nem tud küldeni. "
            f"Javítás: `fleet install {entry['agent']}` (a hidas ágens unitja a híd env-fájlját is betölti)"), None


def _leltar_paths(home: Path) -> set[str]:
    try:
        files = json.loads(H.inventory_path(home).read_text()).get("files", [])
    except (OSError, ValueError, AttributeError):
        return set()
    return {f["path"] for f in files if isinstance(f, dict) and f.get("path") and f.get("class") != "atirat"}


def _scripts(entry: dict, home: Path) -> list[Path]:
    wd = workdir(entry, home)
    dirs = [wd / d for d in SCRIPT_DIRS] + [home / ".config" / entry["agent"] / "jobs"]
    out = [p for d in dirs if d.is_dir() for p in sorted(d.iterdir()) if p.is_file()]
    return out[:MAX_SCRIPTS]


def sourcing_warnings(entry: dict, home: Path) -> list[str]:
    lel = _leltar_paths(home)
    if not lel:
        return []
    out = []
    for s in _scripts(entry, home):
        try:
            text = s.read_text(errors="replace")[:200_000]
        except OSError:
            continue
        for m in SOURCE.finditer(text):
            raw = m.group(1).replace("${HOME}", str(home)).replace("$HOME", str(home)).replace("~", str(home), 1)
            if str(Path(raw).resolve()) in lel or raw in lel:
                out.append(f"{s.name}: leltárban lévő fájlt tölt be (`. {m.group(1)}`) — vedd env-ből, a fájl "
                           f"csak tartalék legyen: `[ -n \"${TOKEN}\" ] || . {m.group(1)}`")
    return out


def send_failures(entry: dict, home: Path, now: float | None = None) -> str | None:
    now = time.time() if now is None else now
    inbox = home / ".config" / entry["agent"] / "telegram-inbox"
    n = 0
    for day in {time.strftime("%Y-%m-%d", time.gmtime(now - d)) for d in (0, 86400)}:
        try:
            lines = (inbox / f"delivery-{day}.jsonl").read_text(errors="replace").splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("type") == "notice" and r.get("event") == "missing_token" and now - r.get("ts", 0) / 1000 < 86400:
                n += 1
    return f"a send.mjs {n}× futott token nélkül az elmúlt 24 órában (semmi nem ment ki)" if n else None
