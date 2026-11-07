"""A registry nem mondhat ellent önmagának.

MIÉRT LÉTEZIK EZ A FÁJL. Éles eset (2026-08): három ágens kadenciája
félóráról 17 órára változott. A telepített unitokat átírták `:startup`-ra, a
`tick_period_s`-t 61200-ra — de a `loop_cmd` mezőben ottmaradt a `/loop 30m`.
Az érték nem hibás adat volt, hanem egy IGAZ adat, amit körbenőtt a világ.
Hetekig senki nem javította, mert a két meglévő ellenőrzés egyike a rossz
oldalt nevezte deviációnak, a másik a registryt a SABLONHOZ mérte — és a két
elavult másolat tökéletesen egyetértett.

A tét nem esztétikai: a `liveness.py` a re-armkor a registryből olvassa a
`loop_cmd`-et és betmuxolja. Ha elsül, egy 17 órás kör helyett félórásat indít
— 34-szeres tick-szám, valódi pénz.

A SZŰRŐ. Nem string-illesztés és nem törlés: ott bukj, ahol a `loop_cmd`-ben
DEKLARÁLT periódus ellentmond a `tick_period_s`-nek. Egy ágens, akinél a
`/loop 30m` helyes (mert a periódusa tényleg 1800), strukturálisan esik ki,
nem kivételként.

A 2. eset (nincs deklarált periódus) a lényeg: ettől marad az állítás
ÉRTELMES a `:startup`-ra átírás UTÁN is — nincs mit összemérni, tehát nincs
mit állítani.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)

import json
import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
#: A vizsgált registry: a FLEET_REGISTRY, ha be van állítva (így a saját
#: flottád registryjére is lefuttatható), különben a példa-registry.
REGISTRY_DIR = Path(os.environ.get("FLEET_REGISTRY") or REPO_ROOT / "examples" / "registry")
REGISTRY = REGISTRY_DIR / "agents.json"

#: `/loop 30m …`, `/loop 2h …`, `/loop 90s …` — a periódust DEKLARÁLÓ alak.
#: Ami nem illeszkedik (tipikusan `/<agens>:startup`), az nem deklarál semmit.
LOOP_PERIODUS = re.compile(r"^/loop\s+(\d+)\s*([smh])\b")

EGYSEG_S = {"s": 1, "m": 60, "h": 3600}


def deklaralt_periodus_s(loop_cmd: str | None) -> int | None:
    """A `loop_cmd`-ben deklarált periódus másodpercben, vagy None.

    None azt jelenti: ez a parancs nem mond semmit a kadenciáról — nem azt,
    hogy nulla. A kettő összekeverése pontosan az a hibaosztály, ami miatt ez
    a fájl létezik.
    """
    if not loop_cmd:
        return None
    m = LOOP_PERIODUS.match(loop_cmd.strip())
    if not m:
        return None
    return int(m.group(1)) * EGYSEG_S[m.group(2)]


class TestRegistryOnkonzisztencia(unittest.TestCase):
    def setUp(self):
        self.reg = json.loads(REGISTRY.read_text())

    def test_registry_nem_ures(self):
        """Anti-vákuum: üres registryn az alábbi ciklus némán átmenne."""
        self.assertTrue(
            self.reg,
            "üres agents.json — csonkolt fájl vagy rossz útvonal, nem 'nincs ágens'",
        )

    def test_loop_cmd_periodus_egyezik_a_tick_period_s_szel(self):
        sertok = []
        vizsgalt = 0

        for e in self.reg:
            dekl = deklaralt_periodus_s(e.get("loop_cmd"))
            if dekl is None:
                continue  # nem deklarál periódust — nincs mit összemérni
            vizsgalt += 1
            tick = e.get("tick_period_s")
            if dekl != tick:
                sertok.append(
                    f"{e['agent']}: loop_cmd {dekl}s-t deklarál, "
                    f"tick_period_s={tick}s ({dekl / max(tick or 1, 1):.0f}x eltérés)"
                )

        self.assertEqual(
            sertok,
            [],
            "A registry ellentmond önmagának:\n  " + "\n  ".join(sertok),
        )
        # Ha ez nullára csökken, az állítás vakuummá vált: senki nem deklarál
        # periódust, tehát a szabály nem véd semmit. Ilyenkor a fájl törlendő
        # vagy újragondolandó — de NEM csendben, ezért bukik itt.
        self.assertGreater(
            vizsgalt,
            0,
            "egyetlen loop_cmd sem deklarál periódust — az állítás vakuummá vált, "
            "nézd meg, hogy még véd-e bármit",
        )


if __name__ == "__main__":
    unittest.main()
