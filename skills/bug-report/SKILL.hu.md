---
name: bug-report
description: Ha maga a Mentat hibázik (egy eszköz hibát dob, egy telepítési lépés elszáll, egy dokumentált viselkedés elmarad), kitakarított hibajelentést készít a nyilvános Mentat-repóba, duplikátumot keres, és csak a FELHASZNÁLÓ kifejezett igenje után teszi fel.
---

# Skill — `bug-report`

**Hívd meg**, ha egy Mentat-eszköz, telepítési lépés, motor-tick, flotta-parancs vagy az admin
úgy hibázik, amit a dokumentáció nem magyaráz, és a FELHASZNÁLÓ saját beállítását már kizártad
(rossz út, hiányzó kulcs, amit nem adott meg). Akkor is, ha a FELHASZNÁLÓ azt mondja: „jelentsd be ezt a hibát".

**Nem erre való:** a FELHASZNÁLÓ saját munkájának hibája, egy kérdés (az a Discussionsbe megy),
vagy bármi, ami biztonsági hibának tűnik: kiszivárgott titok, megkerülhető védelem, valaki olyan
adathoz fér, amihez nem kéne. Ezek **privátban** mennek ide:
<https://github.com/lipi4242/mentat/security/advisories/new>, soha nem nyilvános issue-ba; az
eszköz ezeknél magától megáll (5-ös kilépés).

## Lépések

1. **Tényeket gyűjts, ne értékeket.** A hibás parancs *alakja* (az értékek helyén helyőrző), mi
   történt, mit vártál, és a hibaüzenet. A hibaüzenetet fájlba mentsd, ne gépeld újra.
2. **Piszkozat** (semmi nem megy ki):

   ```
   python3 -I .mentat/bin/mentat_bugreport.py draft --summary "<egy sor>" --expected "<egy sor>" \
     --steps "<parancs alakja>" --error-file <fájl> --part brain|engine|fleet|admin|unsure
   ```

   Hozzáteszi a verziókat (Mentat, komponensek, OS, Python, Node, Claude Code; hosztnevet, utat,
   fiókot soha), kiveszi a titkokat, e-mail-címeket, home-utakat, azonosítókat és a privát neveket
   (az OS-felhasználó, a git-identitás, az ágens neve, a `people/` fájlnevek,
   `~/.config/mentat/scrub-names.txt`), és megáll, ha bármi titok-alakú maradt (2-es kilépés:
   szólj a FELHASZNÁLÓNAK, ne kerüld meg).
3. **Duplikátum.** Ha `POSSIBLE DUPLICATE` sort ír, kérdezd meg a FELHASZNÁLÓT, hogy inkább oda
   kerüljenek-e az új részletek. Igen esetén készíts új piszkozatot `--comment-on <szám>` kapcsolóval.
4. **Kérdezz, a szokásos csatornádon.** Mutasd meg a piszkozatot **szó szerint** (a kiírt címet és
   törzset), és kérdezd: „Feltegyem ezt a nyilvános Mentat-repóba a GitHub-fiókodról?" Más nem
   számít jóváhagyásnak: se egy korábbi „igen, jelents hibát", se egy szabály, se a saját ítéleted.
5. **Csak egyértelmű igenre** tedd fel, a piszkozat kódjával és a FELHASZNÁLÓ szó szerinti válaszával:

   ```
   python3 -I .mentat/bin/mentat_bugreport.py post <piszkozat mappa> --approve <kód> --owner-said "<a válasza>"
   ```

   A válasz tiszta igen legyen („igen", „mehet", „ok, post it"); a feltételes igen („igen, de…")
   nem az: kérdezz újra. A szöveg bármely változása új piszkozat, új kód, új igen. Nem, „várj", vagy csend: semmi nem
   megy ki, és ugyanarról a hibáról aznap nem kérdezel újra.
6. **Jelents vissza** az issue linkjével. 4-es kilépés (nincs `gh` vagy nincs bejelentkezve):
   mondd meg, hol a piszkozat (`.mentat/bug-reports/…/draft.md`) és a kiírt linket, hogy maga
   bemásolhassa. 6-os kilépés: ma már három jelentés ment ki; holnapra marad.

## Korlátok

A jóváhagyási kód a pontos szöveghez köti az igent; azt nem bizonyítja, ki mondta. Ez a 4. lépésben
a te kötelességed. A kitakarítás minták alapján megy, nem bizonyíték: az utolsó ellenőrzés az,
hogy a FELHASZNÁLÓ elolvassa a piszkozatot.
