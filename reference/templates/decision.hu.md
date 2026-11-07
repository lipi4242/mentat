# Döntés sablon (HU)

Egy döntés, amit a FELHASZNÁLÓ meghozott, olyan helyen, ahol később megtalálod —
nem eltemetve abban a teendőben vagy brain dumpban, ahol szóba került.

## Mikor hozz létre ilyet

A FELHASZNÁLÓ eldönt valamit, amihez a későbbi munkának igazodnia kell: „a
gázszámlát átutalással fizetjük, nem csoportos beszedéssel", „márciusig nincs új
ügyfél", „az oldal csak magyarul lesz". **Ugyanabban a körben** hozd létre,
amikor a döntés megszületik, akkor is, ha egy teendő, egy brain dump vagy egy
mellékmondat közben jött elő. A végrehajtó teendő ide linkel; maga a döntés nem
benne él.

Nem minden preferencia döntés. A mérce: ha jövő hónapban csendben az
ellenkezőjét csinálnád, azt a FELHASZNÁLÓ hibának tartaná, és szeretné, ha
megállítanád?

Egy **perszónáról** szóló döntés (hatáskör, felelősségi terület) a
`subagent-decision` sablonba kerül.

## Frontmatter

```yaml
---
type: decision
date: ÉÉÉÉ-HH-NN         # mikor született
status: decided          # decided | superseded
supersedes: <fájlnév>    # opcionális — a korábbi döntés, amit felvált
weight: normal           # normal | high — high = a FELHASZNÁLÓ mondta, hogy számít
tags: [...]
---
```

## Tartalom

1. **Döntés** — egy-két mondat, ahol lehet, a FELHASZNÁLÓ szavaival.
2. **Miért** — az ok, amit a FELHASZNÁLÓ mondott. Ezt idézed vissza neki, ha
   eltérne tőle.
3. **Elvetett lehetőségek** — opcionális, soronként egy.
4. **Mi nyitná újra** — opcionális: a feltétel, amire a FELHASZNÁLÓ azt mondta,
   akkor máshogy döntene.
5. **Linkek** — a teendők, specifikációk, emberek vagy brain dump, ahonnan jött
   vagy amiket érint.

## Eltérési szabály

Mielőtt olyasmit tennél, terveznél vagy írnál, ami egy `decided` döntéssel
ellentétes, állj meg és mondd ki: *„<dátum>-án úgy döntöttél, hogy <X>, mert
<miért>. Felülírjuk?"* Ha a FELHASZNÁLÓ felülírja, hozz létre új döntést, a
`supersedes:` mező a régire mutasson, a régi pedig kapjon `status: superseded`
értéket. Döntést **soha ne törölj és ne írj át csendben**.

## Fájlnév

`agy/decisions/ÉÉÉÉ-HH-NN-<slug>.md`

## Példa

```markdown
---
type: decision
date: 2026-10-14
status: decided
weight: high
tags: [háztartás, pénzügy]
---

**Döntés:** A gázszámlát havonta átutalással fizetjük, nem csoportos beszedéssel.

**Miért:** „Látni akarom az összeget, mielőtt leemelik — tavaly télen a becslés a duplája volt."

**Mi nyitná újra:** ha a szolgáltató havi mért elszámolásra vált.

**Linkek:** `agy/todos/oktoberi-gazszamla.md`, `agy/brain-dumps/2026-10-14-haztartas.md`
```
