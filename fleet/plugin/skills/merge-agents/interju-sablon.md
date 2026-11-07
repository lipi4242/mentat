# Interjú-sablon — ágens-összeolvasztás (fogadó és donor)

Küldd el szó szerint, a `<…>` helyekre írd be a valódit. Egy ágensnek ~6 perc.
Fiókon át, RC nélkül: `fleet ask <ágens> --file <ez-a-fájl-kitöltve>` — a válaszfájl
útját a pane-be küldött sor adja meg, ilyenkor az alábbi `<út>` sort törölheted.

---

Szia! `<a tulajdonos>` kérésére összeolvasztjuk `<donor>` feladatait `<fogadó>`-val.
Hat kérdés. **A válaszodat ebbe a fájlba írd: `<út>/interju-<ágens>.md`**, és a
legutolsó sora legyen pontosan: `KÉSZ`. Ne Telegramra válaszolj, és ne a
csoportba. Ha valamit nem tudsz, írd oda, hogy nem tudod — ne találgass.

1. **Mit csinálsz ténylegesen?** A rendszeres feladataid, mindegyiknél: milyen
   gyakran, mi indítja (cron, tick, kérés), és hova ír ki (naptár, levél,
   issue-tracker, csoport).
2. **Mi él csak szokásként?** Amit rendszeresen csinálsz, de nincs mögötte kód
   vagy ütemezés — csak a memóriádban vagy a szabályaidban.
3. **Mi a legnagyobb hiányod?** Mi miatt maradt el valami az elmúlt hetekben
   (ütemező, jogosultság, login, adat)?
4. **Milyen kulcsokkal és kinek a nevében írsz kifelé?** Csak a kulcs NEVE és a
   fájl helye — értéket ne írj. A választ a szabályaidból és az emlékezetedből add:
   kulcsfájlt most ne nyiss meg, maszkolva sem (a `sed`-es maszk egy JSON-kulcson
   nem takar semmit).
5. **Mi folyik most?** Nyitott ügyek, ígéretek, határidők, és merge-eletlen ágak
   vagy PR-ek, amikben döntés él.
6. **Mit tennél másképp az összeolvasztásban?** Mi veszhet el, és mit kell a
   fogadónak az első napon tudnia?

---
