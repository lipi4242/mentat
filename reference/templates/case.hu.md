# Ügy sablon (HU)

Valami, amit a FELHASZNÁLÓnak el kell intéznie és időben követnie — egyszer,
vagy újra meg újra: a gázszámla minden hónap 10-éig, az adóbevallás május
20-ig, egy biztosítási kárigény, amelyben a biztosítóra várunk.

## Mikor hozz létre ilyet (javaslat — szabjátok a FELHASZNÁLÓra, és rögzítsd az `agy/cases/_meta.md`-ben)

Ügy az, aminek

1. **elintézett állapota van** — vagy, ha ismétlődik, minden egyes
   előfordulása elintézhető;
2. **van következő lépése** (akár: „várunk X-re");
3. **van dátuma**: határidő, vagy amikor újra rá kell nézni.

Nem ügy: a **projekt** vagy **exploration** (iránya van, „kész" állapota
nincs), a **sima teendő** (egy lépés, kontextus nélkül — maradjon todo), a
**döntés** (betartandó szabály, nem elintézendő dolog), az **életterület**
(pénzügyek, egészség: ügyek gyűjtőhelye). Határeset: egy teendő, ami hetek óta
görög és mástól függ → ügy.

## Frontmatter

A mezőnevek ugyanazok, mint az admin ügyek-pluginjában, így az ügy átköltözése
mezőről mezőre másolás, nem szövegből találgatás.

```yaml
---
type: case
case_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RS   # ULID, egyszer generálva, sosem változik
title: Gázszámla
status: open            # open | waiting | done | dropped
description: A havi gázszámla, átutalással   # egy-két mondat: miről szól
next_action: Átutalni, amint megjön a számla   # egy mondat; várakozásnál: „várunk X-re"
due_at: 2026-11-10      # egyszerinél a határidő; ismétlődőnél a legkorábbi nyitott előfordulás
recurrence: monthly:10  # monthly:<nap> | quarterly:<nap> | yearly:<HH-NN> | weekly:<mon..sun> | üres
anchor_at: 2026-10-10   # ismétlődőnél: a sorozat első esedékessége (kötelező)
occurrences:            # ismétlődőnél: csak a lezárt előfordulások, a legrégebbi elöl
  - { due_at: 2026-10-10, status: done, done_at: 2026-10-08, note: átutalva }
extra: {}               # saját mezőid (pl. kategória, összeg), amíg be nem válnak
tags: [...]
---
```

Egyszeri ügynél a `recurrence`, az `anchor_at` és az `occurrences` elmarad:
a `due_at` maga a határidő (lásd a második példát).

Ha a FELHASZNÁLÓnak tartósan kell egy mező, ami itt nincs (kategória,
összeg, prioritás): markdown-módban az `extra`-ba írd. Adminnal ez saját
mező lesz az adminban (az admin `agent/EXTENDING.md` receptje), és a `cases`
CLI `--set mező=érték` kapcsolóval írja.

Az ULID-et egyszer generáld, a fájl létrehozásakor (Python 3):

```bash
python3 -c "import os,time;n=(int(time.time()*1000)<<80)|int.from_bytes(os.urandom(10),'big');a='0123456789ABCDEFGHJKMNPQRSTVWXYZ';print(''.join(a[(n>>5*i)&31] for i in range(25,-1,-1)))"
```

## Törzs

1. **Kontextus** — történet, számítás, dokumentumok, érintett emberek
   (linkeld őket). Ez a rész mindig markdownban marad, az adminba költözés
   után is.
2. **Napló** — dátumozott sorok arról, mi történt.

## Esedékesség lezárása

- **Egyszeri ügy:** `status: done` (vagy `dropped`), és naplózd, miért.
- **Ismétlődő ügy:** **csak a legkorábbi nyitott előfordulást** zárd le — azt,
  ami a `due_at`-ben áll. Fűzd az `occurrences`-hez (`status: done` vagy
  `skipped`, `done_at`, `note`), aztán léptesd a `due_at`-et a sorozat
  következő dátumára: az `anchor_at` + n × `recurrence` közül az első, ami még
  nincs lezárva. Ha a nap egy hónapban nem létezik (31.), a hónap utolsó napja
  számít. A `quarterly:<nap>` (pl. negyedéves ÁFA) háromhavonta lép, az
  `anchor_at` hónapjától: `quarterly:20` 2026-01-20-tól → január, április,
  július, október 20.; `quarterly:31` novemberi horgonnyal februárban 28-a. Egy kifizetetlen október nem tűnhet el egy kifizetett november
  mögött: két lejárt hónap esetén mindkettő nyitott, és az október zárul
  előbb. Maga az ügy `open` marad.
- **Kilógó első hónap:** ha az első esedékesség nem esik az ütemre (mostantól
  10-éig, de október 10-e elmúlt, az október 20-án jár le), az is a sorozat
  része, nem külön egyszeri ügy: `anchor_at: 2026-10-10`, `due_at: 2026-10-20`
  (a `due_at` a legkorábbi nyitott előfordulás a saját hónapján belül későbbre
  tehető). Lezáráskor az `occurrences`-be a sorozat-dátum kerül (2026-10-10).
  A `cases` CLI-vel: `add --recurrence monthly:10 --due 2026-10-20`.
- Soha ne zárj le olyan dátumot, amit a FELHASZNÁLÓ nem erősített meg
  elintézettnek.

## Hol él

`agy/cases/<slug>.md`. A `mentat.json` mondja meg, hol követjük az ügyeket:
`cases.backend: markdown` (az alapérték) — a fenti frontmatter maga a
nyilvántartás. `cases.backend: admin` mellett a követett mezők csak az
adminban élnek, ez a fájl a `case_id`-t és a kontextust tartja meg; az admin
`brain_ref` mezője erre a fájlra mutat. A két mód közti váltás `cases
migrate`-tel megy, sosem kézzel.

## Példa

```markdown
---
type: case
case_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RS
title: Gázszámla
description: A havi gázszámla, minden hónap 10-éig, átutalással
status: open
next_action: Átutalni, amint megjön a számla
due_at: 2026-11-10
recurrence: monthly:10
anchor_at: 2026-10-10
occurrences:
  - { due_at: 2026-10-10, status: done, done_at: 2026-10-08, note: átutalva }
tags: [háztartás, pénzügy]
---

**Kontextus:** Átutalással fizetjük, nem csoportos beszedéssel — lásd `agy/decisions/2026-10-14-gaz-atutalassal.md`.

**Napló:**
- 2026-10-08 — október kifizetve.
```

Egyszeri ügy:

```markdown
---
type: case
case_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RT
title: Adóbevallás 2026
description: Az éves SZJA-bevallás, a NAV tervezet alapján
status: open
next_action: A tervezetet átnézni, a bérleti díjat hozzáadni
due_at: 2027-05-20
tags: [pénzügy]
---

**Kontextus:** A NAV-tervezetből hiányzik a bérbeadás; a szerződés: `agy/dokumentumok/berlet.md`.

**Napló:**
- 2027-03-18 — a tervezet megjött.
```

## Dátum- vagy állapotváltás előtt

Mielőtt egy ügy `due_at`-ját, `status`-át vagy egy előfordulását módosítod, olvasd el az ügy
`description`-jét, `next_action`-jét, az `occurrences` jegyzeteit és a törzsét. Ha bármelyik
feltételt szab (pl. „ne előbb, mint…”, „csak X után”, „várunk Y-ra”), és a kért változás
ütközik vele, idézd a feltételt, kérdezz, és csak a válasz után írj. Ütközés nélkül nem kell kérdezni.
