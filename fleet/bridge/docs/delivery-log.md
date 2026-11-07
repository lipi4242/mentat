# Kézbesítési napló (2.0)

A Telegram egy bot saját üzeneteit **soha** nem adja vissza a `getUpdates`-ből.
Arra, hogy egy válasz tényleg kiment-e, ezért csak a saját naplónk felel. Ez a
lap a napló szerződése: a séma, a sorrend, és hogyan kell olvasni.

A napló az 1.x-es koordinációs napló helyére lépett (a migráció:
`CHANGELOG.md`, 2.0.0). A több példányos koordináció és a szobák megszűntek. Ágensek a natív Claude Code csatornán beszélnek egymással
(`ListAgents` / `SendMessage`), nem a hídon át.

## Fájl és helye

```
${BRIDGE_INBOX_DIR}/delivery-YYYY-MM-DD.jsonl
```

- `BRIDGE_INBOX_DIR`, ha nincs: `${BRIDGE_STATE_DIR}/telegram-inbox`, ha az sincs
  (csak a `send.mjs`-nél és a `delivery.mjs`-nél): a telepítési helyből
  származtatva, `<state>/sub-etha/send.mjs` → `<state>/telegram-inbox`.
- Ágensenként egy könyvtár, naponta egy fájl, **UTC** nap szerint (ugyanaz a
  szabály, mint az `events-*.jsonl`-nél). A retention ugyanaz:
  `BRIDGE_RETENTION_DAYS`, alap 14 nap.
- Írók: a híd (`inbound`, `notice`) és minden `send.mjs`-hívás (`intent`, `outcome`, `notice`).
  Minden sor egyetlen `appendFileSync` (O_APPEND), legfeljebb 4 KB, így több
  egyidejű író mellett is egész sorok kerülnek a fájlba.

## Sortípusok

Közös mezők minden sorban:

| Mező | Jelentés |
|---|---|
| `v` | Sémaverzió, most `1`. |
| `id` | Egyedi sor-azonosító, `<ts>-<pid>-<seq>`. Az `intent` sornál ez a küldés azonosítója. |
| `ts` | Epoch ms. |
| `type` | `inbound` \| `intent` \| `outcome` \| `notice`. |
| `chat_id` | String. |

### `inbound` — bejövő üzenet (a híd írja)

Csak a kapun átjutott, **sikeresen kézbesített vagy sorba állított** üzenet
kerül ide (allowlist- vagy mention-kapun elutasított nem).

| Mező | Jelentés |
|---|---|
| `msg_id` | A Telegram `message_id`. Reakciónál `null`. |
| `kind` | `message` \| `edited` \| `media` \| `reaction`. |
| `from`, `from_id` | A küldő (sanitize-olt név, user id). |
| `reply_to` | Ha a bejövő egy korábbi üzenetre válaszolt (opcionális). |
| `target_msg_id` | Reakciónál: melyik üzenetre jött. |
| `text` | Sanitize-olt szöveg. Médiánál a felirat + ` [media]`, fájl-út nélkül. |

### `intent` — küldési szándék (a `send.mjs` írja, a Telegram-hívás ELŐTT)

| Mező | Jelentés |
|---|---|
| `action` | `message` \| `reaction`. |
| `reply_to` | `--reply-to`: a bejövő `msg_id`, amire válaszol. **Ez köti össze a választ a bejövővel.** |
| `target_msg_id` | Reakciónál `--message`. |
| `media` | `photo` — képküldésnél (`send.mjs --photo`); a `text` a caption, vagy `[kep <fájlnév>]`, ha nincs (opcionális). |
| `part` | Darabolt küldésnél a darab: `"k/n"` (opcionális). Csak az első darab viszi a `reply_to`-t. |
| `text` | A kiküldendő szöveg (a 4096-os vágás után), reakciónál az emoji. |

### `outcome` — a hívás kimenete (a `send.mjs` írja, a hívás UTÁN)

| Mező | Jelentés |
|---|---|
| `send_id` | Az `intent` sor `id`-je. |
| `status` | `confirmed` \| `failed` \| `unknown`. |
| `message_id` | A Telegram adta azonosító, ha `confirmed` és üzenet volt. |
| `error` | `failed` / `unknown` oka. |

- **`confirmed`** — a Telegram `ok: true`-val válaszolt. Kiment.
- **`failed`** — a Telegram `ok: false`-szal elutasította, vagy a kapcsolat fel
  sem épült (DNS, connection refused). Biztosan nem ment ki.
- **`unknown`** — a kérés elindult, de válasz nem jött (timeout, kapcsolat-
  bontás, nem-JSON válasz). Lehet, hogy kiment.

### `notice` — esemény (a `lib/notice.mjs` írja)

Nem küldés és nem bejövő üzenet: olyan esemény, amiről a naplóban nyomnak kell
maradnia. Az olvasó (`resolveSends`, `summarize`) figyelmen kívül hagyja. Az
írása sosem dob, a fő folyamot nem állíthatja meg.

| Mező | Jelentés |
|---|---|
| `event` | Kötelező. Az esemény neve (lásd alább). |
| `detail` | Opcionális részlet, pl. a kapcsoló neve. |
| `part` | Opcionális: több részes küldésnél a rész sorszáma. |
| `target` | Opcionális: a `webhook_*` eseménynél a nevesített webhook-cél neve (`SUBETHA_WEBHOOKS`). A `default` célnál (`SUBETHA_REPLY_WEBHOOK`) nincs ilyen mező. |

Eseménynevek:

- `deprecated_flag` — elavult kapcsolót kapott a `send.mjs` (pl. `--instance`);
  `detail` = a kapcsoló. A küldés megy tovább, a kapcsoló hatástalan.
- `webhook_failed` — a webhook-hívás nem sikerült (408, 429, 5xx vagy hálózati
  hiba, az utolsó újrapróba után); `chat_id`, `msg_id`, `detail`.
- `webhook_ok` — a szerver 2xx-szel nyugtázta; `detail:"HTTP <státusz>"`,
  `chat_id`, `msg_id`.
- `webhook_rejected` — a szerver véglegesen elutasította (4xx, a 408 és 429
  kivételével), nincs újrapróba; `detail:"HTTP <státusz>"`, `chat_id`, `msg_id`.
- `webhook_skipped` — a cél nem hívott: egy korábbi cél válasza kizárta
  (`detail:"unless <cél>:<kulcs>=<érték>"`), a szülő cél kimenete ismeretlen
  (`detail:"unless <cél>: a szulo kimenete ismeretlen"`, fail-closed), vagy lábléc nélküli válasz volt
  (`detail:"nofooter: visszakerdez"` / `"nofooter: nema"`); `chat_id`, `msg_id`, `target`.
  A szálba írt válasz maga `intent`/`outcome` párként kerül a naplóba (`reply_to` = a kiváltó üzenet).
- `inbound_confirmed` — a bejövő üzenet megjelent az ágens transzkriptjében
  (érkezés-nyugta, `docs/config.md` 3.2); `chat_id`, `msg_id`.
- `inbound_unconfirmed` — a bejövő üzenet egy újrainjektálás után sem jelent
  meg a transzkriptben; `chat_id`, `msg_id`; `detail:"no transcript"`, ha a
  transzkript nem volt meg, `detail:"stale"`, ha az ellenőrzés rég lejárt
  (ilyenkor újrainjektálás sincs). Mellé a híd riaszt, és — a `no transcript`
  kivételével — 😨 reakciót tesz az üzenetre (a ⚠️ nem engedett Telegram-reakció).

## A sorrend és az, amit garantál

1. `intent` sor a lemezre.
2. Telegram-hívás.
3. `outcome` sor.

Ha a `send.mjs` a 2. lépés közben hal meg (SIGKILL, OOM, a box újraindul), az
`intent` sor kimenet nélkül marad. **Az olvasó ezt `unknown`-nak veszi**, nem
hiánynak: egy elindított küldés így sosem tűnik el a naplóból.

Ha a szándék-sort nem lehet kiírni (tele a lemez, ismeretlen könyvtár), a
küldés **akkor is megy**: egy napló miatt nem maradhat el egy válasz. Ilyenkor
a `send.mjs` hangosan, `3`-as kóddal áll meg (lásd `protocol.md` §2).

## Olvasás

- **Megválaszolt** egy bejövő, ha van hozzá `action: "message"` küldés
  ugyanabban a chatben, `reply_to` = a bejövő `msg_id`-je, és a státusza
  `confirmed`. Ezért a válasz **mindig `--reply-to`-val megy**.
- A darabolt küldés (`part` `1/n` … `n/n`, ugyanabból a `send.mjs`-folyamatból)
  **egy** válasz: a státusza az első nem-`confirmed` darabé, különben
  `confirmed`; ha a naplózott darabok mind `confirmed`-ek, de kevesebb van
  belőlük `n`-nél, `failed`. A részben kiment válasz tehát nem zárja le a bejövőt.
- A notice-okat az olvasó eseményenként számolja (`notices`), küldésnek nem számítanak.
- A reakció nyugta, nem válasz. A bejövő reakció nem kérdés.
- Egy szerkesztett üzenet (`edited`) ugyanaz az üzenet, mint az eredeti
  (`msg_id` azonos).

A kész olvasó: `lib/delivery-log.mjs` (`readDay`, `resolveSends`,
`summarize`), és a parancssorból:

```
node ~/.config/<ágens>/sub-etha/delivery.mjs [--day YYYY-MM-DD] [--json]
```

Kiírja a napi bejövők számát, a küldéseket (válaszonként) státusz szerint, a
notice-okat eseményenként (`notice: inbound_unconfirmed 2, webhook_failed 1, …`), a
megválaszolatlan bejövőket és a bizonytalan (`unknown`) küldéseket. Kilépési
kód: `0` rendben, `2` van megválaszolatlan vagy `unknown`, `1` használati hiba.

## Példa

```json
{"v":1,"id":"1792...-811-0","ts":1792000000000,"type":"inbound","chat_id":"-100","msg_id":7,"kind":"message","from":"J","from_id":"1","text":"mehet?"}
{"v":1,"id":"1792...-902-0","ts":1792000004000,"type":"intent","chat_id":"-100","action":"message","reply_to":7,"text":"igen, indítom"}
{"v":1,"id":"1792...-902-1","ts":1792000004300,"type":"outcome","chat_id":"-100","send_id":"1792...-902-0","status":"confirmed","message_id":812}
```
