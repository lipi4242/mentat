# Subagent döntési rekord sablon (HU)

ADR, amit **a perszónánál** is tartunk, nem csak a projektben.

## Mikor hozz létre ilyet

Egy projektben döntési rekord születik, miközben ez a perszóna részt vett benne,
és a döntés az alábbiak egyike:

- **róla szól** — a hatásköréről, a területéről, arról, hogyan hívjuk;
- **a projekttel való kapcsolatáról szól** — mi tartozik itt rá, és mi nem;
- **egy olyan válasz, amit ő adott, és ami fontos marad** — egy döntés, ami
  alakítja, hogy ki ő, és amit egy későbbi hívásnak nem kellene nulláról
  újratárgyalnia.

Ha a döntés tisztán a projektről szól, és semmit nem mond erről a perszónáról,
hagyd a projektben. **Ne másolj át mindent** — minden ADR gyűjteménye egy második
archívum, nem személyiség.

## Frontmatter

```yaml
---
type: subagent-decision
name: <ugyanaz a slug, mint a personan>
number: NNN
status: eldontve       # eldontve | felulirva
supersedes: NNN        # opcionalis
tags: [...]
---
```

## A törzs szerkezete

1. **Kontextus** — miről kellett dönteni, és miért került ehhez a perszónához.
2. **Döntés** — mi lett a döntés, egy bekezdésben.
3. **Ki döntött** — a perszóna, a felhasználó, vagy mindkettő. Ha a perszóna egy
   korábbi felhasználói döntés ellenében döntött, **mondd ki**.
4. **Következmények** — mi következik belőle, beleértve, hogy mit zár el.
5. **Mit mond ez a perszónáról** — az a mondat, amiért érdemes itt tartani, és
   nem csak a projektben.

## Számozás

Perszónánként folyamatos, három számjegy, sosem újrahasznált: `001-`, `002-`…
A felülírt rekordot **nem töröljük** — megjelöljük, és az új visszahivatkozik rá.

## Fájlnév

`agy/subagentek/<nev>/decisions/NNN-<slug>.md`
