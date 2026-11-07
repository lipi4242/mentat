---
name: subagent
description: Perszóna létrehozása, hívása, a közös munka és a session naplózása — egy újrahasználható subagent teljes életciklusa.
---

# Skill — `subagent`

**Akkor hívd**, ha olyasvalaki kell, aki nem te vagy: szakértő, üzletismerő,
felelős gazda, vagy egy ügyfél, aki kívülről néz.

Önállóan is fut, és a `develop` skill subskillként hívja.

---

## 0. lépés — Olvasd el a réteget

Töltsd le a `reference/subagents.hu.md`-t, ha ebben a sessionben még nem tetted.
A perszónáknak meghatározott agy-szerkezetük van — ne találd ki.

---

## 1. lépés — Előbb nézd meg, aztán építs

**Olvasd el az `agy/subagentek/_meta.md`-t.** Ha van megfelelő perszóna,
**használd** — ne írj újat. Pont az a lényeg, hogy egy perszónát újra hívunk.

Ha van: olvasd el a `persona.md`-jét **és a `history.md` utolsó néhány
bejegyzését**. Az utóbbi mondja meg, mire számíts, és mit ne kérj tőle megint.
Aztán ugorj a 3. lépésre.

---

## 2. lépés — Hozd létre a perszónát (csak ha nincs megfelelő)

Töltsd le és kövesd ezeket a sablonokat. A szerkezetet ne improvizáld:

| Fájl | Sablon |
|---|---|
| `persona.md` | `reference/templates/subagent.hu.md` |
| `history.md` | `reference/templates/subagent-history.hu.md` |
| `personal-history.md` | `reference/templates/subagent-personal-history.hu.md` |
| `decisions/` | `reference/templates/subagent-decision.hu.md` |

Két rész dönti el, hogy a perszóna ér-e valamit:

- **Hatáskör** — miben *dönt*, szemben azzal, amit a felhasználó elé visz. Egy
  perszóna hatáskör nélkül csak egy lassabb módja annak, hogy magadtól kérdezz.
- **Személyes történet** — honnan jött. Lehet fabrikált; így képződik a
  személyiség. **Ügyfél-perszónánál ez az ügyfélút**, és ez teszi relevánssá a
  visszajelzést az általános helyett. **Jelöld, mi kitalált és mi valódi.**

Aztán **vedd fel az `agy/subagentek/_meta.md`-be**. Egy perszóna, aki nincs benne
az inventárban, a következő embernek nem fog létezni.

---

## 3. lépés — Hívd meg

- A **perszóna lényegét** tedd a briefbe, a feladat-specifikus részt mellé. A
  perszóna nem változik feladatonként — a feladat igen.
- **Add meg, amit tudnia kell** (a `persona.md`-jében felsorolt fájlokat). Egy
  perszóna, aki kötöttségek nélkül kap feladatot, a saját ízlése szerint dönt.
- **Kérj meghatározott válasz-szerkezetet.** Anélkül esszét ír. Mondd meg
  számozva, milyen szakaszokat vársz vissza.
- **Írási jogot csak akkor**, ha terméket kell előállítania. Egy reviewer mér és
  ítél; ne ő kivitelezzen is.

### Kommunikáció a munka közben

A perszóna **partner, nem automata**:

- Ha jelentés nélkül elhallgat, **kérdezz rá közvetlenül**: kész, elakadt, vagy
  nem érti. Ne feltételezd, hogy befejezte.
- Ha ellentmond a felhasználó korábbi döntésének, és ez a hatáskörén belül van,
  az megengedett — de **ki kell írnia**, mi volt a korábbi döntés, mit döntött
  helyette, és mi alapján.
- Ha a hatáskörén **kívül** mond ellent, ne nyeld le: vidd a felhasználó elé
  mindkét álláspontot, és ő döntsön.
- **Ellenőrizd a fontos állításokat.** Egy perszóna „kész" jelentése jelentés,
  nem bizonyíték — ugyanaz a szabály, mint bármely más munkánál.

---

## 4. lépés — Naplózd a sessiont. Nem opcionális.

Írd a `history.md`-be: mit kértél, mit adott, **mi lett belőle** (elfogadva /
módosítva / elvetve — és miért), és a tanulságot.

**Ki írja:** aki meghívta — a subagent meghalhat, mielőtt írna. Ha a perszóna
maga összefoglalta a működését, azt illeszd be, és tedd hozzá, amit csak te
láttál: bejött-e a tanácsa?

> Enélkül az inventár prompt-gyűjtemény, nem tanuló rendszer.

**Ha döntési rekord született**, miközben ez a perszóna részt vett benne, és
mond valamit arról, *ki ő* — másold a `decisions/` mappájába. Nem minden
projekt-ADR-t; csak azokat, amik alakítják a perszónát.

---

## 5. lépés — Fejleszd, ha a history azt mondja

Ha a history-ból kiderül, hogy a perszóna rendre elakad valamin, vagy rendre hoz
valami értékeset, **írd bele a `persona.md`-be**, és jegyezd fel a history-ba,
mikor és miért változott.

A perszóna **verziózott lény**, nem konstans.
