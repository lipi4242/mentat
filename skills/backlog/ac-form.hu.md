# Az AC-űrlap (A–F)

A fejlesztő jelentése egy backlog-tételről: minden elfogadási feltételhez
(AC) egy eredmény bizonyítékkal, és amire a PM-nek a döntéshez szüksége van.
Kézzel soha nem írod: a `todo item show KULCS --form --lang hu` kiírja, már a
tétel élő AC-ivel kitöltve, a `todo item submit KULCS --form FÁJL` pedig elküldi.
(`todo` = `python3 -m anytime_todo.cli`.)

```markdown
# WEB-12: A „kinél a labda” oldal
<!-- mentat:ac-form item=01JC8Q2W5V round=1 -->

## Meta
- summary: az oldal a néző minden nyitott tételét listázza
- head_sha: 3f2c9e1
- pr: https://github.com/example/app/pull/41

## A) Elfogadási feltételek

### AC 01JC8Q3A1B
> Kész, ha az oldal minden nyitott tételt listáz, amelynél a nézőnél a labda
- verdict: met
- evidence: test_ball_page_lists_open_items (worker/test/ball.test.ts:18), zöld

## B) Tesztek
## C) Review
## D) Kapuk
## E) Verdikt
## F) Csatolmányok
```

## A részei

| Rész | Mi kerül bele | Ki mire olvassa |
|---|---|---|
| Meta | `summary` (egy sor, kötelező), `head_sha` (a commit, amelyre a bizonyíték vonatkozik), PR-onként egy `pr:` sor | a PM megtalálja a változást |
| A | AC-nként: `verdict` = `met`, `not_met` vagy `na`, és `evidence` (tesztnév, `fájl:sor`, naplósor) | a PM minden sort ellenőriz |
| B | melyik teszt melyik AC-t fedi, a parancs és az eredménye, és hogy a teszt tényleg az AC-t állítja-e | valódi-e a bizonyíték? |
| C | a review: a teherhordó állítások megtámadva, minden lelet a feloldásával | mi lehet még rossz |
| D | a sáv kapui, zölden; képernyőt érintő változásnál képernyőkép kell | semmi nem maradt ki |
| E | **nem írod be**: beküldéskor csak akkor igen, ha minden AC `met` vagy `na` | |
| F | mi van csatolva (PR, napló, képernyőkép) | |

## Szabályok

- **Az AC-sorok a tételéi, nem a tieid.** Az `### AC <azonosító>` sort és az
  alatta idézett szöveget ne írd át. Az azonosító örökre azt az AC-t jelöli; ha
  a PM átírja a szövegét, a régi űrlapot a parancs visszadobja („changed since
  the form was made”): kérj frisset.
- **Minden élő AC-hez pontosan egy eredmény.** A hiányzó, kétszer szereplő vagy
  ismeretlen AC, a változatlanul hagyott `met | not_met | na` sor és az üres
  bizonyíték elakad, mielőtt bármi elmenne.
- **A `not_met` megengedett.** Mondd ki egyenesen, indokkal; a PM dönt. Csak az
  elfogadáshoz kell, hogy minden AC teljesüljön.
- **Körönként egy űrlap.** Elutasítás után a következő jelentés a következő kör:
  kérj friss űrlapot. Egy korábbi kör űrlapját a parancs visszadobja.
- A B, C, D és F a jelentés szövegeként megy, a címsorokkal együtt; a `<!-- -->`
  közötti tippek kimaradnak. A bizonyíték lehet több soros, idézet (`>`) és kódblokk is.
- **Semmi nem vész el csendben.** A kódblokkon belüli `## ` sor tartalom; az azonos
  betűs második szakaszt, az E-be írt szöveget, az ismeretlen Meta-sort és a Meta
  fölé írt szöveget a parancs visszadobja, így még küldés előtt javíthatod.
