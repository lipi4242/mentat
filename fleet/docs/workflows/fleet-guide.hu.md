# A flotta részletei

A [README](../../README.hu.md) háttere: a registry, a rétegek, hogyan dönt a felügyelet, mi fut a boxon, és a tesztek.

## A registry

A registry nem része ennek a repónak, a saját könyvtáradban él. A `fleet` a registry könyvtárát így keresi, ebben a sorrendben:

1. a `FLEET_REGISTRY` környezeti változó;
2. a `~/.config/fleet/registry` fájl (egyetlen sor: a könyvtár útvonala);
3. ha egyik sincs, vagy nem létező könyvtárra mutat: hibával megáll
   („nincs registry beállítva: …"). Nincs csendes alapérték.

```sh
export FLEET_REGISTRY=~/fleet-config/fleet          # egy sessionre
echo ~/fleet-config/fleet > ~/.config/fleet/registry  # tartósan, a boxon (a timerek ezt olvassák)
```

A registry szerkezete (a példa: `examples/registry/`, kitalált ágensekkel):

| fájl | mit ír le |
|---|---|
| `agents.json` | HOL és HOGYAN fut egy ágens: host, unit, session, `rc_name`, `status` (`active`/`dormant`), kadencia, híd, `claude_account` |
| `boxes.json` | a gépek (`key`, `hostname`, …) |
| `accounts.json` | külső fiókok azonosítói, titok nélkül |
| `runbooks/` | ágensenkénti runbook; az `agents.json` `runbook` mezője ehhez a könyvtárhoz relatív |
| `units/` | opcionális: kézzel írt unitok (`unit_source: file`) |

A `fleet init` ezt a minimumot maga írja (`~/.config/fleet/registry.d`).
Titok (token, kulcs) nem kerül a registrybe: a bot-token a boxon,
`~/.config/<agent>/telegram.env`-ben él (0600).

## A rétegek

| réteg | hol | mit tud |
|---|---|---|
| **Futtató** | `src/fleet/` (stdlib Python), `bin/fleet` | `init`, `validate`, `preflight`, `render`/`install`, `bridge install`/`status`, `reconcile` (timer), `postcheck`, `doctor`, `roster`, `stop`/`wait-up`/`restart`, `lock`/`unlock`/`unquarantine`, `join`/`upgrade`, `status`, `release`, `secrets` |
| **Híd** | `bridge/` (Node) | Telegram ↔ tmux: `bridge.mjs` (poller, inbox, health), `send.mjs` (plain text; `--html` szűrt formázás) |
| **Plugin + sablonok** | `plugin/`, `templates/` | a skillek és a SessionStart hook; unit-sablon (`--remote-control`, `--strict-mcp-config` beépítve), drop-in, `rules/fleet.md.tmpl`, systemd-timerek |

A szerkezeti szabály: a futtató **csak a registryből olvas**, és csak
stdlibet használ. A híd Node, de a futtató nem importálja — unitot ír neki.

## Felügyelet: az öt jel

| jel | forrás | ha rossz |
|---|---|---|
| **processz** | fut-e a `claude` a várt `--remote-control <név>`-vel | restart (3/óra), utána postcheck |
| **ütemezés** | `last-tick.json` / tick-marker a transzkriptben; ha a flotta ütemez (`schedule_owner: fleet`), a `last-tick.json` a `fleet-tick-<név>.timer` periódusához mérve — `proactive: false` mellett is | re-arm (csak a claude-loopnak); 12 periódus (vagy `silence_after_s`) után riasztás |
| **csatorna** | a híd `health.json`-ja + 409 a journalban | poller leölése / híd-restart (költségvetéssel) |
| **RC** (opcionális) | a transzkript RC-eseményei — csak esemény, nem állapot | jelentés; az állapotot a `/fleet:roster` (ListAgents) méri; nem mérhetően `n/a`, a kilépési kódot nem rontja |
| **auth** | `authentication_failed` assistant-rekord a transzkriptben, utána nincs valódi válasz | riasztás (restart nem gyógyítja): `claude auth login` azon a boxon |

Mindegyiknek van `unknown` értéke, és az nem `down` és nem `ok`. A `fleet
doctor` minden jelet `healthy` · `pending` · `unknown` · `unhealthy` szerint
ítél, az ágens a legrosszabb jelét kapja, és csak a teljes `healthy` OK
(kilépési kód 0). Kivétel az RC: opcionális jel, nem mérhetően `n/a` (➖),
és nem rontja az ítéletet — a bizonyított leszakadás viszont hiba. Egy
indítási ablaknál álló tmux-pane hiba, akkor is, ha a processz fut; a `--fix` sikere a javítás utáni újramérés. Egy restart
akkor „kész", ha a **postcheck** zöld: új processz-generáció, nincs
telegram-plugin poller, nincs 409, az auth él, és a restart UTÁN landolt tick
(a türelmi időn belül `pending`, utána bukás; az RC nem kötelező, mert a
visszakapcsolódás nem naplózódik). Két bukott postcheck
→ karantén, riasztás, ember oldja fel.

`dormant` = kívánt állapot: a reconcile leállítja és letiltja, ami fut. A
`systemctl disable` önmagában nem üzen a felügyeletnek.

## Mi fut a boxokon

| timer | periódus | mit csinál |
|---|---|---|
| `fleet-reconcile` | `templates/systemd/fleet-reconcile.timer` | az EGY vezérlő: a registry kívánt állapota + postcheck, OOM-védelem (-600), tick re-arm, duplikáció-riasztás |
| `fleet-reconcile-fast` | 30 mp | gyors út (`reconcile --fast`): CSAK a két egymás utáni megfigyelésben hiányzó claude-processzt indítja újra (≤~1 perc); híd, riasztás, re-arm marad a teljes körön — ezek nem gyorsíthatók (a 409 elmúlása percekbe telik, a költségvetést a hatás előtt égetné el) |
| `fleet-tick-<ágens>` | a motor ütemezése szerint | a motor tick-belépője, ha a join átvette az ütemezést |

A heartbeatet csak a motor írja; a felügyelet a transzkript korát és a
`last-tick.json`-t olvassa (a régi `agent-liveness.timer` maga is
írta a heartbeatet, ezt a `fleet install` leveszi). A sablonok a
`templates/systemd/` alatt; a checkout útvonalát a telepítés helyettesíti be.
Ha ugyanaz az ágens egy másik gépen (a registry `host`-ja szerint) EZEN a
gépen is fut, a reconcile és a doctor riaszt. A tulajdonjog a `~/.config/fleet/controller` fájlban
(`reconcile`); nélküle a reconcile csak megfigyel. A box kulcsa:
`FLEET_HOST` vagy `~/.config/fleet/host`, különben a `boxes.json` `hostname`
mezője; ismeretlen gépen nincs alapértelmezett box.

## Titkok egy közös boxon

Egy box ágensei egy Unix-felhasználón futnak, így bármelyik olvashatja a másik kulcsait és
átiratait. A `fleet secrets` úgy dolgozik, hogy érték egyetlen Claude-kontextusba se kerüljön:

| parancs | mit csinál |
|---|---|
| `fleet secrets scan --agent A [--agent B]` | a titokfájlok neve, helye, formátuma és kulcsnevei (repó, `~/.config/<a>/`, `~/.claude-<a>/`, `<repó>/.mentat/`, unit `EnvironmentFile=`), érték nélkül; `~/.mentat/titkok/leltar.json` (0600), és felteszi a titok-kaput |
| `fleet secrets approve --item OP:NÉV:HONNAN:HOVA:MIÉRT --owner-text "…"` | tételes tulajdonosi jóváhagyás, legfeljebb 60 percig, tételenként egyszer |
| `fleet secrets move\|copy --name K --from X --to Y --approval ID` | egy kulcs átvitele folyamaton belül, 0600, atomikusan, symlink nélkül; nyugta: `~/.mentat/titkok/nyugtak.jsonl` |
| `fleet secrets audit [--repo DIR]` | került-e leltárban lévő érték átiratba, repóba vagy git-történetbe (csak fájl:sor) |
| `fleet secrets hook install\|status` | a titok-kapu (PreToolUse, csak tilt) a box minden `~/.claude*/settings.json`-jában |

A kapu nem engedi megnyitni a leltárban lévő vagy kulcsnevű fájlt, más ágens átiratát, és a
környezet kiírását, `cat`/`sed`/`python`/`cp`/`ln`/glob útján sem. v1 korlátai: közös
Unix-felhasználó, a jóváhagyás-fájlt az ágens is megírhatja, és egy elszánt szereplő egy hookot
megkerülhet. v2: sandbox denyRead, ágensenként külön Unix-felhasználó, a híd által aláírt
jóváhagyás, `fleet secrets run --as` burkoló.

## Tesztek

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src python3 -m unittest discover -s src/fleet -p 'test_*.py' -q
node --test "bridge/test/*.test.mjs"
FLEET_REGISTRY=examples/registry PYTHONPATH=src python3 -m fleet.cli validate
```

A Python-tesztek a `pytest` csomagot is importálják (a tesztek unittest és
pytest alatt is futnak), ezért az legyen telepítve. A registry-konzisztencia
tesztjei (`tests/test_registry_consistency.py`,
`tests/test_registry_runbook_egyezes.py`) alapból a példa-registryt nézik;
`FLEET_REGISTRY`-vel a saját registrydre is lefuttathatók.

## Ami szándékosan nincs itt

- A konkrét flotta adatai (registry, runbookok, ops-jegyzetek) — tartsd
  egy saját könyvtárban vagy repóban.
- A szoba-alapú ágens-közi kommunikáció (rooms, post, follow) és a korábbi
  flotta-vezérlő ágens; a natív Claude Code csatorna (`ListAgents` /
  `SendMessage`) váltotta ki. A híd 2.0-tól csak kézbesítési naplót vezet
  ([`bridge/docs/delivery-log.md`](../../bridge/docs/delivery-log.md)).
