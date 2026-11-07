# Subagent-history sablon (HU)

A napló, amitől a perszóna fejlődik.

## Mikor írd

**Minden használat után.** Nem opcionális: enélkül az inventár
prompt-gyűjtemény, nem tanuló rendszer.

**Ki írja:** alapesetben az, aki meghívta — a subagent meghalhat, mielőtt írna.
Ha a perszóna maga összefoglalta a működését, azt illeszd be, és egészítsd ki
azzal, amit csak a hívó látott (bejött-e a javaslat?).

## Frontmatter

```yaml
---
type: subagent-history
name: <ugyanaz a slug, mint a personan>
tags: [...]
---
```

## A törzs szerkezete

Használatonként egy dátumozott szakasz, a legújabb elöl:

```markdown
## ÉÉÉÉ-HH-NN — <a feladat egy mondatban>

| | |
|---|---|
| **Hívta** | |
| **Mire** | |
| **Mit adott** | |
| **Mi lett belőle** | elfogadva / módosítva / elvetve — és miért |
| **Bejött?** | (utólag, ha kiderült) |

**Tanulság:** mit kérnénk legközelebb máshogy, vagy mit érdemes beépíteni a
`persona.md`-be.
```

## Fájlnév

`agy/subagentek/<nev>/history.md`

## Miért a „mi lett belőle" oszlop a lényeg

Egy napló arról, amit a perszóna *mondott*, jegyzőkönyv. Egy napló arról, hogy
**mi történt a tanácsával**, tudás. Az elvetett javaslatok gyakran a
legtanulságosabb bejegyzések — írd oda, miért lettek elvetve.
