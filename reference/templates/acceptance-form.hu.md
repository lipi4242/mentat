
# Átvételi form — sablon (HU)

A `development-process.hu.md` 4. lépéséhez tartozik: ez a „kész" bizonyítéka.

> **Hogyan használd (a kiadó oldalról):** másold a feladat mellé
> (pl. `<munkatér>/form-<feladat>.md`), töltsd ki a fejlécet és az acceptance
> criteriákat, majd add oda az agentnek azzal, hogy **a feladat része a form
> kitöltése**. Üres formmal a munka nincs kész.
>
> **Hogyan használd (az agent oldaláról):** olvasd el ELŐSZÖR, a tervezés
> előtt. A terved ehhez mérődik: ha nem fed le egy feltételt, az most derüljön
> ki, ne a végén. Kitöltés után a form visszamegy emberi ellenőrzésre.

---

## Fejléc

| | |
|---|---|
| **Feladat** | *(egy mondat: mi a cél)* |
| **Kiadta / mikor** | |
| **Branch** | |
| **Worktree** | |
| **Fejlesztési mód** | *(Superpowers / közvetlen / egyéb)* |
| **Brainstorming kérdések címzettje** | *(autonóm / felhasználó / külső szakértő modell)* |
| **Specifikációs körök száma** | |

---

## 1. Acceptance criteriák

> Egy sor = egy feltétel. **Minden feltételhez teszt kell.** A „mit bizonyított"
> oszlop a lényeg: nem az, hogy a teszt zöld, hanem hogy **mi lett volna, ha
> nem működik**.

| # | Feltétel | Teljesült? | Teszt neve | Mit tesztel | Mit bizonyított |
|---|----------|-----------|-----------|-------------|-----------------|
| 1 | | ☐ | | | |
| 2 | | ☐ | | | |
| 3 | | ☐ | | | |

### Tud-e bukni? — negatív kontroll

> Ez a rubrika azért van, mert **egy ellenőr, ami nem tud bukni, rosszabb, mint
> a semmi**. Rontsd el szándékosan azt, amit a teszt véd, futtasd, és nézd meg,
> hogy tényleg elbukik-e. Utána állítsd vissza, és **igazold, hogy visszaállt**.

| Teszt | Hogyan rontottad el | Bukott? | Visszaállítva? |
|-------|--------------------|--------|----------------|
| | | ☐ | ☐ |

---

## 2. Lefedettség — amit a „teljes kör" jelent

> Ezek nem opcionálisak. Ha egy sor nem értelmezhető a feladatra, írd oda, hogy
> **miért nem** — az üresen hagyás nem válasz.

| Dimenzió | Rendben? | Mivel igazolod |
|---|---|---|
| Asztali nézet | ☐ | |
| **Mobil nézet** (390×844 vagy hasonló) | ☐ | |
| Köztes méret / tablet | ☐ | |
| **Világos mód** | ☐ | |
| **Sötét mód** | ☐ | |
| Billentyűzetes használat (fókusz, sorrend) | ☐ | |
| Képernyőolvasó (címkék, hibaüzenetek, aria) | ☐ | |
| Üres állapot | ☐ | |
| Hibás állapot | ☐ | |
| Minden érintett oldal / képernyő | ☐ | |

---

## 2.5 A kérdés-szűrő nyoma

> Ha volt szakértő reviewer (UX Master, domain-szakértő), aki triázsolta a
> fejlesztő kérdéseit: **mit tartott meg magának, és mit vitt a felhasználó elé.**
> Ez teszi auditálhatóvá, hogy a felhasználó miért pont azt a néhány kérdést kapta.

| A fejlesztő kérdése | Kié lett | Ha a szakértőé: mit döntött, mi alapján |
|---|---|---|
| | ☐ szakértő · ☐ felhasználó | |

## 3. Amit magamtól döntöttem el

> Minden nagy feladatban marad tisztázatlan pont. Nem az a baj, ha döntesz —
> az, ha némán teszed. **Sorold fel**, és mondd meg, mi alapján.

| Mi volt a nyitott kérdés | Mit döntöttem | Mi alapján |
|---|---|---|
| | | |

---

## 4. Amit NEM csináltam meg

> Kihagyott dimenzió, elhalasztott rész, ismert korlát. **A kimondott hiány
> kezelhető; a kimondatlan meglepetés.**

| Mi maradt ki | Miért | Mi a kockázata |
|---|---|---|
| | | |

---

## 5. Reviewer-körök

> Ha volt Customer Voice vagy CodeX reviewer, **minden kör ide kerül** — hogy a
> folyamat oda-vissza auditálható legyen: mit mondott, mi lett belőle, és ha
> nem lett semmi, miért.

### Kör 1 — *(reviewer típusa)*

| Mit mondott | Mi lett belőle | Ha elutasítva: miért |
|---|---|---|
| | | |

### Kör 2 — *(reviewer típusa)*

| Mit mondott | Mi lett belőle | Ha elutasítva: miért |
|---|---|---|
| | | |

---

## 6. A mérés állapota

> **A mérőeszköz állapota is a mérés része.** Ez a szakasz azért van, mert
> háromszor fordult elő, hogy a zöld a mérő gépéről szólt, nem a repóról.

| Kérdés | Válasz |
|---|---|
| Tiszta `git worktree`-ben mértél? *(nem a munkafában)* | ☐ |
| Friss `npm ci` (vagy megfelelője) futott? | ☐ |
| A munkafa a mérés után tiszta? (`git status`) | ☐ |
| Maradt-e nem követett fájl, ami nélkül a build bukna? | |
| Változott-e függőség (`package.json` / lock)? | |

---

## 7. Összefoglaló

| | |
|---|---|
| **Kész?** | ☐ igen · ☐ igen, fenntartásokkal · ☐ nem |
| **Ha fenntartásokkal: mik?** | |
| **Commitok** | |
| **Tesztek összesen** | *(fájl / eset, projektenként)* |
| **Typecheck** | ☐ tiszta |
| **Mit nézzen meg először egy ember?** | *(hova kattintson, mit nyisson meg)* |
