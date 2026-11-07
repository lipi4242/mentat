# Példa-registry

Kitalált flotta (`demo-agent`, `demo-helper`, egy `demo-box`) a tesztekhez és
a kipróbáláshoz. A saját flottád registryje egy külön (privát) könyvtárban vagy
repóban él, ugyanebben a szerkezetben:

```
agents.json      # ágensek: hol és hogyan fut
boxes.json       # gépek
accounts.json    # külső fiókok (csak azonosítók, titok nélkül)
runbooks/        # ágensenkénti runbook; az agents.json `runbook` mezője ehhez a könyvtárhoz relatív
units/           # opcionális: kézzel írt unitok (unit_source: file)
```

```sh
FLEET_REGISTRY=examples/registry PYTHONPATH=src python3 -m fleet.cli validate
```
