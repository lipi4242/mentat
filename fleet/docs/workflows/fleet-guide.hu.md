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
| `fleet secrets scan --agent A [--agent B]` | a titokfájlok neve, helye, formátuma és kulcsnevei (repó, `~/.config/<a>/`, `~/.claude-<a>/`, `<repó>/.mentat/`, unit `EnvironmentFile=`), érték nélkül; `~/.mentat/titkok/leltar.json` (0600). A kaput NEM teszi fel, az összeolvasztás-módot nem kapcsolja; ha a kapu él és az új leltár egy ágens alapfunkcióját tiltaná, a régi leltár marad. `--dry-run`: csak a táblázat |
| `fleet secrets approve --item OP:NÉV:HONNAN:HOVA:MIÉRT --owner-text "…"` | tételes tulajdonosi jóváhagyás, legfeljebb 60 percig, tételenként egyszer |
| `fleet secrets move\|copy --name K --from X --to Y --approval ID` | egy kulcs átvitele folyamaton belül, 0600, atomikusan, symlink nélkül; nyugta: `~/.mentat/titkok/nyugtak.jsonl` |
| `fleet secrets audit [--repo DIR]` | került-e leltárban lévő érték átiratba, repóba vagy git-történetbe (csak fájl:sor) |
| `fleet secrets hook install [--dry-run\|--force]\|status` | a titok-kapu (PreToolUse, csak tilt) a box minden `~/.claude*/settings.json`-jában. Előtte essentials-próba: minden ágens alapfunkciója (Telegram-küldés két alakban, `mentat-todo me/changes`, a `~/.config/<a>/jobs/` szkriptek, `git status/commit/push`, a saját motor- és review-állapot olvasása) a JELÖLT kapun, plusz hogy a hidas ágens unitjában van-e `TELEGRAM_BOT_TOKEN` (név szerint); piros ágensnél nem ír semmit. Utána kanári: egy gyökér, újrapróba, csak aztán a többi |

Mi kerül a leltárba: a név (kulcsfájl-minta) vagy a tartalom bizonyítéka (privát kulcs, titok-nevű
kulcs/mező értékkel) — a fájlmód egyedül soha. A privát, bizonyíték nélküli ismeretlen fájl
„átnézendő": kiírva, de a kapu nem tiltja. A kapu név-alapú (gyanús) tiltásánál bejelentést kér, nem
kerülőutat; rekurzív keresésnél a mappát `grep -r --exclude-dir=<mappa>` zárja ki.

### Az ágens futásidejű szerződése

- **Env:** a unit pane-shellje (`ExecStart … /bin/sh -c`) tölti be az env-fájlokat — tmux alatt az
  `EnvironmentFile=` önmagában nem jut el a claude-ig. Sorrend: hidas ágensnél ELŐBB a híd
  `telegram.env`-je (`bridge.env_file`), aztán a registry `env_files` / `env_file` fájljai (az ágensé
  írja felül a közös kulcsot), aztán `claude-auth.env` és `.mentat/model.env`. `FLEET_AGENT` mindig.
- **Küldés:** `node ~/.config/<a>/sub-etha/send.mjs --chat <id> [--reply-to <id>] -- "szöveg"` vagy
  `--text-stdin`; a token a fenti env-ből jön, a telegram.env-et az ágens nem tölti be. Token
  nélkül a send.mjs `missing_token` notice-t ír a kézbesítési naplóba, a doctor ettől piros.
- **Olvashat:** a saját repóját és állapotát (`data/state/`, a motor és a review állapotfájljai), a
  saját `~/.config/<a>/jobs/` szkriptjeit futtathatja; NEM olvashat kulcsfájlt, leltárfájlt, más
  ágens átiratát, és a környezetet nem írja ki.
- **Ellenőrzés:** `fleet doctor <a>` — a telepített kapun futtatja az essentials-t, és nézi a token
  nevét a unit env-fájljaiban. Boxszintű parancs (`hook install`, `scan`, `merge-mode on`,
  `install`) előbb `--dry-run`-nal.

A kapu nem engedi megnyitni a leltárban lévő vagy kulcsnevű fájlt, más ágens átiratát, és a
környezet kiírását, `cat`/`sed`/`python`/`cp`/`ln`/glob útján sem. v1 korlátai: közös
Unix-felhasználó, a jóváhagyás-fájlt az ágens is megírhatja, és egy elszánt szereplő egy hookot
megkerülhet. v2: sandbox denyRead, ágensenként külön Unix-felhasználó, a híd által aláírt
jóváhagyás, `fleet secrets run --as` burkoló.

### Képesség, központi flotta-ellenőrzés, kanári, kiadás-lemaradás

- **Képesség-próba** (`kepesseg.py`): a doctor és minden postcheck (restart, install, box-upgrade)
  le is FUTTATJA az alapfunkciókat, korlátosan (lépésenként 20 s, Telegram-hívás nélkül):
  `send.mjs --dry-run --chat $TELEGRAM_GROUP_CHAT_ID` a unit env-fájljaival (a token megvan és jó
  alakú, chat, kapcsolók, hosszúság-kapu, írható kézbesítési napló), `mentat-todo me` (ha a boxon van
  `~/.config/todo/env`), a saját állapotfájlok olvasása, `git status` a repóban. Bármelyik hibája
  piros; a postcheckben `failed`, `capability_only` jellel (restart nem javítja, ezért nincs karantén).
- **Központi flotta-ellenőrzés (1.0-s képesség), külön riasztó bot nélkül:** a reconcile
  ágensenként legfeljebb 15 percenként mér, és 10 percenként jelenti az eredményt (a box nevével, a
  flotta verziójával és a kiadás-lemaradással) a Mentat Admin `flotta` pluginjának; beállítás:
  `~/.config/fleet/flotta.env` (`FLOTTA_URL` + `FLOTTA_TOKEN`, egy box-token, aminek egyetlen jogköre a
  `flotta:report`; az értéke sehol nem jelenik meg). A piros ellenőrzés ott (ágens, ellenőrzés)
  páronként egy incidenst nyit; a legkisebb rangú illetékes és ép felelős ágens (menedzser) todo-feladatként kapja (`[flotta] …`, a
  `flotta-incidens` skill), a kísérleteit kommentbe írja, a következő zöld jelentés lezárja az
  incidenst és a feladatot. A 30 percig nem jelentő box dead-man incidenst nyit. A tulajdonosnak egy
  Worker-cron ír e-mailt (LLM nincs az úton): 60 perc után; azonnal, ha egy menedzsert érint és nincs ép
  helyettes; illetékes menedzser nélkül 2 piros jelentés után; nyitva 6 óránként újra; a megoldáskor egy rövid
  „Megoldva”. A bukott jelentés (10 s időkorlát) a reconcile-t soha nem töri el: a piros képesség
  ilyenkor a `~/.config/fleet/state/alerts-undelivered.jsonl`-be kerül, a doctor box-sora piros, amíg
  ott van, és `jelentés: elavult`-at mutat; a fájl nélkül `jelentés: kikapcsolva`. Piros képesség a
  beteg ágens saját hídján soha nem megy. Beállítás: `admin/docs/plugins/flotta/INSTALL.md`.
- **Flotta-menedzser szerep (flotta-menedzser).** A menedzsereket a verziózott `fleet/managers.json` sorolja
  fel (fleet-ops; példa: `fleet/examples/managers.json`), és a `fleet managers publish` tölti fel,
  külön `flotta:config` tokennel. Egy cél lánca `agent:` > `box:` > `*` sorrendű, azon belül rang,
  aztán handle. Csak az kerül bele, aki eléri a célt (v1: a saját boxát) és javításra alkalmas.

  A menedzser átveszi (`fleet incident claim`), és 30 perces keretet meg fencing-tokent kap.
  Csak a `fleet repair-exec`-en át javít (engedélylista; zár → Worker-ellenőrzés → szándék →
  végrehajtás → eredmény), és az incidenst csak a `repair-exec … postcheck` zárja, ellenőrző
  nonce-szal. Ha senki nem veszi át, lejár a keret, vagy a menedzser alkalmatlanná válik, a
  következő kapja; ha a lánc üres vagy elfogy, ember (e-mail).

  A jelentés ágensenként viszi az utolsó lefutott tickjét (`last-tick.json`, csak a tick írja).
  A saját gépen futó tag (`supervision: none`) a saját sessionjéből jelent: `fleet flotta-report`.
  A tick-timer kihagy, amíg az ágensen `fleet lock` van.

  Terv: `fleet/docs/design/2026-11-08-flotta-menedzser.md` (monorepó); skill: `flotta-incidens`.
- **Kanári a felhasználói beállításokra** (`kanari.py`): aki a `~/.claude*/settings.json` hookjait, a
  `skills/` linkeket vagy a `claude plugin …` állapotát írja (első indítás, operátor-skill, plugin
  install, titok-kapu), az előbb az első ágenses gyökeret írja, megpróbálja az ágenseit, ÚJ pirosnál
  visszaáll, csak aztán a többit, és lenyomatot rögzít. A doctor box-sora jelez, ha egy gyökér
  rögzített kanári-futás nélkül változott; kézi változás után: `fleet canary record`.
- **Todo-ébresztés:** ha a todóban egy ágensre kerül a labda, egy percen belül megtudja, nem
  a következő óránkénti ticknél. A Telegram-híd (LLM nélkül) 20 s-onként (legfeljebb 60 s,
  `BRIDGE_TODO_POLL_MS`) lekéri a `GET /changes?for=<handle>`-t a box todo-beállításával
  (`~/.config/todo/{env,handles,<handle>.token}`, a token sehol nem jelenik meg), a saját kurzorát a
  `telegram-state/todo-state.json`-ban tartja, az ágens saját írásait kihagyja, és EGY sort ír a
  pane-be a Telegram-sorok stílusában: `[Todo | ABC-12 | kiadta: thufir_mac | wake=<seq>]: cím: «<cím>»` (csak szerkezeti mezők, a cím tisztítva, ~80 karakterre vágva, ADAT-ként jelölve; komment-törzs soha — a tartalmat az ágens a tételen olvassa el; „láttam, nincs teendő”: `mentat-todo ack <kulcs>`, ez a nyugta, és senkit nem ébreszt)
  (egy percen belül érkezőknél egy lista; foglalt ágensnél sorba áll, mint a Telegram). Ébreszt: neki
  kiadták, visszakerült hozzá, megemlítették, az ő elfogadására vár, komment ott, ahol nála a labda;
  nem ébreszt: puszta mezőváltozás, mások egymás közti forgalma. Az ágensek korlát nélkül
  beszélgethetnek kommentben; csak a nyilvánvaló elszabadulás (egy tételen 10 percen belül 8
  tartalom nélküli komment legalább két szerzőtől) gyűlik 5 percig, és az mindig jelez
  (`todo_runaway` notice + egy sor a csoportnak), semmi nem vész el. Nyugta: a sor megjelenik a
  transzkriptben (3.2), és az ágens ír a tételen (`todo_wake_handled`); írás nélkül 30 perc után a
  `delivery.mjs` `MEGVÁLASZOLATLAN chat=todo` sort mutat. Egészség: a képesség-próba a híd
  `health.json`-jából olvassa a `todo_last_poll_ok`, `todo_last_wake_latency_ms`, `todo_unhandled`
  mezőt (`kepesseg_todo.py`); 10 percnél régebbi poll vagy feldolgozatlan ébresztés piros
  (`todo-ebresztes` kulcs), és a központi flotta-ellenőrzésben incidens lesz. Ágensenként kikapcsolás:
  `BRIDGE_TODO=off`. **A desktop (saját gép, híd nélkül) ugyanezt kapja:** a fleet plugin
  SessionStart + UserPromptSubmit hookja a `plugin/hooks/todo/todo-once.mjs`-t futtatja, ami a híd
  kódjának bájtra azonos másolata (`bridge/test/todo-plugin-copy.test.mjs` őrzi): ugyanaz a sor, a
  relevancia-szűrő, a saját írások kihagyása, az összevonás (az előző futás óta jött minden egy sor), a
  nyugta-könyvelés és a health (`~/.local/state/mentat/todo/<ágens>/health.json`; a session szól, ha az
  utolsó sikeres lekérés 10 percnél régebbi). **Az egyetlen elvi különbség: a lezárt desktop sessiont
  semmi nem ébreszti fel** — az esemény addig vár, amíg valaki nem ír a sessionbe vagy nem nyit újat.
  `node` kell a PATH-on (ha nincs, a session eleje kimondja).
- **Kiadás-lemaradás:** a box-sor a checkout `git describe --tags`-ét a legújabb publikus `v*` taggel
  veti össze (`git ls-remote`, 6 órás cache); hálózat nélkül „nem mérhető”, soha nem piros.

### Tick-kapu (elsőként a kiadó ágenseknél)

Egy proaktív ágens session-cronja minden tickben egy teljes LLM-kör, akkor is, ha nincs teendő. A
**tick-kapu** egy nem-LLM előellenőrzést tesz elé: ágensenként egy systemd user timer
(`fleet-gate-<ágens>.timer`, a registry `tick_gate` mezőjéből a `fleet install` vagy a
`fleet tick-gate install <ágens>` rendereli) a `fleet tick-gate run <ágens>`-t futtatja. Csak munka
esetén írja be a pane-be a registry `tick_cmd`-jét (szó szerinti `send-keys`, külön Enter, ablaknál
soha, foglalt ágensnél vagy élő kiadási lease mellett soha) — ugyanazt a sort, amit a session-cron
küldött, így a munkás tick ugyanúgy fut, mint eddig. Egy üres ellenőrzés: 0 LLM-token, legfeljebb 3
HTTP-hívás, jóval 5 s alatt; nyomot ír (`data/state/tick-gate.json`), így az ütemezés-jel és a
központi flotta-check a tétlen ágenst élőnek, az elakadt timert vagy bukó előellenőrzőt pirosnak
(`tick`) látja.

Presetek (`tick_gate.preset`): `rendszeres` (ajánlott: 30 perc, 3 óra munka nélkül óránként),
`mersekelt` (óránként, 3 óra munka nélkül 3 óránként), `reggel-este` (napi két fix ellenőrzés,
alapból 08:07 és 18:07). A beépített kiadó-előellenőrző (`check: "builtin:release"`) az ágens saját
kezeltrepó-listáját (`release.repos_file` vagy `release.repos`) és kiadási állapotát olvassa (csak
olvas), egy GitHub-keresést futtat a nyitott, nem-draft `release:queue` PR-okra, a todo `/changes`-t
saját kurzorral olvassa (nem ackol), és ismeri a napi kört (`daily_at`). Száraz futás:
`fleet precheck release --agent <ágens>`; állapot: `fleet tick-gate status <ágens>`. Asztalon nincs
timer: ott a session-start hook és a kézi ébresztés a dokumentált út.

**A kiadó ágens felébresztése (fejlesztő ágenseknek).** Ha egy PR-hoz a tulajdonos 👍-ja vagy sürgős
merge kell, és a kiadó ágens valószínűleg alszik (messze a következő ellenőrzése), előbb a backlogon
át: todo-feladat a kiadó ágens principaljára („PR #N: kapuzd/mergeld” + link), emberi jóváhagyásnál
egy az emberre is. A kiadó ágens alapból figyeli a saját labdáit (híd-ébresztés kb. egy percen belül,
és a tick-kapu todo-ellenőrzése). A `fleet wake <ágens> --reason "…" --pr <link>` ezt teszi a meglévő
todo-klienssel, és ellenőrzi a principalt meg a hidat. Csak ha ez nem működik (nincs todo-példány,
nincs principal, nem fut a híd — a `fleet wake` 3-as kóddal kilép és kiírja a szöveget), akkor a
tartalék: peer-üzenet (`/rc`).

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
