# Példa-registry

Kitalált flotta (`demo-agent`, `demo-helper`, egy `demo-box`) a tesztekhez és
a kipróbáláshoz. A saját flottád registryje egy külön (privát) könyvtárban vagy
repóban él, ugyanebben a szerkezetben:

```
agents.json      # ágensek: hol és hogyan fut
boxes.json       # gépek
accounts.json    # külső fiókok (csak azonosítók, titok nélkül)
fleet-map.json  # flottatérkép: ki kicsoda, ki kinek jelent, ki melyik repó gazdája (séma: `src/fleet/fleet_map.py`)
runbooks/        # ágensenkénti runbook; az agents.json `runbook` mezője ehhez a könyvtárhoz relatív
units/           # opcionális: kézzel írt unitok (unit_source: file)
```

```sh
FLEET_REGISTRY=examples/registry PYTHONPATH=src python3 -m fleet.cli validate
```

A `fleet-map.json` a flotta szerepeit írja le (tulajdonos, menedzser, ágensenként
szerep, felelősség, jelentési lánc, repók). Ellenőrzése: `fleet map validate`
(`--json` géplesz kimenet; kilépés 0 rendben · 1 hiba · 2 nincs/olvashatatlan fájl).
