# Exploration sablon (HU)

Élő dokumentum egy témához, amelyet többször is megbeszélnek, mielőtt döntés születne.

## Mikor hozz létre ilyet

Olyan téma, amelyről a tulaj többször is beszélget, mielőtt eldönti, hogy belőle
lesz-e valódi projekt. Több struktúra, mint egy brain dump, kevesebb elköteleződés,
mint egy projekt.

## Frontmatter

```yaml
---
type: exploration
status: active   # active | paused | graduated | abandoned
created: ÉÉÉÉ-HH-NN
last_touched: ÉÉÉÉ-HH-NN
tags: [...]
---
```

## Tartalom

1. **A kérdés, amit feszegetünk** — egy mondat arról, amit megpróbálunk kideríteni.
2. **Miért most** — egy rövid bekezdés arról, mi hívta életre ezt.
3. **Nyitott szálak** — felsorolás, csak bővíteni lehet; minden elem megválaszolatlan
   kérdés vagy vizsgálni érdemes irány.
4. **Eddigi döntések** — dátummal előzött felsorolás, pl. `2026-04-29 — X-et választottuk
   Y helyett, mert …`.
5. **Kapcsolódó brain dumpok** — kapcsolódó brain-dump fájlok elérési útjai.

## Fájlnév

`agy/explorations/<slug>.md`

## Példa

```yaml
---
type: exploration
status: active
created: 2026-04-29
last_touched: 2026-04-29
tags: [termék, árazás]
---
```

**A kérdés, amit feszegetünk:** Felhasználónként vagy használat alapján számlázzunk?

**Miért most:** Két enterprise érdeklődő kérdezte ezen a héten az árazást, és nem volt válaszunk.

**Nyitott szálak:**
- Mit számítanak fel a közvetlen versenytársak?
- Mi a tulaj megérzése a pozicionálással kapcsolatban?

**Eddigi döntések:**
- 2026-04-30 — kizártuk a freemiumot; túl drága a fenntartása.

**Kapcsolódó brain dumpok:** `agy/brain-dumps/2026-04-29-arazas-gondolatok.md`
