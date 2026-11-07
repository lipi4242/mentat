# Todo sablon (HU)

Egyetlen konkrét feladat elvégezhető formában.

## Mikor hozz létre ilyet

Bármilyen konkrét feladat, amelynek elvégezhető formája van — ige + tárgy, meg lehet
jelölni késznek. Ha egy feladatnak több mint ~5 részlépése van, vagy több munkameneten
átível, fontold meg a `specification` használatát.

## Frontmatter

```yaml
---
type: todo
status: open   # open | in-progress | done | cancelled
priority: med  # low | med | high
due: ÉÉÉÉ-HH-NN   # opcionális
tags: [...]
---
```

## Tartalom

1. **Feladat** — egy sor, igével kezdve (pl. "Készítsd el az áprilisi számlát").
2. **Kontextus** — miért fontos és honnan ered (1–3 mondat vagy link).
3. **A "kész" definíciója** — 1–3 felsoroláspontban pontosan mikor jelölhető késznek.

## Fájlnév

`agy/todos/<slug>.md`

## Példa

```yaml
---
type: todo
status: open
priority: high
due: 2026-05-02
tags: [pénzügy, acme]
---
```

**Feladat:** Készítsd el a Acme Studio ügyfél áprilisi számláját.

**Kontextus:** Havi számlázási ciklus. A sablon itt található: `agy/procedures/invoicing.md`.

**A "kész" definíciója:**
- Számla PDF előállítva a helyes tételekkel
- Elküldve az ügyfélnek emailben
- Fizetési dátum feljegyezve a pénzügyi nyilvántartóban
