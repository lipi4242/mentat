# Subagent-sablon (HU)

Újrahasználható perszóna: valaki, akinek van szakértelme, hatásköre és története.

## Mikor hozz létre ilyet

Segítőt indítanál, és **nincs megfelelő perszóna az inventárban**
(`agy/subagentek/_meta.md`). Ha van, azt használd — ne írj újat.

Akkor érdemes perszónát csinálni, ha a szerep visszatér: egy szakértő, akit
újra megkérdezel; egy ügyfélhang, aki a kiadásokat átnézi; egy felelős, aki egy
területet rendszeresen ellenőriz.

## Frontmatter

```yaml
---
type: subagent
name: <rovid-slug>
kind: szakerto        # szakerto | uzletismero | felelos | ugyfelhang
status: elo           # elo | kiserleti | nyugdijazott
tags: [...]
---
```

## A törzs szerkezete

1. **Egy mondatban** — ki ő, és miért érdemes őt hívni ahelyett, hogy magad
   csinálnád meg.
2. **Ki ő** — szerep, nézőpont, hozzáállás. Nem életrajz: az számít, **honnan
   néz**, és mit vesz észre, amit más nem.
3. **Mit kell megkapnia** — fájlok, amiket el kell olvasnia, mielőtt dolgozni
   kezd. Egy perszóna, aki kötöttségek nélkül kap feladatot, a saját ízlése
   szerint fog dönteni.
4. **Hatásköre** — kétoszlopos táblázat: miben **dönt**, és mit visz a
   felhasználó elé. Legyen benne a próbakérdés: *„ha ezt a felhasználó elé
   viszem, tudna-e jobbat mondani nálam?"* Ha nem — az övé.
5. **Kötöttségek** — amit a projekt eldöntött, és nem az ő ízlésének tárgya.
6. **Hogyan hívd** — modell (és miért az), eszközök, tipikus feladat, **mit KELL
   kérni tőle** (a válasz szerkezete — enélkül esszét ír), és mit ne kérj.
7. **Amit a története tanított** — a `history.md`-ből nő. Ettől lesz a perszóna
   jobb, mint amikor megírtuk.

## Fájlnév

`agy/subagentek/<nev>/persona.md`

## Megjegyzés

Írási jogot csak akkor adj, ha a perszónának terméket kell előállítania. Egy
szakértő reviewer mér és ítél — ne ő kivitelezzen is.
