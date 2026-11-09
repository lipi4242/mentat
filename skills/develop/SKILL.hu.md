---
name: develop
description: Nagy, nem teljesen specifikált munka végigvitele — mód-választás, specifikáció, perszónák, átvételi form, elkülönített worktree, reviewer-körök.
---

# Skill — `develop`

**Akkor hívd**, ha a felhasználó olyat kér, ami **nagy szkópú** ÉS **nincs
végigspecifikálva**.

**Ne hívd** elgépelésre, átnevezésre, körülhatárolt hibajavításra vagy kérdésre.
Azt csináld meg.

> **A mérce:** ha a kész munka több, egymással nem helyettesíthető helyes alakot
> ölthetne, és nem tudod, melyiket akarja — akkor ezt a skillt futtasd.

---

## 0. lépés — Olvasd el a folyamatot

Töltsd le a `reference/development-process.hu.md`-t. Ez a skill a futtatható
sorrend; az a dokumentum az indoklás mögötte. Ha valaha ellentmondanának, a
dokumentum az erősebb.

---

## 1. lépés — Kérdezd meg a fejlesztési módot. Ne kezdj bele.

**Egy strukturált kör.** Kínáld fel az itt elérhető kereteket, plusz a
feladathoz illő alternatívákat: közvetlen implementáció, csak terv, csak
felmérés.

**Állj meg, és várd meg a választ.** Minden alábbi ezen múlik.

---

## 2. lépés — Ha terv-vezérelt folyamat a választás, kérdezz még kettőt

**Ugyanabban a körben, nem csepegtetve:**

1. **Hány specifikációs kör?** Több / egy / azonnali indulás. Ha „azonnali", a
   hiányzó döntéseket te hozod — de **mindegyiket kiírod** az indoklásával.
2. **Ki válaszol a brainstorming kérdésekre?** Autonóm / a felhasználó / külső
   szakértő modell.

### 2.3 — A kérdés-szűrő (ha van szakértő perszóna a csapatban)

Futtasd a `subagent` skillt, hogy behozd a szakértőt. Aztán:

1. A fejlesztő leírja **mindent**, amit tisztázna. Nem cenzúrázza magát — a
   szűrés nem az ő dolga.
2. **A szakértő triázsol minden kérdést**: *„az én hatásköröm"* → dönt, és
   rögzíti a döntést indoklással; *„valóban a felhasználóé"* → megy a szűk listára.
3. A kettő együtt állítja össze az **egy** kérdéskört a felhasználónak.

> A próbakérdés, ha haboznál: *„ha ezt a felhasználó elé viszem, tudna-e jobbat
> mondani nálam?"* Ha nem — ne vidd. Minden fölösleges kérdés az ő figyelméből
> megy el, és kiszorítja azokat, amikre csak ő tud válaszolni.

---

## 3. lépés — Írj teljes körű acceptance criteriát

Nem részletesebbet a megbeszéltnél — de fedje le a **teljes kört**. Felületnél
legalább: minden képernyőméret (**mobil is**), minden megjelenítési mód,
billentyűzet és képernyőolvasó, minden érintett képernyő, hibás és üres állapot.

Ha szándékosan hagysz ki egy dimenziót, **írd le, és hogy miért**.

---

## 4. lépés — Csatold az átvételi formot

Töltsd le a `reference/templates/acceptance-form.hu.md`-t, másold a feladat
mellé, töltsd ki a fejlécet és a feltételeket, és add oda azzal, hogy **a
kitöltése a munka része**.

Feltételenként kérd: **teszt neve · mit tesztel · mit bizonyított.** Plusz a
negatív kontrollt — rontsd el, amit a teszt véd, igazold, hogy bukik, állítsd
vissza, és bizonyítsd a visszaállást.

> „A teszt zöld" nem bizonyíték. A kérdés az, mi lett volna, ha nem működik.

---

## 5. lépés — Különítsd el a munkát

A fejlesztő **saját `git worktree`-ben, saját branchen** dolgozik. Két okból,
mindkettő megtapasztalva: a párhuzamos agentek egymás alól írnak ki, és **a
munkafa hazudik** — nem követett fájlokat is tartalmaz, tehát az ott mért zöld
lehet, hogy csak a te gépedről szól.

Befejezéskor: merge-eld a branchet, töröld a worktree-t. Ne maradjon szemét.

**Ha kiadó ágens mergel** (a PR `release:queue` címkét kap), és a PR-hoz a tulajdonos 👍-ja vagy
sürgős merge kell, a kiadó ágens pedig valószínűleg alszik (messze a következő ellenőrzése), ébreszd
fel — ebben a sorrendben:

1. **Backlog (elsődleges):** todo-feladat a kiadó ágens principaljára: „PR #N: kapuzd/mergeld” + a PR
   linkje; emberi jóváhagyásnál egy feladat az emberre is. A kiadó ágens alapból figyeli a saját
   labdáit, ez ébreszti fel. Flottában: `fleet wake <kiadó ágens> --reason "PR #N: kapuzd/mergeld" --pr <link>`.
2. **Tartalék, csak ha az 1. nem működik** (nincs todo-példány, nincs principalja a kiadó ágensnek,
   nem fut a hídja — a `fleet wake` ezt 3-as kóddal jelzi, és kiírja a szöveget): peer-üzenet (`/rc`).

---

## 6. lépés — Reviewer-körök

Hozd be a perszónákat a `subagent` skillel:

- **Ügyfélhang** — a tervet *és* az elkészült verziót is átnézi, **több körben**;
  az első a nyilvánvalót találja meg, a második azt, ami az első javításakor
  romlott el.
- **Ellenérdekelt bíráló** — kritikusan értékel; nem az a dolga, hogy egyetértsen.

**Minden visszajelzés a formba kerül** — mit mondott, mi lett belőle, és ha
semmi, miért.

---

## 7. lépés — Dokumentálj helyben, és naplózd a perszónákat

Két dolgot könnyű kihagyni a végén, és mindkettő később kerül pénzbe:

1. **A dokumentáció oda kerül, ahova való** — a projekt saját doksijába, amellé,
   amit leír, a vonatkozó indexek frissítésével. Nem a chatbe, nem egy árva fájlba.
2. **Minden használt perszóna kap history-bejegyzést** (`subagent` skill, 4.
   lépés). Egy perszóna, akinek a sessionje nincs naplózva, semmit nem tanult.

Aztán futtasd meg a kitöltött formot a felhasználóval. A form pont attól ér
valamit, hogy egy ember ránéz, és azt mondja, hogy nem.

---

## Amit ez a skill nem old meg

Nem helyettesíti az ítéletedet; a kitöltött form nem garantál minőséget; és a
merge nem élesítés. Ha a projektnek van kiadási rendje, azt kövesd.
