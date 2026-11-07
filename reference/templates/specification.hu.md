# Specification sablon (HU)

Egy fejlesztés vagy frissítés több részfeladattal, egyetlen szándék alatt.

## Mikor hozz létre ilyet

Az agent bármilyen frissítése VAGY a tulajnak szánt érdemi fejlesztés, amelynek
több részfeladata van. Ha csak egy lépés szükséges, használj `todo`-t helyette.

## Frontmatter

```yaml
---
type: specification
title: <rövid, leíró cím>
status: draft   # draft | active | done | abandoned
created: ÉÉÉÉ-HH-NN
target: ÉÉÉÉ-HH-NN   # vagy "ongoing"
tags: [...]
---
```

## Tartalom

1. **Cél** — egy bekezdés, amely elmagyarázza, miért létezik ez, és milyen problémát old meg.
2. **Megközelítés** — már meghozott kulcsdöntések (felsorolás).
3. **Hatókörön kívül** — explicit lista arról, amit ez a spec NEM fed le.
4. **Teendők** — beágyazott jelölőnégyzetes lista; csak akkor emeld ki önálló `todo`
   entitássá, ha egy részfeladatnak önálló felelőse van vagy több munkameneten át kell követni.

## Fájlnév

`agy/specs/<slug>.md`

## Példa

```yaml
---
type: specification
title: Connector: Gmail olvasási hozzáférés
status: active
created: 2026-04-29
target: 2026-05-10
tags: [connector, gmail]
---
```

**Cél:** Olvasási hozzáférést biztosít az agentnek a tulaj Gmailéhez, hogy a reggeli
bejelentkezés során tudja szűrni a bejövő emaileket.

**Megközelítés:**
- OAuth2 service-account használata domain-wide delegálással
- Hitelesítők adatok `.env`-ben tárolva, soha nem commitolva

**Hatókörön kívül:** Email küldés (külön spec), naptárintegráció.

## Teendők

- [ ] Séma megtervezése
  - [ ] Frontmatter mezők
  - [ ] Szekció struktúra
- [ ] Validáció bekötése
- [ ] Pilot egy valós eseten
