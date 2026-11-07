"""A per-ágens Telegram-híd telepítése és állapota (helyi box).

A híd egy kis node processz ágensenként: long-pollozza a Telegramot és a
tmux sessionbe injektál. A KÓD egy helyen él (`bridge/` ebben a repóban), a
példány az ágens `~/.config/<agent>/sub-etha/` alá települ — a régi útvonal
marad, mert az ágensek agya erre hivatkozik (send.mjs), és egy útvonal-
csere minden agyat egyszerre törne.

A telepített bridge.mjs második sorába verzióbélyeg kerül; a `status` ebből
látja a driftet SSH nélkül.
"""
from __future__ import annotations
import datetime
import shutil
from pathlib import Path

from fleet import TEMPLATES_DIR, BRIDGE_DIR
from fleet.registry import is_dormant
from fleet.install import backup, UNIT_DIR

_STAMP_PREFIX = "// fleet-bridge "

from fleet.bridge_ops import ENTRY_POINTS, _run, drift_files, rollback_bridge  # noqa: F401,E402


def bridge_version(root: Path = BRIDGE_DIR) -> str:
    try:
        return (Path(root) / "VERSION").read_text().strip()
    except OSError:
        return "0.0.0"


def render_unit(entry: dict, *, env_file: str, state_dir: str,
                template: str | None = None) -> str:
    text = template if template is not None else (TEMPLATES_DIR / "bridge.service.tmpl").read_text()
    text = (text.replace("@@AGENT@@", entry["agent"])
                .replace("@@UNIT_AFTER@@", entry["unit"])
                .replace("@@ENV_FILE@@", env_file)
                .replace("@@STATE_DIR@@", state_dir))
    if "@@" in text:
        raise ValueError(f"unsubstituted placeholder remains in rendered bridge unit for {entry.get('agent')!r}")
    return text


def stamp(path: Path, version: str) -> None:
    """A verzióbélyeg a második sorba (a shebang után) — `head -1` túléli."""
    path = Path(path)
    lines = path.read_text().splitlines(keepends=True)
    line = f"{_STAMP_PREFIX}{version} installed {datetime.date.today().isoformat()}\n"
    if len(lines) >= 2 and (lines[1].lstrip().startswith(_STAMP_PREFIX)
                            or lines[1].lstrip().startswith("// sub-etha ")):
        lines[1] = line
    else:
        lines.insert(1, line)
    path.write_text("".join(lines))


def read_stamp(path: Path) -> str | None:
    path = Path(path)
    if not path.exists():
        return None
    lines = path.read_text().splitlines()
    if len(lines) < 2:
        return None
    s = lines[1].strip()
    for prefix in (_STAMP_PREFIX, "// sub-etha "):
        if s.startswith(prefix):
            return s[len(prefix):].split(" ", 1)[0]
    return None


def copy_bridge(dest: Path, *, root: Path = BRIDGE_DIR) -> None:
    """Fájlmásolás a `bridge/`-ből. A cél teljes tartalma lecserélődik, a
    régi példány `.bak-<idő>` könyvtárba kerül."""
    dest = Path(dest)
    if dest.exists():
        stamp_ = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(dest), str(dest.with_name(f"{dest.name}.bak-{stamp_}")))
    dest.mkdir(parents=True)
    for ep in ENTRY_POINTS:
        shutil.copy2(Path(root) / ep, dest / ep)
    (dest / "lib").mkdir()
    for f in (Path(root) / "lib").glob("*.mjs"):
        shutil.copy2(f, dest / "lib" / f.name)
    shutil.copy2(Path(root) / "VERSION", dest / "VERSION")


def install_bridge(entry: dict, *, root: Path = BRIDGE_DIR,
                   dest_root: Path | None = None, unit_dir: Path = UNIT_DIR,
                   run=_run) -> dict:
    """Kód + bélyeg + unit + enable/disable a registry státusza szerint.
    NEM indít újra — azt a hívó dönti el (reconcile / rollout), mert a híd
    újraindítása a bejövő üzeneteket egy pillanatra leállítja."""
    agent = entry["agent"]
    if (entry.get("bridge") or {}).get("custom"):
        raise RuntimeError(f"{agent}: a híd egyedi (bridge.custom) — nem írom felül: "
                           f"{(entry.get('bridge') or {}).get('custom_note', '')}")
    dest_root = Path(dest_root) if dest_root else (Path.home() / ".config")
    dest = dest_root / agent / "sub-etha"
    copy_bridge(dest, root=root)
    version = bridge_version(root)
    stamp(dest / "bridge.mjs", version)

    unit_name = (entry.get("bridge") or {}).get("unit") or f"{agent}-telegram-bridge.service"
    # A HÍD env-fájlja NEM az ágensé: egy ágens saját <agent>.env-je az ágens
    # titkait tartja, a bot-token a telegram.env-ben él. 2026-09-17 01:22:
    # az ágens env-fájljával renderelt híd-unit 16× újraindult FATAL-lal. Ezért a
    # híd a `bridge.env_file`-t kapja, alapból telegram.env-et.
    env_file = f"%h/.config/{agent}/{(entry.get('bridge') or {}).get('env_file') or 'telegram.env'}"
    state_dir = f"%h/.config/{agent}"
    text = render_unit(entry, env_file=env_file, state_dir=state_dir)
    unit_path = Path(unit_dir) / unit_name
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    changed = not unit_path.exists() or unit_path.read_text() != text
    if changed:
        backup(unit_path)
        unit_path.write_text(text)
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "disable" if is_dormant(entry) else "enable", unit_name])
    return {"agent": agent, "dest": str(dest), "version": version,
            "unit": unit_name, "unit_changed": changed}


def bridge_status(agents: list[dict], dest_root: Path | None = None,
                  root: Path = BRIDGE_DIR) -> list[dict]:
    """Telepített vs. repó ágensenként: bélyeg + sha256-alapú `changed` lista."""
    dest_root = Path(dest_root) if dest_root else (Path.home() / ".config")
    current = bridge_version(root)
    rows = []
    for e in agents:
        d = dest_root / e["agent"] / "sub-etha"
        installed = read_stamp(d / "bridge.mjs")
        changed = drift_files(d, root)
        rows.append({"agent": e["agent"], "installed": installed, "current": current,
                     "drift": bool(changed), "changed": changed})
    return rows
