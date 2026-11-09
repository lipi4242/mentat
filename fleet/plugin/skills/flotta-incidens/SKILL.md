---
name: flotta-incidens
description: Mit csinálj egy „[flotta] …” című todo-feladattal — flotta-menedzserként kaptad, mert egy ágens képesség-próbája piros (vagy egy box nem jelent). Átvétel, javítás csak a `fleet repair-exec` végrehajtón, lezárás csak ellenőrzéssel. Használd, ha a labdádban (`mentat-todo ball`) ilyen feladat van.
---

# /fleet:flotta-incidens — flotta-menedzserként

A flotta-menedzser szerep: a `managers.json` szerint te vagy egy cél
(ágens, box vagy `*`) láncának egyik tagja. A központ (Mentat Admin, `flotta`
plugin) a lánc első **alkalmas** tagjának adja az incidenst; ha az kiesik, nem
veszi át, vagy lejár a kerete, a következőnek. Terv:
`fleet/docs/design/2026-11-08-flotta-menedzser.md`.

## Lépések

1. **Átvétel 10 percen belül**: `fleet incident claim <incidens> --as <a te flottaneved>`.
   30 perces keretet kapsz, meghosszabbítás nincs. Ha nem veszed át, a lánc
   következője kapja.
2. **Csak a végrehajtón át lépj**, a cél boxán (v1: a saját boxodon):
   - `fleet repair-exec <incidens> doctor --agent <ágens>`: csak olvas, mindig ezzel kezdj;
   - `fleet repair-exec <incidens> doctor-fix --agent <ágens>`: újraindíthat, a keretből fogy;
   - `fleet repair-exec <incidens> bridge-install --agent <ágens>`;
   - `fleet repair-exec <incidens> unquarantine --agent <ágens> --cause login-renewed|bridge-conflict-gone`.
     Csak ez a két ok működik; más okkal ember kell.
3. **Lezárás csak ellenőrzéssel**: `fleet repair-exec <incidens> postcheck --agent <ágens>`.
   Csak a zöld, nonce-os próba zár. Ütemezett ágensnél az kell hozzá, hogy az
   újraindulás óta lefusson egy tick. Ha még nincs, a keretben később futtasd
   újra. Kézzel ne zárd le.
4. Nem megy, vagy nem a te dolgod: `fleet incident release <incidens> --as <neved>`.
   Ezzel azonnal a következőé.

## Kilépési kódok (`repair-exec`)

- `0`: rendben.
- `1`: nem sikerült, bizonytalan, vagy az ágens dolgozott.
- `2`: használati hiba: nem a te boxod, nincs átvétel, a saját incidensed, vagy
  desktopon újraindító lépés.
- `3`: a cél zárja foglalt (egy másik végrehajtó dolgozik rajta).
- `4`: a Worker nem engedi: elavult átvétel, lejárt keret, átadás folyik.
- `5`: ember kell. Ilyenkor nincs több teendőd.

`4` után ne próbálkozz megkerülő úton.

## Engedély-mátrix (kérdezés nélkül)

| lépés | boxos cél | desktopos cél | a saját egységed |
|---|---|---|---|
| doctor (olvas) | igen | igen | — |
| doctor-fix / bridge-install | igen, a keretből (3/óra/ágens) | nem értelmezhető | **soha** |
| unquarantine | csak a két gépileg igazolt okkal | nem értelmezhető | **soha** |
| szabad parancs, titok, más repójába írás, registry | **soha** | **soha** | **soha** |

A saját incidensedet nem kapod meg: egy másik menedzser javít, és ha nincs ilyen,
a tulajdonos e-mailt kap. Dolgozó ágenst (friss transzkript) nem indítunk újra:
a végrehajtó a kereted végéig vár. A néma, de élő ágenst újra lehet indítani.

## Ha nem megy

Nem kell külön szólnod. E-mail megy a tulajdonosnak, ha a lánc üres vagy elfogy,
ha elfogy a keret, ha egy lépés hatása nem dönthető el, vagy ha az incidens 60
percnél tovább nyitva van. A levél felsorolja, ki mit próbált.
