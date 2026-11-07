"""Unit + drop-in telepítése a HELYI boxon. Minden felülírt fájl időbélyeges
mentést kap; a `fleet install` sosem törli a régit. Minden írás egy
tranzakcióban (`fleet.txn`) megy: bukott lépésnél az előző állapot áll vissza.

Nincs SSH-ág: a telepítés azon a boxon fut, ahova az ágens kerül
(docs/workflows/new-agent.md, 0. pont). Egy "innen oda" telepítés
pontosan azt a kettős igazságot hozná vissza, amit ez a repó megszüntet.
"""
from __future__ import annotations
import datetime
import json
import shutil
from pathlib import Path

from fleet import TEMPLATES_DIR, CONFIG_DIR, REPO_ROOT, registry_dir
from fleet.registry import is_dormant
from fleet.render import render_unit
from fleet.txn import Txn, run_cmd as _run

UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


def backup(path: Path) -> Path | None:
    """Időbélyeges másolat a fájl mellé; None, ha nem volt mit menteni."""
    path = Path(path)
    if not path.exists():
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, dest)
    return dest


def fleet_root_for_units() -> str:
    """A repó gyökere, ahogy a unitok látják (%h-relatív, ha a home alatt van)."""
    home = Path.home()
    try:
        return "%h/" + str(REPO_ROOT.relative_to(home))
    except ValueError:
        return str(REPO_ROOT)


def ensure_mcp_empty(config_dir: Path = CONFIG_DIR, txn: Txn | None = None) -> Path:
    """A `--strict-mcp-config` üres listája. Egy fájl az egész flottának."""
    p = Path(config_dir) / "mcp-empty.json"
    if not p.exists():
        (txn or Txn()).write(p, json.dumps({"mcpServers": {}}) + "\n")
    return p


def drop_in_text(agent: str, *, template: str | None = None) -> str:
    text = template if template is not None else (TEMPLATES_DIR / "10-session-gate.conf.tmpl").read_text()
    return text.replace("@@AGENT@@", agent).replace("@@FLEET_ROOT@@", fleet_root_for_units())


def install_drop_in(entry: dict, *, unit_dir: Path = UNIT_DIR, run=_run, txn: Txn | None = None) -> Path:
    """A session-gate drop-in. ANY path that writes a unit MUST also call this."""
    t = txn or Txn(run)
    dest = Path(unit_dir) / f"{entry['unit']}.d" / "10-session-gate.conf"
    t.write(dest, drop_in_text(entry["agent"]))
    t.sh(["systemctl", "--user", "daemon-reload"])
    return dest


def unit_text_for(entry: dict) -> str:
    """A unit szövege a forrás szerint: sablonból renderelve, vagy a kézzel
    írt fájl a registry `units/` könyvtárából (unit_source: file). A kézzel
    írt unit példány-adat, ezért a registry mellett él, nem a termékben."""
    if entry.get("unit_source") == "file":
        src = registry_dir() / "units" / entry["unit"]
        if not src.exists():
            raise FileNotFoundError(f"unit_source=file, de nincs {src}")
        return src.read_text()
    return render_unit(entry, template=(TEMPLATES_DIR / "agent.service.tmpl").read_text(),
                       fleet_root=fleet_root_for_units())


def install_unit(entry: dict, *, unit_dir: Path = UNIT_DIR, run=_run,
                 enable: bool | None = None, txn: Txn | None = None,
                 config_dir: Path = CONFIG_DIR) -> dict:
    """Unit írása + drop-in + daemon-reload + enable/disable, minden hívás
    kódja ellenőrizve. NEM indít: az indítást és a postchecket a
    `fleet.install_flow` végzi. Ha `enable` None, a registry státusza dönt.

    Saját tranzakció (txn=None) esetén hibánál visszaállít és `StepFailed`-et
    dob; kapott tranzakciónál a visszaállítás a hívóé."""
    own = txn is None
    t = txn or Txn(run)
    try:
        ensure_mcp_empty(config_dir, t)
        unit_dir = Path(unit_dir)
        dest = unit_dir / entry["unit"]
        existed = dest.exists()
        text = unit_text_for(entry)
        saved = backup(dest) if existed and dest.read_text() != text else None  # emberi mentés is
        changed = t.write(dest, text)
        drop_in = install_drop_in(entry, unit_dir=unit_dir, txn=t)
        want_enabled = (not is_dormant(entry)) if enable is None else enable
        verb = "enable" if want_enabled else "disable"
        # a visszaállítás a KORÁBBI engedélyezettséget állítja vissza, nem a fordítottját
        was_enabled = existed and t.try_sh(["systemctl", "--user", "is-enabled", entry["unit"]]
                                          ).stdout.strip() == "enabled"
        t.sh(["systemctl", "--user", verb, entry["unit"]],
             undo=None if was_enabled == want_enabled else
             ["systemctl", "--user", "enable" if was_enabled else "disable", entry["unit"]])
    except Exception:
        if own:
            t.rollback()
        raise
    return {"unit": str(dest), "changed": changed, "existed": existed,
            "backup": str(saved) if saved else None,
            "drop_in": str(drop_in), "enabled": want_enabled}
