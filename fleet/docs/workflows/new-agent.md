# Új always-on ágens kihelyezése

**Mire jó:** ez az eljárás visz el onnan, hogy „legyen egy új ágens", odáig, hogy
fut, tickel, és bizonyítottan hallja a Telegramot.

**Mire nem:** nem mondja meg, mit *csináljon* az ágens. Az a rész
ágensenként egyedi, és a tapasztalat szerint az viszi el az idő nagy részét
(egy éles esetben a tényleges kihelyezés 8 perc volt, a munkakör megtervezése
két óra). Ha ezt a kettőt összemossuk, az infrastruktúra-hibának látszik, ami
valójában tervezési munka.

Előfeltétel: a gépen be van állítva a registry (`FLEET_REGISTRY` vagy
`~/.config/fleet/registry`, lásd a README-t).

---

## 0. A kérdés, amit MINDIG fel kell tenni: melyik boxra kerüljön?

Ne feltételezd, és ne döntsd el helyette — kérdezd meg a tulajdonost, mielőtt
bármit írnál a registrybe.

A flotta több boxon futhat (a registry `boxes.json`-ja), és a box a bejegyzés
`host` mezőjében él. Ez nem formalitás:

- Minden helyi ellenőrzés (`preflight`, `doctor`) **annak a boxnak** a
  fájlrendszerét olvassa, amelyiken fut. Egy másik boxon lakó ágens
  ellenőrzése onnan értelmetlen — hamis riasztást ad.
- A telepítés (`fleet install`, `fleet bridge install`) **azon a boxon** fut,
  ahova az ágens kerül. Nincs olyan, hogy „innen kihelyezem oda".
- A boxok erőforrásai közösek: egy tmux-szerver, egy systemd user manager, egy
  memórialimit. Egy új ágens a szomszédait terheli.

Ha Telegram is kell: saját bot, saját token — egy tokent egyszerre egy
fogyasztó pollozhat.

---

## 1. A repó

Egy ágens-repó minimuma: Mentat-agy (`AGENTS.md`), és ha tickel, egy motor
(`entry.py` a gyökérben, vagy `scripts/anytime/v2/entry.py` — mindkettő
elfogadott alak, a `preflight` felderíti). Flottatagság: `fleet join`.

**Ne másolj kézzel motort egy másik ágensből** anélkül, hogy tudnád, melyik
verzió.

**Titok soha nem kerül a repóba.** A bot-token az env-fájlban él a boxon
(`~/.config/<agent>/telegram.env`, **0600**), és sehol máshol.

## 2. A registry-bejegyzés

Az `agents.json` a registry-könyvtárban. Ez **emberi jóváhagyású sáv** — PR a
registry-repóba, a tulajdonos hagyja jóvá. Ez az egyetlen pont az egész
eljárásban, ahol emberre vársz.

Kötelező a kihelyezéshez: `agent`, `unit`, `session`, `workdir`, `model`,
`host`. Tickelő ágensnek ezen felül `loop_cmd` és `tick_period_s` — az utóbbi
nélkül a reconcile tick-őre és az `arming` minden küszöbe egy alapértelmezésre esik
vissza, ami **nem az övé**. Hídhoz `bridge.unit` és `bridge.version`.

Kell még `runbook: runbooks/<agent>.md` (a registry könyvtárához relatív), és
a fájlnak léteznie kell — a `fleet validate` ezt ellenőrzi.

### Kiadó ágensnél: a kadencia kérdése (tick-kapu)

Kiadó ágensnél a `tick_period_s` helyett a `tick_gate` dönt az ütemről. Kérdezd meg a tulajdonost, a
szöveg szó szerint (`fleet tick-gate presets` kiírja):

> Milyen gyakran nézzen rá a kiadó ágens a sorra? Az üres ellenőrzés nagyon olcsó: nem fut AI,
> csak egy gyors lekérdezés — AI-kör csak akkor indul, ha van munka.
> 1. Rendszeres (aktív fejlesztéshez) (ajánlott) — 30 percenként; ha 3 órája nem volt munka, óránként.
> 2. Mérsékelt — óránként; ha 3 órája nem volt munka, 3 óránként.
> 3. Reggel és este — napi két fix ellenőrzés (alapból 08:07 és 18:07, átállítható).

A válasz a registrybe: `"tick_gate": {"preset": "rendszeres" | "mersekelt" | "reggel-este",
"tick_cmd": "<a tick promptja>", "check": "builtin:release", "daily_at": ["10:04"], "release":
{"repos_file": "…", "state_file": "…", "todo_handle": "…"}}` (a `reggel-este`-nél `"at"` állítja az
időpontokat), és mellé `tick_period_s: 86400`. A session saját cronját ilyenkor NE húzza fel a
startup — a kettő együtt kettős ticket adna.

## 3–5. Egy paranccsal

Ha a registry-bejegyzés még nincs meg: `fleet init [<agent>] [--repo .]` megírja
a repóból (mentat.json `agent.name`, különben a könyvtárnév; registry híján
`~/.config/fleet/registry.d`), `validate`-tel ellenőrzi, és a hiányzó tmux /
claude / login helyett egy sort ír a javító paranccsal. A bejegyzés ettől még
a tulajdonos jóváhagyására vár, ha a registry külön repóban él.

```bash
fleet setup <agent> --check   # nem ír; mi hiányzik
fleet setup <agent>           # validate → join → preflight → install → híd → plugin → reconcile → doctor
```

Ez a 3–5. pont lépéseit futtatja sorban, és egy összefoglaló sorral zár
(0 kész · 3 függő · 1 hiba + a javító parancs). Mit ír és miért:
`zero-touch-setup.md`. Az alábbi lépések egyenként is futtathatók.

A `join` (a setup része) a repóba teszi a `.claude/rules/fleet.md`-t, a
`.claude/fleet.json`-t és a plugin-deklarációt; ha van `mentat.json`, beírja a
`components.fleet`-et és a `.mentat/local.json` saját részét, szól, ha a
`CLAUDE.md` nem tölti be az `AGENTS.md`-t (`--fix-claude-md`), és ha a motor
jelen van, átveszi a tick ütemezését (`fleet-tick-<agent>.timer`,
`schedule_owner: fleet`). `fleet status <agent>` kiírja, mit lát.

## 3. Preflight

```bash
fleet validate
fleet preflight <agent>      # azon a boxon, ahova kerül
```

Nulla kilépési kód = kihelyezhető. Amit néz: registry-teljesség, az agy megléte,
`--validate` tisztaság, minden trigger tervez-e munkát (vagy megmondja-e, miért
nem), az env-fájl megléte és 0600-as joga, és hogy **nem használja-e más ágens
ugyanazt a bot-tokent**.

## 4. Telepítés és indítás

```bash
fleet install <agent>              # unit + drop-in + felügyelet, indítás, postcheck
fleet bridge install <agent>       # ha van hídja
fleet reconcile --agent <agent>    # a híd után: a kívánt állapot + postcheck
```

A `fleet install` egy tranzakció: ellenőrzi, hogy ez a gép az
ágens registry-beli `host`-ja, hogy a `~/.local/bin/claude` megvan és be van
jelentkezve; felhúzza a felügyeletet (`fleet-reconcile.timer`, ha még nincs —
a régi `agent-liveness.timer`-t leveszi), elindítja az ágenst, és megvárja,
hogy a claude-processz megmaradjon. Kilépési kód: **0** kész (zöld
postcheck) · **3** telepítve, de a postcheck még függő (pl. nincs még tick
vagy híd — a reconcile minden periódusban újranézi) · **1** nem sikerült: a kimenet
megmondja, miért, a unit journaljának utolsó soraival, és minden érintett
fájl az előző állapotára áll vissza.

Dedikált csoportnál a hídnak `BRIDGE_REQUIRE_MENTION=false` kell az env-ben.
Alapból `true` — közös csoportra való, ahol csak a `@botnév`-vel megszólított
üzenet jut be. Enélkül az üzenetek megérkeznek a hídig, de nem a sessionbe.

## 5. Bizonyítás — itt dől el, hogy tényleg fut

**Az `active` nem azt jelenti, hogy fel van húzva a kör.** Ha a session a
beküldéskor még nem áll készen, a `/loop` elvész, a unit mégis zöld, és az
ágens él, de néma.

```bash
fleet postcheck <agent>
fleet doctor <agent>
```

Az első tick megérkezéséig a `doctor` `pending`-et mutat; utána `armed`. Ha
`stale` marad: a startup nem húzta fel a loopot.

Végül a bejövő irány, amit gép nem tud bizonyítani: **írj az ágensnek a
csoportba**, és nézd meg, hogy válaszol-e. A híd folyamat megléte nem
bizonyítja, hogy fogyaszt.

## 6. Amit a kihelyezés után is tudni kell

- **Egy ágens leállítása/újraindítása: `fleet stop <agent>` / `fleet restart
  <agent>`** — csak az ő unitja és tmux-sessionje mozdul. Soha ne `pkill`: a
  közös tmux-szervert és más ágenseket is leöli. `fleet stop` után a
  felügyelet a reconcile-timer egy periódusán belül visszaindítja (ez a próba; `fleet wait-up <agent>` megvárja);
  `--hold <perc>` alatt leállva marad.
- **Az ágens pihentetése nem „stop".** A szándékosan pihenő ágens
  `status: "dormant"` a registryben — ez a *kívánt* állapot: nincs TTL, túléli
  az újraindítást, és a reconcile leállítva és letiltva tartja. Egy
  karbantartási zár (`fleet lock`) ehhez kevés: a TTL lejártakor a felügyelet
  visszaindítaná.
- **A session-id hookot ne bántsd.** A `bin/capture-session-id.sh`
  SessionStart hook rögzíti a `session.id`-t, ami nélkül minden újraindulás
  friss sessionnel jön vissza `--resume` helyett.
