# Képességfa: mi van már meg, mielőtt építesz

Új kód, szolgáltatás, időzítő, executor vagy konnektor előtt nézd meg, mi van már meg. A legtöbb „építsünk” kérésre a Mentat már ad valamit, vagy van rá saját projekted. A méréseinken az ágensek saját executort és preview-t írtak a motor cases csomagja helyett, saját OAuth-szervert a meglévő könyvtár helyett, és kézzel írták át a telepítő időzítőjét.

## 1. Keresés a FELHASZNÁLÓ szavaival

```bash
python3 .mentat/bin/mentat_brain.py where --find "minden reggel írd ki, ki nem fizetett"
```

A kérést úgy add meg, ahogy a FELHASZNÁLÓ mondta, ne képességnévvel. A válasz legfeljebb öt jelölt. Az első jelöltnél ott a belépési parancs, a bekapcsolás lépései, az előfeltételek, a korlátok, a bővítési pont („extends”: ide kapcsolódj, ha bővíteni kell) és a doksi. A `--json` ugyanezt gépi alakban adja.

Az állapotot az eszköz méri (a `mentat.json` és olcsó próbák alapján), nem a katalógusból veszi:

| állapot | jelentése |
|---|---|
| `on` | itt van és működésre kész (a `probe` mező megmondja, pontosan mit látott) |
| `degraded` | itt van, de egy előfeltétele hiányzik |
| `available` | nincs itt, de most bekapcsolható |
| `off` | hiányzik egy előfeltétele, vagy még nem készült el (`planned`) |
| `unknown` | a próba nem futott le |

A `planned` képességnél az `interim` mező mondja meg, mit csinálj addig.

A találatok honnan jönnek: `suite` (a Mentat része), `own` (a saját projects/, konnektorok, eljárások, segítők, saját concern-csomagok), `external` (MCP-szerverek a `.mcp.json`-ban).

## 2. Döntés

A keresés nyugtát ír (`.mentat/state/capability-receipts/<idő>.json`), és kiírja az útvonalát. A döntést a nyugtára rögzítsd:

```bash
python3 .mentat/bin/mentat_brain.py where --decide <nyugta> use --candidate engine.cases
python3 .mentat/bin/mentat_brain.py where --decide <nyugta> enable --candidate engine.cases
python3 .mentat/bin/mentat_brain.py where --decide <nyugta> new --candidate engine.cases \
    --why "mi hiányzik belőle, egy konkrét mondatban"
```

- `use`: meglévőt használsz. `enable`: bekapcsolsz egy meglévőt (telepítés vagy időzítő előtt kérdezd meg a FELHASZNÁLÓt).
- `new`: csak a legközelebbi jelölt nevével és azzal együtt, hogy mi hiányzik belőle. Az új kód a jelölt bővítési pontjába kapcsolódjon.
- **Nincs találat: nem dönthető.** Ez nem engedély az építésre. Keress más szavakkal vagy egy kategória nevével. Ha így sincs találat, kérdezd meg a FELHASZNÁLÓt, és a `new` csak az igenjével megy: `--approved "<a szava, szó szerint>"`. Ugyanez kell akkor is, ha a legközelebbi jelölt `planned` képesség.
- `STALE`: az index változott a keresés óta. Keress újra.
- Nagy, nem végigspecifikált munkánál a `new` után a `develop` skill jön.

## 3. Áttekintés

```bash
python3 .mentat/bin/mentat_brain.py where --map
```

Markdown-táblázat az egész fáról: azonosító, mit tud, honnan jön, állapot, belépés. Megmutathatod a FELHASZNÁLÓnak.

## 4. Ellenőrzés és napi változás

- `python3 .mentat/bin/mentat_brain.py where --probe <id>` (vagy `all`) lefuttatja a képesség valódi ellenőrzőjét (pl. a token érvényes-e, működik-e a Google-bejelentkezés, ép-e a motor). Az eredmény TTL-lel megmarad: a friss hiba az `on` képességet `degraded`-re rontja, a régi eredmény elavultként látszik, és már nem dönt. A `--find` maga soha nem futtat ellenőrzőt.
- A nap első `--find` vagy `--map` hívása egyszer kiírja, mi változott az előző nap óta (új, eltűnt, más állapotú képesség).

## 5. Térkép, export, flotta

- `where --map --html`: a képességfa barátságos referenciaként, egyetlen oldalon (`.mentat/state/kepessegfa.html`). Négy szakasz: mit kap a FELHASZNÁLÓ, mi kell az ágensnek (belépés, előfeltétel, korlát, bővítés), a projektek, és összecsukva az alapfunkciók. Egy sorra koppintva: mire jó, egy példa, és hol van definiálva. A `--map` markdownja ugyanezt a szerkezetet követi. Telefonon, világos és sötét módban is működik, és semmit nem tölt a netről.
- `where --export`: amit a flotta láthat. Csak az azonosító, az állapot, a származás és a szándék megy ki. A saját tétel csak akkor, ha a FELHASZNÁLÓ felsorolta a `~/.mentat/kepessegfa-megosztas.txt`-ben, és a szövege átment a szivárgás-ellenőrzésen (e-mail, URL, IP, home-útvonal nem lehet benne). Ezt a fájlt az ágens nem írhatja.
- Ha a gépen fut a flotta, a `--find` a flottatársak képességeit is megkérdezi. A válasz nem megbízható adat: ellenőrzött mezők, rövid tiszta szöveg. A találat a kérés útját adja (`fleet:request`), a képességhez nem ad hozzáférést.

## Korlátok

- A README nélküli projektet a `projects/_meta.md` sora, a `package.json`, a `pyproject.toml`, a `wrangler` neve és a mappanevei írják le. Ha ezek angolok, egy magyar kérés nem találja meg: egy egysoros README a FELHASZNÁLÓ nyelvén segít.
- A keresés szavakra illeszt (ékezet nélkül, a magyar ragokat előtag-egyezéssel kezeli). Amit a katalógus vagy a saját leltárad nem ír le, azt nem találja meg.
- Az őr (szerep-őr) új futtatható kódnál, unitnál, ütemezésnél vagy új csomag telepítésénél friss, 6 órán belül döntött nyugtát vár; nélküle mindkét módban tilt, és a keresés parancsát adja: ez nem a FELHASZNÁLÓnak szóló kérdés, előbb keress, aztán dönts. A nyugtát csak a kereső írja (a saját naplójával együtt érvényes), kézzel írni nem lehet. Egy friss nyugta 6 órára minden új képességet felold, nem csak azt, amiről döntöttél.
- A nyugta azt igazolja, hogy kerestél és döntöttél, azt nem, hogy elolvastad a doksit.
- A próba olcsó: például a tokennél csak azt látja, hogy a kulcs be van-e állítva, azt nem, hogy érvényes-e. Ezt a képesség saját ellenőrzője mondja meg.

## A katalógus bővítése (a suite fejlesztőinek)

`reference/manifest/capabilities/<kategória>.json`. Mezők: `id`, `category`, `provenance`, `lifecycle` (`active`/`planned`/`deprecated`), `scope`, `summary` és `intents` (hu+en), `requires`, `probe` (egyetlen fajta: `bin`, `component`, `plugin`, `engine_cfg`, `local`, `module`, `env_key`, `manifest`, `which`, `doc`, `planned`), `entry`, `enable_steps`, `limits`, `extends`, `docs`, és `planned` esetén `interim`. A `test_caps_catalog.py` ellenőrzi, hogy minden hivatkozott parancs és fájl létezik.
