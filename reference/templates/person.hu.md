# Person sablon (HU)

Profil olyan személyről, akinek visszatérő részletei fontosak.

## Mikor hozz létre ilyet

A tulaj kétszer vagy többször megemlít valakit, VAGY olyan személyről van szó, akinek
adatai befolyásolják a jövőbeli döntéseket — maga a tulaj, családtagok, kulcskollégák,
kulcsügyfelek.

## Frontmatter

```yaml
---
type: person
name: Teljes Név
role: <beosztás vagy kapcsolat>
relationship: colleague | client | friend | family | self
contact: email vagy felhasználónév (opcionális)
tags: [...]
---
```

## Tartalom

1. **Ki ő** — 1–3 mondat: szerepe, kontextusa, miért jelenik meg ebben a munkaterületen.
2. **Kapcsolat a tulajjal** — kapcsolatuk története, hogyan ismerkedtek meg, min
   dolgoznak együtt.
3. **Ami fontos** — preferenciák, korlátok, érzékenységek, amelyek relevánsak
   az interakciókhoz.
4. **Visszatérő témák** — felsorolás azokról a témákról, amelyek rendszeresen előkerülnek
   ezzel a személlyel.

## Fájlnév

`agy/people/<slug>.md`

## Példa

```yaml
---
type: person
name: Kovács Anna
role: Vezető tervező, Acme Studio
relationship: colleague
contact: anna@example.com
tags: [design, acme]
---
```

**Ki ő:** Anna a Acme Studio vezető tervezője. Ő felelős a vizuális rendszerért,
és ő hagyja jóvá az összes front-end PR-t.

**Kapcsolat a tulajjal:** 2024 óta dolgoznak együtt. Az aszinkron kommunikációt
részesíti előnyben a meetingekkel szemben.

**Ami fontos:** Pénteken ne írj neki. Nem kedveli a hatókör-bővülést sprint közben.

**Visszatérő témák:**
- Komponenskönyvtár frissítések
- Márkakonzisztencia-ellenőrzések
