
# Fejlesztési folyamat — nagy, nem teljesen specifikált munkára

> **Új ebben a kiadásban.** Eljárás arra az esetre, amikor a felhasználó nagyot
> kér, és nem specifikálja végig. Párja a `subagents.hu.md`: a perszónák a
> 2.3. és a 6. lépésnél lépnek be.

---

## Mikor lép életbe

Ha a felhasználó olyan feladatot ad, ami **nagy szkópú** ÉS **nincs teljesen
specifikálva**.

Nem ilyen: egy elgépelés javítása, egy mező átnevezése, egy kérdés
megválaszolása, egy körülhatárolt hibajavítás. Azt csináld meg.

**A mérce kétség esetén:** ha a feladat végén több, egymással nem
helyettesíthető helyes megoldás lenne, és nem tudod megmondani, melyiket
akarja — akkor ez a folyamat kell.

---

## Miért van ez így

Három drága, megtörtént hibából:

1. **Egy agent kidolgozott egy több száz soros javaslatot, amit el kellett
   dobni**, mert rossz felállásban indult el. Nem a munka volt rossz — a
   *kérdés* nem volt tisztázva, mielőtt elindult.
2. **„Kész" jelentés érkezett olyan munkáról, ami nem működött.** Az űrlap egy
   kitöltött névmezőre azt mondta, hogy töltsd ki — miközben több mint ezer
   teszt volt zöld. A hibaosztályt egyik teszt-készlet sem tárgyalta.
3. **Zöld mérés, ami a mérő gépéről szólt, nem a repóról.** Nem követett
   fájlok, elavult függőségek, egy előző futás maradéka — mindhárom úgy nézett
   ki, mint egy elvégzett munka.

Három szabály tartja az egészet:

> **A szándékot tisztázni kell, mielőtt bárki dolgozni kezd.**
> **A „kész" bizonyítékkal jár, nem jelentéssel.**
> **A mérőeszköz állapota is a mérés része.**

---

## 1. Kérdezd meg a fejlesztési módot

**Mindig kérdezd meg, mielőtt bármit elindítasz.** Ne találgasd, és ne
alapértelmezz.

A kérdés legyen egyetlen, strukturált kör (ne csepegtess), és a válaszok között
szerepeljen a projektben elérhető fejlesztési keretrendszer (pl. egy
terv-vezérelt, subagent-alapú folyamat), valamint a feladathoz illő
alternatívák: közvetlen implementáció, csak terv, csak felmérés.

---

## 2. Ha terv-vezérelt folyamat a választás, két kérdés következik

Ez a kettő **együtt** dönti el, mennyi emberi idő megy bele, és ki hozza a
szakmai döntéseket.

### 2.1 Mennyire vegyen részt a specifikáció előkészítésében?

Nem „igen/nem", hanem **hány kör**:

- **Több kör** — játsszatok le N kérdéskört, amíg részletes specifikáció
  születik. Minden kör EGY témát fedjen le, ne szórja szét a kérdéseket.
- **Egy kör** — egyszer kérdezel végig, aztán mész.
- **Azonnali indulás** — nem akar több specifikációt adni. Ilyenkor a hiányzó
  döntéseket **te hozod meg**, de a döntést és az indoklást **kiírod** — nem
  hallgatólagosan.

### 2.2 Kinek tegye fel a fejlesztő agent a brainstorming kérdéseit?

- **Autonóm** — magában dolgozik, saját ítélete szerint dönt.
- **A felhasználónak** — a kérdések hozzá mennek, te közvetítesz.
- **Külső szakértő modellnek** — egy másik modell (pl. egy független
  kódmodell), külső szakértőként.

**A külső szakértőről:** az az értéke, hogy **ellentmondhat az eredeti kérésnek
is**, ha úgy látja, hogy nem jó ötlet, vagy létezik jobb megoldás. Ne
visszhangnak hívd, hanem ellensúlynak. Ha ellentmond a felhasználó kérésének,
**ne nyeld le**: vidd elé a két álláspontot, és ő döntsön.

### 2.3 A kérdés-szűrő — a szakértő elé, ne a felhasználó elé

**Ez a lépés akkor lép be, ha van szakértő reviewer a csapatban** (pl. UX- vagy
domain-szakértő, lásd a 6. pontot). Ilyenkor a fejlesztő agent kérdései
**NEM közvetlenül a felhasználóhöz mennek**, hanem előbb a szakértőhöz.

**Miért.** A fejlesztő fejlesztőfejjel gondolkodik, és jóhiszeműen olyat is
megkérdez, ami valójában **szakmai döntés** — elrendezés, tipográfia,
navigációs minta, komponens-választás. Ezekhez a szakértő jobban ért, mint a
felhasználó. Ha mindet felvisszük, a felhasználó húsz kérdést kap, amiből ötben
tud érdemben dönteni, a maradék tizenötben pedig tippel — és a tippje
gyengébb lesz, mint a szakértő döntése lett volna.

**A menete:**

1. A fejlesztő összeírja, mit tisztázna. **Ne cenzúrázza magát** — a szűrés nem
   az ő dolga. Jelölje meg, melyiket tartja szakmainak, melyiket termék-szintűnek;
   ez a saját olvasata, információ, de nem döntés.
2. **A szakértő triázsol.** Minden kérdésre két válasz lehet:
   - **„ez az én hatásköröm"** → **dönt benne**, és a döntést kiírja indoklással
     (a formba is bekerül, lásd a 4. lépést);
   - **„ez valóban a felhasználóé"** → felkerül a szűk körbe.
3. **A kettő együtt** állítja össze azt az EGY kérdéskört, ami a felhasználó elé
   megy — rajtad keresztül.

**A szűrés mércéje:**

| A felhasználó elé megy | A szakértőnél marad |
|---|---|
| mit ígérünk az ügyfélnek | elrendezés, tipográfia, térköz |
| mit hagyunk el | navigációs minta (hamburger vs. alsó sáv) |
| mi a fontossági sorrend | komponens-választás, hierarchia, animáció |
| mi kerül időbe vagy pénzbe | hány lépésre bontunk egy űrlapot |
| amit ha rosszul döntünk, az ügyfelet érinti | minden, amiben a szakértő a kompetensebb |

> **A próbakérdés, ha haboznál:** *„ha ezt a felhasználó elé viszem, tudna-e
> jobbat mondani nálam?"* Ha nem — akkor ne vidd. A kérdezés nem udvariasság;
> **egy fölösleges kérdés is a felhasználó idejéből megy el**, és elvonja a
> figyelmet azoktól, amikben tényleg csak ő dönthet.

**A cél, kimondva:** a felhasználó a **lehető legkevesebb** kérdést kapja — csak
azokat, amik a legnagyobb döntésekhez kellenek. Onnantól ezen a kereten belül a
fejlesztő és a szakértő már együtt tud dolgozni.


---

## 3. Teljes körű acceptance criteria

Amikor fejlesztési feladatot adsz ki egy subagentnek, **határozz meg teljes
körű acceptance criteriákat**.

**Nem kell részletesebbnek lenniük a megbeszéltnél** — de **fedjék le a teljes
kört**. A kettő nem ugyanaz:

- *részletesség*: mennyire pontosan írod le az egyes feltételt;
- *lefedettség*: hány dimenzió marad kimondatlanul, amiről kiderülhet, hogy
  „nem így gondoltam".

Egy felhasználói felületnél a teljes kör legalább ennyi:

- **minden képernyőméret** — nem csak asztali gép; mobilon is nézzen ki jól,
- **minden megjelenítési mód** (pl. világos és sötét), ha van ilyen,
- **billentyűzet és képernyőolvasó** — fókusz, címkék, hibaüzenetek,
- **az összes érintett képernyő**, nem csak az, amin épp dolgozik,
- **hibás és üres állapotok**, nem csak a boldog út.

> Ha egy dimenziót szándékosan hagysz ki, **írd le, hogy kihagytad, és miért**.
> A kimondott hiány kezelhető; a kimondatlan meglepetés.

---

## 4. A form: a „kész" bizonyítéka

**Minden kiszervezett fejlesztési feladathoz küldj egy formot** (`.md` fájl), és
kérd meg az agentet, hogy **a feladat részeként töltse ki**. Üres formmal a
munka nincs kész.

A sablon: `reference/templates/acceptance-form.hu.md`

### Mit tartalmazzon

- **az összes acceptance criteriát**, egyenként;
- **minden kérdést, amiből azonnal látszik, hogyan áll az anyag** — nem csak
  azt, hogy kész-e, hanem hogy *mi maradt ki*, *mi bizonytalan*, *mit döntött
  el magától*;
- **tesztet minden feltételhez**;
- a reviewerek visszajelzéseit, ha voltak;
- a **mérés állapotát** (lásd lent).

### Tesztek — ez a form gerince

Fajtája a feltételtől függ, és lehet keverék:

| Fajta | Mire jó |
|---|---|
| **unit teszt** | Tiszta logika, számítás, validáció. |
| **end-to-end teszt** | Végigfut a valódi úton, a felhasználó lépéseivel. |
| **screenshot-alapú kézi teszt** | Amit csak látni lehet: elrendezés, tördelés, mobil nézet. |

Ha egy feltétel teljesül, az agent küldje vissza: **a teszt nevét**, **mit
tesztel**, és **mit bizonyított vele**.

> A harmadik a lényeg, és ezt a legkönnyebb elsunnyogni. „A teszt zöld" nem
> bizonyíték — az a kérdés, hogy **mi lett volna, ha nem működik**. Ezért a form
> külön kéri: *tud-e ez a teszt bukni, és honnan tudod?* A negatív kontroll:
> rontsd el szándékosan, amit a teszt véd, futtasd, nézd meg, hogy elbukik-e,
> majd állítsd vissza — és igazold, hogy visszaállt.

### A tervezés is a formhoz mérődik

**Az agent a saját terv- vagy dizájndokumentumát is ehhez a formhoz mérje**,
amikor a munkát tervezi. Ha a terve nem fed le egy feltételt, az a tervezéskor
derüljön ki, ne a végén.

### Emberi ellenőrzés

**Miután az agent kitöltötte a formot, futtasd meg a felhasználóval is.** Ez nem
formalitás: a form pont attól ér valamit, hogy egy ember ránéz, és azt mondja,
hogy nem.

---

## 5. Worktree és branch

**A fejlesztő agent mindig külön `git worktree`-ben, külön branchen dolgozzon.**

Két okból, és mindkettő megtörtént hiba:

1. **Párhuzamos szerkesztés.** Ha két agent ugyanabban a munkafában dolgozik,
   egymás alól írják ki a fájlokat — és a mérésed olyan állapotot mér, amit
   közben felülírtak.
2. **A munkafa hazudik.** A munkafa tartalmazza a nem követett fájlokat is; egy
   tiszta worktree csak a verziókövetettet — vagyis azt, amit MÁS is kap.

Amikor a munka elkészül: a **branch merge-elésre kerül**, a **worktree
kitakarításra** — ne maradjon felesleges szemét utána.

> Ha a projektben külön kiadási rend van, a merge a fejlesztési ág lezárását
> jelenti, **nem az élesítést**.

---

## 6. Reviewerek, igény szerint

Nem kötelezőek, de nagy szkópnál rendszerint megérik. Használj perszónákat a
subagent-inventárból (`subagents.hu.md`).

### Ügyfélhang (Customer Voice)

Egy **tipikus felhasználó**, vagy egy adott témához kiválóan értő szakértő.
**A hibákat keresi.**

- Feedbacket ad **a tervre ÉS az elkészült verzióra** is.
- **Több kör fusson belőle** — az első kör a nyilvánvalót találja meg, a
  második azt, ami az első javítása után romlott el.
- **A visszajelzései kerüljenek bele a formba**, hogy a folyamat oda-vissza
  auditálható legyen: mit mondott, mi lett belőle, és ha nem lett semmi, miért.

### Ellenérdekelt bíráló (adversarial reviewer)

Külső modell **adversarial szerepkörben**: kritikus szemmel értékeli a
fejlesztést. **Nem az a dolga, hogy egyetértsen.**

---

## Amit ez a folyamat NEM old meg

- **Nem helyettesíti a saját ítéletedet.** Ha a folyamat végigfutott, és a
  dolog mégis rossz, akkor rossz — mondd ki.
- **Nem garantál minőséget attól, hogy kitöltötték a formot.** A form akkor ér
  valamit, ha a tesztek valóban tudnak bukni.
- **Nem menti fel a kiadási rendet.** A merge nem élesítés.
