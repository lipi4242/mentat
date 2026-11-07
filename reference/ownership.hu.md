# Tulajdon és publikálási határ

[English](ownership.md)

Az agy-repóban kétféle szöveg él. Ha külön tartjuk őket, a termék frissíthető
a FELHASZNÁLÓ memóriájának érintése nélkül, és a memória nem szivárog ki.

## Kezelt és személyes

| | **Kezelt** (a terméké) | **Személyes** (a FELHASZNÁLÓé) |
|---|---|---|
| Mi | az `AGENTS.md` `mentat:managed` jelölők közötti szabály-blokkjai; a `skills/`-ből másolt skillek (pl. `.claude/skills/<név>/SKILL.md`); `.mentat/bin/` | minden más: az `agy/` — entitások, brain-dumpok, emberek, döntések, ügyek, konnektorok, eljárások, subagentek és történetük; `projects/`; az `AGENTS.md` jelöletlen szakaszai (identitás, működési hozzáállás, bármi, amit a FELHASZNÁLÓ hozzáírt) |
| Ki írja | a frissítés (`mentat upgrade`), egy blokkot **egészében** cserélve | az ágens, a FELHASZNÁLÓval |
| Sablonok | igény szerint töltődnek a tagelt kézikönyvből, sosem másoljuk őket — nincs mit birtokolni | — |

Egy kezelt blokk az `AGENTS.md`-ben:

```markdown
<!-- mentat:managed:start entities -->
5. **Entitás-feldolgozási szabály** — …
<!-- mentat:managed:end entities -->
```

Szabályok:

1. **Kezelt blokkon belül ne szerkessz.** Ha a FELHASZNÁLÓ egy termék-szabályt
   másképp akar, az eltérést személyes szakaszba írd („Saját szabályaink" vagy
   a megfelelő személyes szakasz), és mondd ki, hogy felülírja a blokkot.
   Ütközésnél a személyes szöveg nyer.
2. **A frissítés csak jelölők között ír.** Az azonos azonosítójú blokk
   tartalmát cseréli, az új blokkokat hozzáadja, a jelölőkön kívüli szöveget
   bájtra pontosan meghagyja. Hiányzó vagy páratlan jelölőjű blokkhoz nem
   nyúl, hanem jelenti.
3. **Az azonosítók stabilak.** `reference-manual`, `layers`, `brain-dumps`,
   `entities`, `files`, `frameworks`, `claims`, `large-work`. Az átnevezett blokk egy új
   meg egy törölt blokk.
4. **A termék soha nem ír személyes tartalmat** — se telepítéskor, se
   frissítéskor. Kivétel csak az, amit a FELHASZNÁLÓ ágense a telepítés során a
   FELHASZNÁLÓval együtt hoz létre.

## Publikálási határ

Az agy-repó **privát memória**: benne vannak a FELHASZNÁLÓ gondolatai, más
emberek adatai, és hogy a FELHASZNÁLÓ eszközei hogyan vannak bekötve.

- Ne adj hozzá publikus remote-ot, ne tedd publikussá, és ne told közös
  szervezetbe a FELHASZNÁLÓ kifejezett, arra a remote-ra szóló döntése nélkül.
- A `.env*` és a `.mentat/` mindig gitignored.
- Ha valamit publikálni kell — egy projektet, egy eljárást, egy sablont, amit
  a FELHASZNÁLÓ írt —, **azt az egyet másold át egy külön repóba**, és azt
  publikáld. Másolás előtt nézd át nevekre, e-mail-címekre, IP-címekre, belső
  útvonalakra és tokenekre, és mutasd meg a FELHASZNÁLÓnak a fájllistát.
- A saját publikus repóval bíró projekt a `projects/<név>/` alatt saját git
  repóként (vagy submodule-ként) él; `agy/` sosem kerül bele.

Ez a teljes szabály. Nincs szinkronban tartandó engedélylista: az agy-repóban
minden alapból *privát*, a publikálás tudatos másolás.
