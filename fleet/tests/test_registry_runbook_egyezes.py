"""Ahol a `loop_cmd` nem deklarál periódust, a runbook igen — és a kettőnek egyeznie kell.

MIÉRT LÉTEZIK EZ A FÁJL. A testvérmodul
(`test_registry_consistency.py`) szándékosan NÉMA arra az ágensre, aminek a
`loop_cmd`-je `/<agens>:startup` — ott tényleg nincs mit összemérni. A
következmény: az ilyen ágensek `tick_period_s`-ére EGYETLEN állítás sem
vonatkozott.

Éles eset (2026-09): egy ágens registry-periódusa 21480 (5,97 ó) volt, amiből
a `staleness_min_for` 1074 percet, 17,9 órát számol; a valós kadenciája 30
perc. MIKÖZBEN a saját runbookja helyesen ezt írta: "ticks every 30 min". A
helyes szám a registry-repóban VOLT, csak nem abban a fájlban, amit a
felügyelet betölt.

A SZŰRŐ. Ott bukj, ahol a runbook prózában kimondott kadenciája ellentmond a
registry `tick_period_s`-ének. A runbook útvonala a registry könyvtárához
relatív. Az anti-vákuum állítás alul bukik, ha a vizsgált esetek száma
nullára csökken, tehát a szabály nem tud csendben jelentéktelenné válni.
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

#: "ticks every 30 min", "ticks every 2 hours" — a runbook prózában kimondott
#: kadenciája. Csak az angol alak: a magyar változatok ("félóránként") túl
#: sokfélék ahhoz, hogy egy regex igaz állítást tegyen róluk, és egy pontatlan
#: minta itt HAMIS egyezést adna, ami rosszabb a hiányzónál.
RUNBOOK_KADENCIA = re.compile(r"ticks?\s+every\s+(\d+)\s*(min|minutes?|h|hours?)\b", re.I)

EGYSEG_S = {"min": 60, "minute": 60, "minutes": 60, "h": 3600, "hour": 3600, "hours": 3600}


def runbook_periodus_s(szoveg: str) -> int | None:
    """A runbookban kimondott periódus másodpercben, vagy None ha nem mond ilyet."""
    m = RUNBOOK_KADENCIA.search(szoveg)
    if not m:
        return None
    return int(m.group(1)) * EGYSEG_S[m.group(2).lower()]


class TestRegistryRunbookEgyezes(unittest.TestCase):
    def setUp(self):
        self.reg = json.loads(REGISTRY.read_text())
        self.assertTrue(self.reg, "üres agents.json — csonkolt fájl, nem 'nincs ágens'")

    def test_runbook_kadencia_egyezik_a_tick_period_s_szel(self):
        sertok = []
        vizsgalt = 0

        for e in self.reg:
            rb = e.get("runbook")
            if not rb:
                continue
            p = REGISTRY_DIR / rb
            if not p.is_file():
                continue
            kimondott = runbook_periodus_s(p.read_text())
            if kimondott is None:
                continue  # a runbook nem mond kadenciát — nincs mit összemérni
            vizsgalt += 1
            tick = e.get("tick_period_s")
            if kimondott != tick:
                sertok.append(
                    f"{e['agent']}: {rb} {kimondott}s-t mond, "
                    f"tick_period_s={tick}s → staleness {3 * (tick or 0) // 60} perc"
                )

        self.assertEqual(
            sertok,
            [],
            "A registry ellentmond a saját runbookjának:\n  " + "\n  ".join(sertok),
        )
        self.assertGreater(
            vizsgalt,
            0,
            "egyetlen runbook sem mond kadenciát — az állítás vakuummá vált, "
            "nézd meg, hogy még véd-e bármit",
        )


if __name__ == "__main__":
    unittest.main()
