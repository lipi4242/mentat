# Connector sablon (HU)

Konfigurációs rekord egy külső eszköz integrációjához.

## Mikor hozz létre ilyet

A tulaj először kér segítséget egy külső eszközhöz (Gmail, TickTick, Asana, Strava stb.).
Állítsd be a hitelesítést `.env`-ben (SOHA ne commitold), az interfészt dokumentáld itt.

## Frontmatter

```yaml
---
type: connector
name: <eszköz-neve>
status: configured   # configured | placeholder
auth_location: .env
tags: [...]
---
```

## Tartalom

1. **Mihez kapcsolódik** — egy sor: az eszköz neve, szerepe ebben a munkaterületen.
2. **Hitelesítés + beállítás** — hol vannak a hitelesítők adatok, hogyan kell frissíteni.
   Csak `.env` kulcsnevekre hivatkozz — **SOHA ne illeszd be a tényleges hitelesítőket ebbe a fájlba.**
3. **Elérhető műveletek** — az általa nyújtott képességek felsorolása.
4. **Furcsaságok / ismert korlátok** — rate limit-ek, lapozás, ismert buktatók.
5. **Kapcsolódó procedúrák** — az ezt a connectort használó procedure fájlok elérési útjai.

## FONTOS — Biztonság

**Ez a fájl NEM tartalmazhat semmilyen hitelesítőt, tokent, API kulcsot vagy jelszót.**
Hivatkozz `.env` kulcsnevekre (pl. `GMAIL_CLIENT_ID`), de soha ne az értékeikre.
A hitelesítők kizárólag `.env`-ben tárolódnak (gitignored).

## Fájlnév

`agy/connectors/<name>.md`

## Példa

```yaml
---
type: connector
name: gmail
status: configured
auth_location: .env
tags: [email, google]
---
```

**Mihez kapcsolódik:** Gmail — a tulaj fiókjának olvasása és email küldése.

**Hitelesítés + beállítás:** OAuth2 service account. Kulcsok: `GMAIL_CLIENT_ID`,
`GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` a `.env`-ben. Frissítés:
`scripts/get-token.sh`.

**Elérhető műveletek:**
- Postaláda keresése lekérdezési szöveg alapján
- Szál olvasása azonosító alapján
- Email piszkozat küldése

**Furcsaságok / ismert korlátok:** 250 kvótaegység/másodperc; sok szál esetén kötegeld.

**Kapcsolódó procedúrák:** `agy/procedures/morning-email-triage.md`
