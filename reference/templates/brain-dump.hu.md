# Brain Dump sablon (HU)

A tulajtól érkező hosszú üzenet nyers rögzítése. Feldolgozás előtt szó szerint kerül mentésre.

## Mikor hozz létre ilyet

A tulaj kb. 200 szónál hosszabb üzenetet küld, ami gondolatfolyam — több ötlet,
követelmény vagy kontextus egyszerre zúdul ki. Felismered, hogy ez több, mint egy
egyszerű utasítás.

## Frontmatter

```yaml
---
type: brain-dump
date: ÉÉÉÉ-HH-NN
topic: <2-4 szavas slug>
processed: false
tags: [...]
---
```

## Tartalom

1. **Nyers átirat** — illeszd be a tulaj üzenetét szó szerint. Ne szerkeszd, ne
   összefoglald, ne formázd át.
2. **(Feldolgozás után)** Egy "Feldolgozva" szekció a kinyert entitások listájával,
   linkekkel a létrehozott/frissített entitásfájlokhoz, és egy bekezdéses összefoglalóval.
3. **Nyitott kérdések** — csak ha van (üres fejlécet ne hagyj); amit a szövegből nem tudtál eldönteni, soronként egy,
   `- [ ] tisztázandó: ...` jelöléssel.

## Naprakészen tartás

Ha a FELHASZNÁLÓ később megválaszolja valamelyik nyitott kérdést — ebben vagy egy
későbbi sessionben —, ugyanabban a körben térj vissza ehhez a fájlhoz, és pipáld
ki (`- [x] tisztázva ÉÉÉÉ-HH-NN: <válasz egy sorban> → <fájl, ahova került>`).
A nyers átiratot soha nem szerkeszted.

## Fájlnév

`agy/brain-dumps/ÉÉÉÉ-HH-NN-<topic-slug>.md`

## Példa

```markdown
---
type: brain-dump
date: 2026-04-29
topic: q3-strategia
processed: false
tags: [stratégia, munka]
---

# Q3 Stratégia Brain Dump

Szóval gondolkodtam a Q3-on és három dolog van a fejemben...
[szó szerint folytatódik]
```
