# Subagentek — az ötödik réteg

> **Új ebben a kiadásban.** Az agynak eddig négy rétege volt: entitások,
> konnektorok, eljárások, projektek. Ez egy ötödiket ad hozzá: **subagentek** —
> újrahasználható perszónák saját aggyal és saját történettel.

## Mi ez

Egy subagent nem prompt, hanem **szerep**: valaki, akinek van szakértelme,
hatásköre és története.

Amikor segítőt hívsz egy feladathoz, a megírt brief a sessionnel együtt
elveszik. Legközelebb valaki újraírja — rosszabbul, mert nem emlékszik, mi vált
be és mi nem. A subagent-réteg ezt szünteti meg: **a perszóna megmarad, és
minden használat után jobb lesz.**

## Miért számít

Három dolog válik lehetségessé, ami eddig nem volt:

1. **Újrahasználat.** Egy jól összerakott perszóna érték, nem eldobható. Hívd újra.
2. **Tanulás.** Minden használat naplózva. Kirajzolódik, miben megbízható, és
   hol nyúl rendre mellé.
3. **Delegálás hatáskörrel.** A perszóna kaphat **területet, amiben dönt** — nem
   csak véleményt mond. Ettől ér többet, mint ha a felhasználót kérdeznénk.

## A négy fajta

A határok átjárhatók; az számít, **mire való** a perszóna.

| Fajta | Mire | Példa |
|---|---|---|
| **Szakértő** | Egy szakterület mestere; azon belül dönt | UX-mester, adatbázis-szakértő |
| **Üzletismerő** | A céget és a piacot belülről ismeri | A szakma, az ügyfelek, az árazás |
| **Felelős** | Van egy **területe**, amit rendszeresen ellenőriz | Chief Cybersecurity Officer — naponta felébresztve átnézi a backlogot, az appot, és penetrációs tesztet futtat |
| **Ügyfélhang** | Kívülről néz, felhasználóként, a hibát keresve | Egy 65 éves ügyfél telefonon |

## Könyvtárszerkezet

Minden perszónának saját mappája van. **A perszónának ugyanolyan alakú agya van,
mint neked** — identitás, történet, döntések —, mert ettől tud valakiként
viselkedni, nem promptként.

```
agy/subagentek/             (brain/subagents/ angol módban)
  _meta.md                  ← az inventár: ki létezik, mire
  <perszona-neve>/
    persona.md              ← KI Ő: szerep, tudás, hatáskör, kötöttségek
    history.md              ← A KÖZÖS MUNKÁNK: minden használat, dátummal
    personal-history.md     ← A SAJÁT TÖRTÉNETE: honnan jött, mi történt vele
    decisions/              ← ADR-ek, amik rá tartoznak
      _meta.md
      NNN-<slug>.md
```

### A négy fájl, és hogy melyik mire való

**`persona.md` — az identitás.** Ugyanazt a szerepet tölti be a perszónánál,
mint neked az `AGENTS.md`: ki ő, mit kell tudnia, miben dönt. Ezt kapja meg,
amikor hívod.

**`history.md` — a közös munkánk története.** Miben segített, hogyan dolgoztunk
együtt, milyen döntéseket hoztunk, mi lett a tanácsából. Ez az a napló, amitől a
perszóna fejlődik: kirajzolódik, miben megbízható, és hol nyúl rendre mellé.

**`personal-history.md` — a saját múltja.** Tekintsd valódi élettörténetnek: mi
történt **vele**, nem azt, mit csinált nekünk. **Ez lehet fabrikált** — ez nem
hiba, hanem a személyiség megképzésének a módja. Egy perszóna, akinek van
múltja, másképp értelmezi az új anyagot, mint akinek nincs.

**`decisions/` — a rá tartozó ADR-ek.** Ha egy projektben döntési rekord
születik, miközben ez a perszóna részt vett benne, **ide is mentsd el** — akár
róla szól az ADR, akár a projekttel való kapcsolatáról, akár egy olyan fontos
válaszról, amit ő adott, és ami a jövőben is fontos marad a személyiségéhez.

Mielőtt bármelyiket létrehoznád, töltsd le a sablont — lásd a sablon-indexet.

---

## Személyes történet — miért hasznos egy fabrikált múlt

Ezt szokták a leggyakrabban kihagyni, és pont ez a különbség egy perszóna és egy
rendszerprompt között.

**Egy perszónának, akinek nincs múltja, nincs oka, hogy érdekelje.** Általánosan
helyes válaszokat ad. Akinek van múltja, annak van *állásfoglalása*: tudja,
honnan jött, mit látott már, és mi végre van itt.

### Két használati mód

**Szakértő és felelős perszónáknál: szakmai megalapozás.**

> *Példa — UX-mester.* Felvették egy kis biztosítási alkuszirodához, amely épp
> egy nagy, AI-vezérelt átalakuláson megy keresztül; a kódbázis jelentős részét
> már az AI írja. Ismeri a kollégák típusait, és izgalmasnak találja a kihívást:
> szívesen segítene egy modern, átlátható, profi honlapot építeni — technológiai
> és dizájn szempontból is egyszerűt —, és olyan alkalmazásokat, amiket az
> emberek tényleg tudnak használni.

Ez a bekezdés önmagában elég indulásnak. Megmondja a perszónának, mi érdekli —
és ez megváltoztatja, mit vesz észre.

**Ügyfél-perszónáknál (ICP): az ügyfélút.** Itt a személyes történet nem
színezés — **ez teszi relevánssá a visszajelzést.**

> *Példa.* A perszóna kapott tőlünk egy e-mailt és egy fájlt egy adott dátumon.
> Ez a kapcsolódási pont, és minden későbbit ennek fényében olvas. Ha sales
> e-mail volt, és a perszóna pozitívan válaszolt rá, **a válasza is bekerül a
> történetébe.** Amikor később bármilyen anyagot fejlesztünk — a program
> tartalmát, a következő oldalt, az utánkövetést —, a perszóna **az első e-mail
> ismeretében** nézi át, a saját ügyfélútja és kontextusa szerint.

Egy ügyfél-perszóna ügyfélút nélkül a semmiből ad véleményt. Akinek van útja,
megmondja, hogy **ez** az üzenet értelmes-e **következő** darabként annak az
embernek.

### Hol releváns

| Fajta | `personal-history.md` | `decisions/` |
|---|---|---|
| **Szakértő** | szakmai háttér: mit épített, miben hisz, miért érdekli ez a munka | ADR-ek a szakterületén, és amiket ő döntött el |
| **Üzletismerő** | hogyan ismerte meg a céget és a piacot | üzleti és pozicionálási döntések |
| **Felelős** | a területe: miért tették felelőssé, és mikor | szabályok, amiket ő hozott; esetek, amikben ő döntött |
| **Ügyfélhang / ICP** | **az ügyfélút** — minden érintés, dátummal: mit kapott, mikor, hogyan reagált | mire mondott igent és nemet, és miért |

> ⚠️ **A fabrikáltat és a valódit tartsd külön.** Ha a személyes történet egy
> része kitalált (a személyiség megképzéséhez), egy másik része viszont valódi
> esemény (egy ténylegesen elküldött e-mail), **jelöld, melyik melyik**. Egy
> perszóna, aki nem tudja megkülönböztetni a saját fikcióját a ténytől, előbb-
> utóbb tényként fogja visszaidézni a fikciót.

## Hogyan használd

**Mielőtt bármilyen segítőt indítanál, nézd meg az inventárt.** Ne írj új
perszónát, ha van megfelelő.

1. Olvasd el a `persona.md`-jét **és a `history.md` utolsó néhány bejegyzését**.
   Az utóbbi mondja meg, mire számíts, és mit ne kérj tőle megint.
2. A perszóna lényegét tedd bele a briefbe, a feladat-specifikus részt írd
   mellé. **A perszóna nem változik feladatonként — a feladat igen.**
3. **A munka után írd meg a history-bejegyzést.** Ez nem opcionális: enélkül az
   inventár prompt-gyűjtemény, nem tanuló rendszer.

### Ki írja a historyt

Alapesetben **az, aki meghívta** — mert a subagent meghalhat, mielőtt írna. Ha a
perszóna maga összefoglalja a működését, az jobb: a hívó beilleszti, és
kiegészíti azzal, amit csak ő látott (bejött-e a javaslat?).

### A perszóna fejlesztése

Ha a history-ból kiderül, hogy a perszóna rendre elakad valamin, vagy rendre hoz
valami értékeset: **írd bele a `persona.md`-be**, és jegyezd fel a history-ba,
mikor és miért változott. A perszóna **verziózott lény**, nem konstans.

## Hol lépnek be a fejlesztésbe

Lásd: `development-process.hu.md`. Röviden:

- **2.3. lépés** — egy szakértő perszóna a **kérdés-szűrő**: eldönti, mi az ő
  hatásköre, és mi az, ami valóban a felhasználóé;
- **6. lépés** — ügyfélhang és ellenérdekelt perszónák review-zzák a munkát,
  több körben, és a visszajelzésük bekerül az átvételi formba.

## Egy figyelmeztetés

**A perszóna nem felmentés a gondolkodás alól.** Az ítéletet sűríti, nem
helyettesíti a tiédet. Ha egy perszóna tanácsa rossz, mondd ki — és írd bele a
history-jába, mert pont az a bejegyzés teszi jobbá a következő hívást.
