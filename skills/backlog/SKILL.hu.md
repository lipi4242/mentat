---
name: backlog
description: Munka az Admin közös munkatárában (teendők, ügyek, elfogadási feltételekkel ellátott backlog-tételek) backlog-gazdaként (PM), fejlesztőként vagy egy ügy gazdájaként. Hívd meg, ha munkát adsz át egy másik ágensnek vagy átveszel tőle, ha valaki megkérdezi, kinél a labda, és minden olyan tickben, amelynek tervében ott a `todo_labda`.
---

# Skill — `backlog`

**Hívd meg**, ha munkát adsz ki valakinek (egy másik ágensnek, vagy magadnak
fejlesztőként), átveszed a neked kiadott munkát, eldöntöd, hogy egy kész munka
elfogadható-e, egy hosszú folyamatot ügyként követsz, vagy a tervben ott a `todo_labda`.

Egy tár, egy postaláda: a teendők, az ügyek és a backlog-tételek az Admin
teendőlistájában élnek, és minden, ami velük történik, a `changes`-en át ér el
hozzád. **A labda** annál van, akinek most lépnie kell. A tokened a
személyazonosságod: minden írás a tiéd, és soha nem írhatsz más nevében.

Minden parancs a repó gyökeréből fut: `python3 -m anytime_todo.cli …` (lent: `todo …`).
Ha a repóban nincs `anytime_todo`, de a boxon van `mentat-todo` (a fleet telepíti), az
ugyanez a CLI a box checkoutjából, a te azonosságoddal: `mentat-todo …`.

## 0. lépés — Megvan?

A `todo me` kiírja, ki vagy. Ha azt írja, hogy a csomag nincs beállítva, ennek
az ágensnek még nincs Adminja: mondd el a FELHASZNÁLÓnak, hogy az Admin a Mentat
**teendő- és backlog-kezelője**, és ajánld fel (`admin/README.md`, „Connect your
agent”). Az igene nélkül ne vezess helyette backlogot markdown-fájlokban.

## 1. lépés — A postaládád, minden tickben

1. `todo changes`: a neked szóló események a kurzorod után, a legrégebbivel kezdve.
2. Mindegyiket intézd el: válaszolj a kérdésre vagy az említésre
   (`todo task comment ID --text …`), és lépj abban, ami a tiéd lett
   (`todo ball`: minden, aminél nálad a labda).
3. Csak ezután: `todo changes --ack <last_seq>`. Amit nem intéztél el, azt ne
   nyugtázd. Ha a nyugta előtt leállsz, legfeljebb újra elolvasod ugyanazt.

## 2. lépés — PM-ként (a tétel gazdájaként)

Egy tétel útja: `draft` → `issued` (KIADVA) → `taken` (ÁTVÉVE) → `review` → `done`,
mellette `hold` (HOLDRA) és `dropped`. A tétel elejétől a végéig a tiéd.

1. **Úgy írd meg, hogy más is meg tudja csinálni:** `todo item new --project KULCS
   --title … --description …`. A leírásban: miért, mi tartozik bele, mi **nem**
   tartozik bele, és ki dönt. A kérő szó szerinti mondatai a `--quote`-ba
   kerülnek (hogy hol mondta, az a `--quote-ref`-be).
2. **Minden elfogadási feltétel legyen mérhető:** feltételenként egy
   `--ac "Kész, ha …"` („390 px-es képernyőn a feliratok nem metszik a pöttyüket”).
   Egy AC azonosítója sosem változik; a szövegét az `item ac-edit` írja át, ne törölj és vegyél fel újat.
3. **Add ki:** `todo item issue KULCS --dev <handle>` (a fejlesztő lehetsz te is).
   Nézd meg, melyik tétel maradt `issued`, és nem vette át senki; egyszer kérdezz
   rá kommentben, időzítővel soha.
4. **Dönts a jelentésről.** A `todo item show KULCS` minden eredményt az AC-je
   mellett mutat. Minden eredményt vess össze a bizonyítékával (nyisd meg a
   tesztet, a fájlt, a PR-t).
   - Minden met vagy na, és a bizonyíték megáll: `todo item accept KULCS --checked`.
   - Különben: `todo item reject KULCS --fail AC_ID="mi hiányzik" … --note …`,
     minden el nem fogadott AC-re egy `--fail`. A tétel visszamegy a fejlesztőhöz.
5. `hold` (előbb döntés kell), `resume`, `drop` (nem készül el): mindegyik `--note`-tal.

## 3. lépés — Fejlesztőként

1. **Vedd át, amikor elkezded:** `todo item take KULCS`. Ezt látja a PM olvasási nyugtaként.
2. **Ha nem tudod vagy nem kellene megcsinálni:** `todo item handback KULCS --note "<miért>"`. Ne ülj rajta.
3. **Ha kész:** `todo item show KULCS --form --lang hu > urlap.md`, töltsd ki
   (`ac-form.hu.md`), aztán `todo item submit KULCS --form urlap.md`.
   - **Minden** AC-hez adj bizonyítékot. Amit nem teljesítettél, az `not_met`,
     indokkal: mondd ki egyenesen, a PM dönt.
   - A PR-t a `pr:` sorba írd, az állapotát a `gh pr view` alapján.
4. Elutasítás után **friss** űrlapot kérj: a következő jelentés új kör.

## 4. lépés — Ügyek (hosszú, egyszeri folyamat)

1. **Te javaslod, ember hagyja jóvá:** `todo case new --title … --goal "<mit
   jelent a kész>" [--frame …] [--next-action …] [--waiting-on …] [--review-every 7]`.
   Az általad felvett ügy javaslat, amíg egy ember jóvá nem hagyja. Ismétlődő kötelezettség nem ügy.
2. A `next_action` a **te** következő lépésed; a `waiting_on` az, akit a táron
   kívül sürgetsz. Mindkettőt tartsd frissen: `todo case update ID …`.
3. Minden tickben: `todo case review-due`; nézd át mindegyiket, lépj, aztán `todo case review ID --note …`.
4. Tudatosan zárd le: a `todo task done ID --children close|keep` dönti el, mi
   lesz a nyitott teendőivel. Az alatta nyitott backlog-tételt előbb el kell fogadni vagy ejteni.

## Soha

- Ne írj egy ember nevében, és ne tedd egy ember nevét a saját szavaid alá.
- Senkit ne sürgess időzítővel, és új információ nélkül egynél többször se.
- Ne fogadj el tételt, amelynek a bizonyítékát nem nézted meg.
