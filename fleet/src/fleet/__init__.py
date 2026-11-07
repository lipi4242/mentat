"""fleet — az always-on ágensek futtatásának, felügyeletének és telepítésének
egyetlen csomagja. Csak stdlib; csak a registryből olvas.

A registry (agents.json, boxes.json, …) NEM a csomag része: egy konkrét
flotta példány-adata, külön (privát) helyen él. Az útvonalát a
`registry_dir()` oldja fel, minden híváskor újra.
"""
import os
from pathlib import Path

#: A csomag verziója. Ugyanez a szám él a plugin manifestjében és a
#: `bridge/VERSION`-ben csak akkor egyezik, ha a release-tuple azt mondja —
#: a három réteg külön verziózódik, a `fleet release` írja össze őket.
__version__ = "1.3.0"

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
BRIDGE_DIR = REPO_ROOT / "bridge"
PLUGIN_DIR = REPO_ROOT / "plugin"

#: A box-oldali futásidejű állapot (restart-számlálók, host-név, release-tuple).
#: Nem a repóban él: gépenként más, és nem verziózott tudás.
CONFIG_DIR = Path.home() / ".config" / "fleet"

#: A registry helyét megadó környezeti változó.
REGISTRY_ENV = "FLEET_REGISTRY"


class RegistryNotConfigured(RuntimeError):
    """Nincs (érvényes) registry beállítva. Szándékosan nem üres lista: egy
    hiányzó registry nem azt jelenti, hogy „nincs ágens"."""


def registry_pointer_file(home: Path | None = None) -> Path:
    """A `~/.config/fleet/registry` fájl — egy sor: a registry könyvtára.
    Híváskor számolva; a `home` ugyanaz, amit a hívó a többi írásához használ
    (2026-10-18: a `fleet init` a kapott home alá írta a registry.d-t, de a
    mutatót a $HOME alá — a valódi ~/.config/fleet/registry így jött létre)."""
    return Path(home or Path.home()) / ".config" / "fleet" / "registry"


def registry_dir(home: Path | None = None) -> Path:
    """A registry könyvtára. Sorrend:

      1. `FLEET_REGISTRY` környezeti változó;
      2. `~/.config/fleet/registry` fájl (egyetlen útvonal benne);
      3. hiba (`RegistryNotConfigured`), érthető üzenettel.

    Nincs csendes alapérték: a régi „a repó `fleet/` mappája" visszaesés
    pont azt rejtené el, hogy a termék és a példány-adat szétvált.
    """
    env = os.environ.get(REGISTRY_ENV, "").strip()
    pointer = registry_pointer_file(home)
    if env:
        source, raw = f"{REGISTRY_ENV} környezeti változó", env
    else:
        try:
            raw = pointer.read_text().strip()
        except OSError:
            raw = ""
        source = str(pointer)
        if not raw:
            raise RegistryNotConfigured(
                f"nincs registry beállítva: sem a {REGISTRY_ENV} környezeti változó, "
                f"sem a {pointer} fájl nem ad útvonalat. Állítsd be például így: "
                f"export {REGISTRY_ENV}=/út/a/registryhez (a könyvtárban agents.json, boxes.json)")
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = (Path.cwd() / p) if env else (pointer.parent / p)
    if not p.is_dir():
        raise RegistryNotConfigured(
            f"nincs registry beállítva: a(z) {source} ({raw!r}) nem létező könyvtárra mutat")
    return p
