---
name: roster
description: Ki van a flottában és ki elérhető most — a registry, a ListAgents és a box-szonda három külön oszlopban. Használd, mielőtt egy másik ágensnek írnál, vagy ha kérdés, ki fut.
---

# /fleet:roster — ki elérhető

Három forrás, három oszlop. **Nem keverhetők**: „nincs a listában", „nem fut"
és „nem mérhető" három különböző mondat.

## Lépések

1. **Registry** — ki tag, milyen néven, melyik boxon, kívánt állapota:
   - Ha ezen a gépen van Mentat-checkout (a `fleet` parancs: `command -v fleet`,
     különben `~/src/mentat/fleet/bin/fleet`)
     és be van állítva a registry (`FLEET_REGISTRY` vagy
     `~/.config/fleet/registry`): `fleet roster --no-probe`.
   - Ha nincs checkout, de a registry-könyvtár elérhető: `python3 -c 'import json,sys;
     [print(a["agent"], a.get("status","active"), a.get("host"), a.get("rc_name",a["agent"])) for a in json.load(open(sys.argv[1]))]' "$FLEET_REGISTRY/agents.json"`
   - Ha egyik sincs: a registry oszlop „nem mérhető"
2. **ListAgents** — ki él most a natív csatornán. Futtasd a `ListAgents`
   eszközt. Egy `Remote Control · offline` sor NEM azt jelenti, hogy az
   ágens halott: csak hogy az RC-je nincs bekötve. A generált nevű sorok
   (`macbook-pro-local-*`, feladatcímek) a tulajdonos saját sessionjei.
3. **Box-szonda** — ha a boxon vagy: `fleet roster` (a `processz` oszlop
   a claude-processz létét mutatja a várt `--remote-control` névvel).

## Kimenet

Egy tábla, ágensenként: `flottanév · kívánt · host · RC-listában? · processz`.
Ahol egy forrás nem mérhető, írd ki, hogy nem mérhető — ne hagyd üresen.

## Csapdák
- A SendMessage-cím (`<mappa>-<hash>`) minden indulásnál más. Ne írd le fixen.
- A `--remote-control` név ≠ flottanév lehet (rövidebb, kézzel adott név):
  a registry `rc_name` mezője mondja meg.
