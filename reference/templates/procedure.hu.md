# Procedure sablon (HU)

Visszatérő feladat forgatókönyve.

## Mikor hozz létre ilyet

Olyan feladat, amelyet a tulaj egynél többször, meghatározott módon szeretne elvégeztetni.
Példák: "reggeli email-szűrés", "Interfood rendelés", "heti áttekintés". Ha a feladat
csak egyszer fordul elő, használj `todo`-t helyette.

## Frontmatter

```yaml
---
type: procedure
name: <rövid-slug>
frequency: on-demand   # on-demand | daily | weekly | monthly | ...
uses_connectors: []    # connector nevek listája, pl. [gmail, ticktick]
tags: [...]
---
```

## Tartalom

1. **Mit csinál** — egy sor: mit állít elő vagy ér el a procedúra.
2. **Trigger** — mikor kell futtatni (ütemezés, esemény vagy a tulaj explicit kérése).
3. **Lépések** — számozott lista egyszerű prózában; minden lépés egy egyértelmű teendő.
4. **Eredmény** — mit kap a tulaj a végén (riport, üzenet, frissített fájl).
5. **Élhelyzetek / mikor kérdezz vissza** — olyan szituációk, amikor a procedúrának
   meg kell állnia és ellenőriznie kell, mielőtt cselekszik.

## Fájlnév

`agy/procedures/<name>.md`

## Példa

```yaml
---
type: procedure
name: morning-email-triage
frequency: daily
uses_connectors: [gmail]
tags: [email, reggeli]
---
```

**Mit csinál:** Összefoglalja az éjszakai emaileket, és jelöli a ma teendőket igénylő elemeket.

**Trigger:** A tulaj azt mondja "reggeli bejelentkezés", vagy munkanap reggel 10:00 előtt van.

**Lépések:**
1. Az elmúlt 12 óra olvasatlan szálainak lekérése a gmail connectoron keresztül.
2. Kategorizálás: teendő szükséges / tájékoztató / hírlevél / egyéb.
3. Kategóriánként csoportosított összefoglaló piszkozat készítése.
4. Bemutatás a tulajnak; várakozás az utasításra.

**Eredmény:** Felsorolásos összefoglaló a chatben; emailt csak explicit jóváhagyással küld.

**Élhelyzetek:** Ha > 30 olvasatlan szál van, kérdezz rá a tulajnál, mielőtt mindet feldolgozod.
