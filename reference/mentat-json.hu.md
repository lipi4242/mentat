# mentat.json — komponens-manifest és szinergia-mátrix

Séma: 1. [English](mentat-json.md)

A négy építőelem — **agy** (a repó gyökere), **motor** (`engine/`), **flotta**
(`fleet/`) és **admin** (`admin/`), mind az egy Mentat-repóban — önállóan is működik.
Az ágens repójában két fájl köti össze őket:

- **`mentat.json`** (commitolt): SZÁNDÉK — mely elemek tartoznak az ágenshez,
  és a repón belüli útvonalaik. Nincs benne gép-, verzió- vagy végpont-tény.
- **`.mentat/local.json`** (gitignored): TÉNY ezen a gépen — telepített
  verziók, a flotta-azonosító, az admin végpontja. Klónozáskor nem utazik, így
  egy klón sosem állít valótlant.

## 1. Alak

Ugyanaz, mint az [angol változatban](mentat-json.md#1-shape); magyar módban az
agy gyökere jellemzően `agy`, a nyelv `hu`.

## 2. Szabályok

1. **Kulcs-gazdák.** `schema`, `agent` és `roles`: az agy telepítője.
   `components.<x>` és `installed.<x>`: az x elem telepítője. `cases`: a
   `cases` CLI (az agy telepítője csak *beveti* a `cases.backend: markdown`
   értéket, ha hiányzik). A local-ban a `fleet` a flottáé, az `admin` az
   admin-bekötésé. Más kulcsához senki nem nyúl. **Egyetlen kivétel:** a
   `components.engine.schedule_owner` kulcsot a flotta join-ja is írhatja
   (`engine` → `fleet`), az 5. szabály szerint; a motor többi kulcsához nem
   nyúl. A fájlt az első író hozza létre, `"schema": 1`-gyel.
2. **Írás zárral.** Minden író kizárólagos `flock`-ot tart a `.mentat/lock`
   fájlon a teljes beolvasás → saját kulcs összefésülése (a saját szekció
   ismeretlen mezői megmaradnak) → tmp-fájl + átnevezés köré. A kulcssorrend
   nem része a szerződésnek.
3. **Bizalmi határ.** A commitolt fájl nem visz végpontot és nem tölt kódot:
   útvonal csak repón belüli relatív lehet (`..` és abszolút tilos); a
   `plugins` csak a repó saját csomagjait nevezheti, pontozott névvel, sosem
   URL-lel vagy útvonallal. Az admin URL-je és a token env-neve a local
   fájlban él, a token tartalma `.env`-ben (0600, gitignored). Hostnév igen,
   IP-cím nem. Mindhármat csak az admin `npm run connect` parancsa írja
   (ezen a gépen futó adminhoz `--local`-lal), kézzel soha; egy session az
   admint máshol nem keresi.
4. **Hiányzó elem = nincs jelen, az opcionális szinergia csendben marad el** —
   de a `status` kimondja („admin: nincs bekötve"). **Kivétel: kifejezetten
   választott adattár.** Ha `cases.backend: admin`, és az admin hiányzik vagy
   elérhetetlen, az ügy-művelet hibával áll meg — nincs visszaesés
   markdownra. Backend-váltás csak `cases migrate`-tel.
5. **Ütemezés: egy gazda.** `engine.schedule_owner`: `engine` (a motor saját
   timere) vagy `fleet`. A flotta join-ja idempotensen átveszi; a motor nem
   telepít timert, amíg a gazda `fleet`.
6. **Ismeretlen `schema` (nagyobb az ismertnél) → csak diagnosztika**: nem
   indít feladatot, nem ír se a fájlokba, se az adminba. Új mező csak akkor
   nem törő, ha figyelmen kívül hagyva is helyes a működés; különben a
   `schema` nő.
7. **Ismeretlen kulcs tűrt**, olvasó sosem bukik el rajta.
8. **Szerepek.** A `roles.installed` szerepneveket sorol
   (`^[a-z][a-z0-9-]*$`), a `roles.default` ezek egyike kell legyen; ha nem,
   az olvasó `invalid_value`-t jelez (`roles.default` vagy
   `roles.installed[i]` helyen), de egy elemet sem kapcsol ki. A szerep a
   futásra szól, nem a repóra: a hatályos szerep a `MENTAT_ROLE`, ha
   telepített (különben hiba), egyébként a `roles.default`; munkamenetben a
   `/szerep` váltja. A jogosultságot a szerep-őr hook érvényesíti, nem ez a
   fájl (lásd `bekotes/BEKOTES.hu.md`).

**Jelen van** egy elem, ha a `mentat.json` `components`-ében szerepel, ezen a
gépen telepítve van (local `installed.<x>`; az adminnál `admin.url`), és a
saját szekciójában nincs hiba. Hibás bejegyzésű elem = nincs jelen.

## 3. Szinergia-mátrix

| pár | mi kapcsol be | ki valósítja meg |
|---|---|---|
| agy + motor | a motor providerei az agy `root`-jából olvasnak (teendők, ügyek, döntések); starter concern: reggeli áttekintés | motor |
| agy + flotta | a join ellenőrzi, hogy a CLAUDE.md betölti az AGENTS.md-t | flotta |
| motor + flotta | a flotta veszi át a tick ütemezését, és a `last-tick.json`-t felügyeli | flotta |
| agy + admin | csak `cases.backend: admin` mellett: az ügyek az adminban, az agy fájljai `brain_ref`-fel hivatkoznak | admin `cases` CLI |
| motor + admin | `cases.due` provider az admin API-ból | motor concern-csomag |
| flotta + admin | fleet plugin: kívánt és megfigyelt állapot | flotta + admin |

Minden elem ad egy `status` parancsot, ami kiírja, mit lát a két fájlból, és
mely szinergiák élnek. Az agyé a [`status` skill](../skills/status/SKILL.hu.md).

## 4. release.json

Minden kiadás a tagelt fában publikál egy `release.json`-t; alakja és
szabályai az [angol változat 4. pontjában](mentat-json.md#4-releasejson).
Röviden: `severity` = `patch | minor | major`, a `security` külön jelző;
verzió-átugrásnál a köztes kiadások `release.json`-jai sorban olvasandók;
a `requires_if_present` csak akkor feltétel, ha a másik elem jelen van; nincs
függőségfeloldó — ütközésnél a frissítő megáll és szól.

## 5. Hivatkozó implementáció és megfelelőség

A [`manifest/`](manifest/) a kanonikus példány: `mentat_manifest.py`,
`mentat_rules.py`, `mentat_roles.py` (szerepek), `mentat_cli.py` (`init-brain`, `status`), és a közös
fixture-ök a `manifest/conformance/` alatt, elvárt eredménnyel. Minden olvasó
(a TypeScript admin is) ezeken teszteli magát. Hibakódok: lásd az angol
változatot.
