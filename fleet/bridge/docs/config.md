# Konfiguráció

A híd (`bridge.mjs`) minden beállítást env-ből olvas (`lib/config.mjs`).
A kimenő CLI (`send.mjs`) csak `TELEGRAM_BOT_TOKEN`-t igényel — lásd a lap
alján.

## Kötelező

Hiányzó vagy üres érték bármelyikből **FATÁLIS induláskor** — a híd
`process.exit(1)`-gyel áll le, mielőtt bármit is pollozna. Ez szándékos: egy
rossz agent alá indított híd rossz botot pollozna és rossz tmux sessionbe
injektálna.

| Env | Jelentés |
|---|---|
| `TELEGRAM_BOT_TOKEN` | A Telegram Bot API tokenje (getUpdates/sendMessage/getFile ehhez a bothoz kötve). |
| `TELEGRAM_GROUP_CHAT_ID` | A dedikált csoport chat ID-ja — innen jön be minden csoport-üzenet, ide megy a `selfAlert`. |
| `TELEGRAM_ALLOWLIST_IDS` | Vesszővel elválasztott user ID lista — DM-ben csak ezekről a userekről fogad el üzenetet. |
| `TMUX_SESSION` | A tmux session neve, ahova a híd a `tmux send-keys`-szel injektál. |
| `BRIDGE_STATE_DIR` | Alap könyvtár az állapotfájlokhoz (offset, pending, health, media-queue) — az opcionális útvonal-envek ebből származtatják a defaultjukat. |

## Opcionális

Minden alábbi env-nek van defaultja; hiányuk nem fatális.

| Env | Default | Jelentés |
|---|---|---|
| `BRIDGE_OFFSET_FILE` | `${BRIDGE_STATE_DIR}/telegram-state/bridge-offset.json` | Az utolsó feldolgozott `update_id` + 1. |
| `BRIDGE_PENDING_FILE` | `${BRIDGE_STATE_DIR}/telegram-state/bridge-pending.json` | A kézbesítetlen (tmux inject sikertelen) sorok lemezes sora. |
| `BRIDGE_INBOX_DIR` | `${BRIDGE_STATE_DIR}/telegram-inbox` | Letöltött média, esemény-napló (`events-YYYY-MM-DD.jsonl`) és kézbesítési napló (`delivery-YYYY-MM-DD.jsonl`, lásd `docs/delivery-log.md`) helye. |
| `BRIDGE_HEALTH_FILE` | `${BRIDGE_STATE_DIR}/telegram-state/health.json` | Életjel-fájl — lásd `docs/protocol.md` §4. |
| `BRIDGE_MEDIA_QUEUE_FILE` | `${BRIDGE_STATE_DIR}/telegram-state/media-queue.json` | Tartós média letöltési sor (`lib/mediaqueue.mjs`). |
| `BRIDGE_MAX_FILE_BYTES` | `12 * 1024 * 1024` (12 MB) | Egy letöltött fájl mérethatára — fölötte `tooBig` hibaüzenet megy a csoportnak, nem próbál letölteni. |
| `BRIDGE_RETENTION_DAYS` | `14` | Hány napig marad meg egy inbox-fájl, mielőtt a periodikus takarítás törli. |
| `BRIDGE_ALBUM_DEBOUNCE_MS` | `2500` | Album (media_group) puffer-ablak — ennyi ideig vár új album-részre, mielőtt egyetlen sorba fogva kiküldi. |
| `BRIDGE_PENDING_RETRY_MS` | `30000` | Milyen gyakran próbálja újra a pending-sort injektálni. |
| `BRIDGE_PENDING_ALERT_MS` | `600000` (10 perc) | Ennyi kézbesítetlenség után szól a híd a csoportnak (`selfAlert`). |
| `BRIDGE_CONFLICT_ALERT_MS` | `900000` (15 perc) | Ennyi folyamatos 409 után szól a híd, hogy másik poller fogja a tokent. |
| `BRIDGE_MAX_PENDING` | `500` | A pending-sor mélység-sapkája — a legrégebbi sorok esnek ki fölötte (`lib/pending.mjs`). |
| `BRIDGE_REQUIRE_MENTION` | `true` | Csoportban `false`-ra állítva minden üzenet bemegy; `true` esetén csak `@botnév`-es vagy a bot üzenetére adott reply. |
| `BRIDGE_STARTUP_BACKLOG` | `skip` | `skip`\|`process` — induláskor a régi (backlog) update-eket átugorja vagy feldolgozza. Bármi más érték fatális. |
| `BRIDGE_AGENT_LABEL` | `${TMUX_SESSION}` | A `selfAlert` üzenetek felirata — melyik telepített híd szól, több híd esetén ne mindig ugyanaz a név szerepeljen. |
| `BRIDGE_LOCK_DIR` | `$HOME/.config/sub-etha-locks` (felhasználónként közös, NEM a state-ből származtatva: különböző szülőjű state-ek ugyanarra a tokenre is ütköznek; az `XDG_RUNTIME_DIR`-től független, így a systemd alatti és a kézi/cron futás ugyanazt a zárat látja) | A tokenenkénti zár helye (`tg-<sha256(token)[:12]>.lock`, 0700/0600). Egy tokenre EGY poller: a második híd `75`-ös kóddal, `token-zár foglalt` hibasorral áll le, mielőtt Telegramot hívna. Sérült zárat a híd nem töröl — a hibasor megnevezi a kézzel törlendő fájlt. |
| `BRIDGE_LOCK_CHECK_MS` | `30000` (nem-szám vagy `1000` alatti érték esetén is) | A tulajdonos-önellenőrzés periódusa: ha a zárfájlban már nem a híd saját nonce-a áll (kézzel törölték vagy átvették), `token-zár elveszett` hibasorral `75`-tel leáll. |
| `SUBETHA_PHOTO_TIMEOUT_MS` | `60000` | A `sendPhoto` (kép-feltöltés) időkorlátja; lejárta után a kimenet `unknown` (exit 5). |
| `SUBETHA_TELEGRAM_API` | `https://api.telegram.org` | Csak tesztnek: helyi hamis Telegram címe (ugyanaz, mint a send.mjs-nél). |
| `BRIDGE_WEBHOOK_QUEUE_FILE` | `${BRIDGE_STATE_DIR}/telegram-state/webhook-queue.json` | A jóváhagyó webhook tartós sora (lásd lent). |

## Jóváhagyó webhook (3.1)

| Env | Jelentés |
|---|---|
| `SUBETHA_REPLY_WEBHOOK` | A cél-URL. Csak `https://` engedett. Üresen a webhook csendesen KI. |
| `SUBETHA_REPLY_WEBHOOK_TOKEN` | Az `X-Bridge-Token` fejléc értéke. URL mellett kötelező. |

Hibás beállítás (nem `https://`, érvénytelen URL, hiányzó token) **nem
fatális**: a híd induláskor egy `[bridge] WEBHOOK KI: <ok>` sort ír a
stderr-re, a health-be `webhook: "off"` kerül, és fut tovább. Az ok sosem
tartalmazza a tokent vagy az URL-t. Bekapcsolva az indulási sorba csak
`webhook=on host=<host>` kerül.

**Ki megy ki:** minden `reply_to`-s, nem szerkesztett szöveges üzenet, ami a
bejövő kapun átjutott (saját csoport vagy allowlistes DM, bot soha, a
mention-kapuval együtt). A jogosultságot a szerver dönti el a `tg_from_id`
alapján. A beinjektálás ettől független, és előbb történik.

**Törzs** (`content-type: application/json`, fejléc `X-Bridge-Token`):
`event_id` (`"<chat_id>:<message_id>"`), `tg_from_id`, `tg_chat_id`,
`tg_message_id`, `tg_reply_to`, `tg_date`, `text`.

**Küldés:** egy POST a beállított hostra, átirányítást nem követ (3xx = hiba),
a tanúsítványt mindig ellenőrzi, 5 s időkorláttal (socket-idle és fali óra is —
a lassan csepegő válaszra is). Hiba után 10 s, 60 s, 300 s múlva újrapróbál
(összesen 4 próba); utána az elem kiesik a sorból, és egy `notice` sor marad
`event:"webhook_failed"`-del a kézbesítési naplóban. Ez csak a 408-ra, a 429-re,
az 5xx-re és a hálózati hibára igaz: más 4xx végleges (nincs újrapróba,
`webhook_rejected`), a 2xx pedig `webhook_ok` sort ír (`detail:"HTTP <státusz>"`).
Így egy próba látja, hogy a szerver megkapta és válaszolt.

**Tartósság:** az enqueue szinkron, szigorúan íródik a sorfájlba. Ha ez nem
sikerül, a feldolgozás dob, és az offset nem lép — a következő getUpdates
ugyanazt hozza (a beinjektálás így kétszer is megtörténhet). A sor újraindítás
után folytatódik. A sorfájlban a törzs van, a token nincs.

**Idempotencia a SZERVER dolga:** az `event_id`-n deduplikáljon. A helyi
`done`-halmaz (az utolsó 500 `event_id`) csak a fölösleges forgalmat
csökkenti, garanciát nem ad.

## Több nevesített webhook-cél

A fenti `SUBETHA_REPLY_WEBHOOK` a **`default`** nevű cél, változatlan
viselkedéssel. Mellé (vagy helyette) tetszőleges számú nevesített cél adható:

| Env | Default | Jelentés |
|---|---|---|
| `SUBETHA_WEBHOOKS` | — | Célnevek vesszővel (`[a-z][a-z0-9_]*`, a `default` foglalt). A sorrend a kiértékelés sorrendje. |
| `SUBETHA_WEBHOOK_<NÉV>_URL` | — | Kötelező, csak `https://`, átirányítás nélkül. |
| `SUBETHA_WEBHOOK_<NÉV>_TOKEN` | — | Kötelező. |
| `…_TOKEN_HEADER` | `X-Bridge-Token` | A token fejlécének neve. |
| `…_MATCH` | `reply` | `reply`, `reaction`, `footer`, vesszővel kombinálható. |
| `…_FROM` | mind | Csak ezektől a küldőktől (id-lista). Zajszűrő, nem jogosultság: azt a szerver dönti el. |
| `…_FOOTER` | — | `footer`-hez kötelező: regex **egy** capture-csoporttal, a válaszolt **bot-üzenet** utolsó nem-üres sorára. Az id URL-dekódolva kerül a törzsbe. |
| `…_FOOTER_ALL` | — | Regex: a válaszolt szöveg minden találata ugyanarra az id-re mutasson, különben nincs kötés. |
| `…_FOOTER_FIELD` | `ref` | A törzsmező neve a kinyert id-nek (a törzsben a `tg_date` és a `text` között). |
| `…_FOOTER_EXCLUDE` | — | Vesszős lista: ezek az id-k (URL-dekódolás UTÁN, a `_FOOTER` és a `_FOOTER_ALL` találataira is) nem kötnek, pl. egy listaoldal. |
| `…_REPLY` | — | A válasz-JSON mezője, ami a szálba kimegy (reply a kiváltó üzenetre, reakciónál a reagáltra). |
| `…_REPLY_SKIP` | — | `kulcs=érték[,…]`: ha a válasz-JSON-ban így áll, a szál néma. |
| `…_UNLESS` | — | `<korábbi cél>:kulcs=érték`: megvárja annak a célnak a végső kimenetét ugyanarra az eseményre; ha a válaszában így áll, ez a cél nem hív. A döntés a szülő sorfájljában őrzött kimenetből jön (újrajátszás után is); ha a szülő kész, de a kimenete ismeretlen, a cél nem hív (fail-closed, `webhook_skipped`). Egy szülőnek legfeljebb **egy** függője lehet; a másodikat a híd KI-re állítja. |
| `…_NOFOOTER_REPLY` | — | `footer`-célnál: ha a bot üzenetére adott válaszban nincs (egyértelmű) lábléc, ez az egy sor megy a szálba, POST nélkül. |
| `…_NOFOOTER_FILTER` | — | Egy `.mjs` útja; a default exportja `(text) => boolean` dönti el, kell-e a `NOFOOTER_REPLY`. Hiba vagy hiányzó modul: néma (fail-closed). |
| `…_TIMEOUT_MS` | `5000` | Kérésenkénti időkorlát. |
| `…_EVENT_ID` | `on` | `off`: a küldött törzsből kimarad az `event_id` (a helyi sor kulcsa megmarad). |
| `…_REPLY_TO` | `off` | `on`: a `footer`-törzs is viszi a `tg_reply_to`-t (a válaszolt bot-üzenet id-je), hogy a szerver megtalálja a horgonyt (pl. zárt opciós válasznál). `off`: a törzs bájtra a régi. |
| `…_TEXT` | `raw` | `oneline:<N>`: a `text` egy sorba vonva (vezérlő → szóköz, bidi/zero-width le, whitespace összevonva), `N` karakternél vágva. |

Hibás cél **nem fatális**: `[bridge] WEBHOOK KI (<név>): <ok>` a stderr-re, a
többi cél és a híd fut. Bekapcsolva az indulási sorba
`webhook=on targets=<név>@<host>,…` kerül (csak a `default`-tal a régi alak).

**Törzsek.** `reply`: a 3.1-es törzs. `reaction`: `event_id`
(`"<chat>:<msg>:r<from>:<date>"`), `tg_from_id`, `tg_chat_id`, `tg_message_id`
= `tg_reply_to` = a reagált üzenet, `tg_date`, `text` (az új emojik szóközzel).
`footer`: `event_id`, `tg_from_id`, `tg_chat_id`, `tg_message_id`, `tg_date`,
`text` és `<FOOTER_FIELD>`; `tg_reply_to` csak `…_REPLY_TO=on` mellett (a
`tg_message_id` után).

**Sor és újrapróba** célonként külön: tartós sorfájl
(`webhook-queue-<név>.json` a `BRIDGE_WEBHOOK_QUEUE_FILE` mellett), 10/60/300 s,
`webhook_ok|rejected|failed|skipped` notice `target` mezővel.

**Szálba írt válasz.** A `_REPLY` szövege 2xx-re és végleges 4xx-re megy ki
(újrapróbálható hibánál nem; 64 KB fölötti válasz-törzset a híd nem olvas be).
Ha egy `_UNLESS`-es cél vár ugyanarra az eseményre, a két szöveg **egy**
üzenetben, sortöréssel fűzve megy ki: egy `_UNLESS`-lánc egy eseményre legfeljebb
egy üzenetet ír. Egymástól független, `_REPLY`-os célok külön-külön válaszolhatnak. Újraküldés
nincs (a duplikált válasz rosszabb a hiányzónál); a küldés `intent`/`outcome`
sorként a kézbesítési naplóban van.

### Recept: jóváhagyás és ügy-üzenet két célra (a fork kiváltása)

A teljes env-készlet; a törzs és a fejléc betűre egyezik a fork kéréseivel
(`test/webhook-paritas.test.mjs` ugyanezzel fut, a `TIMEOUT_MS` és a valódi értékek kivételével):

```
SUBETHA_WEBHOOKS=draft,ugy
SUBETHA_WEBHOOK_DRAFT_URL=https://<szerver>/api/telegram/draft-approve
SUBETHA_WEBHOOK_DRAFT_TOKEN=<híd-token>
SUBETHA_WEBHOOK_DRAFT_TOKEN_HEADER=X-Partner-Bridge-Token
SUBETHA_WEBHOOK_DRAFT_MATCH=reply,reaction
SUBETHA_WEBHOOK_DRAFT_REPLY=message
SUBETHA_WEBHOOK_DRAFT_REPLY_SKIP=reason=no_anchor
SUBETHA_WEBHOOK_DRAFT_EVENT_ID=off
SUBETHA_WEBHOOK_DRAFT_TEXT=oneline:1500
SUBETHA_WEBHOOK_DRAFT_TIMEOUT_MS=20000
SUBETHA_WEBHOOK_UGY_URL=https://<szerver>/api/telegram/case-message
SUBETHA_WEBHOOK_UGY_TOKEN=<híd-token>
SUBETHA_WEBHOOK_UGY_TOKEN_HEADER=X-Partner-Bridge-Token
SUBETHA_WEBHOOK_UGY_MATCH=footer
SUBETHA_WEBHOOK_UGY_FROM=<kijelölt küldő Telegram-id>
SUBETHA_WEBHOOK_UGY_FOOTER=^Ügy:\s+https?://\S*?/ugyek/([^\s/?#]+)/?$
SUBETHA_WEBHOOK_UGY_FOOTER_ALL=https?://\S*?/ugyek/([^\s/?#]+)
SUBETHA_WEBHOOK_UGY_FOOTER_FIELD=case_id
SUBETHA_WEBHOOK_UGY_FOOTER_EXCLUDE=tipus
SUBETHA_WEBHOOK_UGY_UNLESS=draft:ok=true
SUBETHA_WEBHOOK_UGY_REPLY=message
SUBETHA_WEBHOOK_UGY_REPLY_SKIP=ok=true
SUBETHA_WEBHOOK_UGY_EVENT_ID=off
SUBETHA_WEBHOOK_UGY_TEXT=oneline:1500
SUBETHA_WEBHOOK_UGY_TIMEOUT_MS=20000
SUBETHA_WEBHOOK_UGY_NOFOOTER_REPLY=<egysoros visszakérdezés, a fork MELYIK_UGYRE szövege>
SUBETHA_WEBHOOK_UGY_NOFOOTER_FILTER=<út egy .mjs-hez: export default (t) => keresnek_latszik(t, { javithatoDraft: true })>
```

A `SUBETHA_WEBHOOK_UGY_FROM` a receptben **kötelező**: a fork alapból csak a
kijelölt küldő (Anna) üzenetét vitte az ügyre, `_FROM` nélkül bárki
válasza felkerülne. A `\s` a `_FOOTER`-ben szó szerint kell, hogy megérkezzen (systemd
EnvironmentFile alatt ellenőrizd). **Maradó eltérés a forktól:** hiba után 4
próba (10/60/300 s) a fork 1 próbája helyett (az ügy-cél ilyenkor a draft
végső kimenetét várja), és 5xx-nél a szál néma (a fork kitette a JSON `message`-ét).

## Érkezés-nyugta (3.2)

Ágensenként kapcsolható (a `BRIDGE_REPLY_HINT` mintájára); kapcsoló nélkül a
híd viselkedése változatlan, és `receipts.json` sem jön létre.

| Env | Default | Jelentés |
|---|---|---|
| `BRIDGE_RECEIPT` | ki | Csak `1` kapcsolja be. |
| `BRIDGE_SESSION_ID_FILE` | `${BRIDGE_STATE_DIR}/session.id` | Az ágens aktuális Claude-session azonosítója (egy sor). |
| `BRIDGE_TRANSCRIPT_ROOT` | `$HOME/.claude/projects` | A transzkript itt: `<root>/*/<session-id>.jsonl`. |

Az állapot a `${BRIDGE_STATE_DIR}/telegram-state/receipts.json`-ban van, és
újraindítás után folytatódik.

**Mit csinál:** minden `msg=`-es beinjektált sorhoz (szöveg, média; reakció
nem) az injektálás ELŐTT megméri a transzkript hosszát, és 2 percen belül
keres utána egy `user` bejegyzést — vagy, ha az ágens épp dolgozott, egy
`queued_command` csatolmányt (`{"type":"attachment","attachment":{"type":"queued_command","prompt":…}}`) —,
amelynek szövegében a sor fejléce
(`[Telegram inbound | … id=<uid> | chat=<chat> | msg=<msg>`) a szöveg ELEJÉN pontosan
szerepel (`msg=12` nem egyezik `msg=123`-mal; a névben lehet `]`, és a névben álló
`| chat=… | msg=…` sem ad hamis egyezést, mert a minta az `id=<szám> | chat=` részhez horgonyoz). Csak teljes (`\n`-nel lezárt) sorok
számítanak; ha a fájl rövidebb lett a mért hossznál, vagy kicserélték (más
`dev`/`ino`, akár nagyobb méretben), elölről keres — de legfeljebb a fájl
utolsó 8 MB-jától (a sorhatárig előre lépve).
Session-váltásnál (és később megjelenő transzkriptnél) az újat ugyanígy, a
vége előtti 8 MB-tól (kis fájlnál az elejétől), a régit a régi helytől nézi
tovább. Az olvasás rögzített 1 MB-os ablakokban megy, így a több száz MB-os
transzkript sem fér ki a `MemoryMax=96M` unitból; az 1 MB-nál hosszabb sort
(pl. beágyazott kép) átugorja — Telegram-sor sosem ekkora. A pending-sorból később kézbesített sor a kézbesítéskor rögzül.

- Megjelent → `inbound_confirmed` notice a kézbesítési naplóban.
- 2 perc után sincs → **egy** újrainjektálás ugyanazzal a sorral; a késve
  megjelenő első is nyugtának számít.
- Még 2 perc után sincs → `inbound_unconfirmed` notice, riasztás a csoportnak
  és 😨 reakció az üzenetre, egyszer. (Nem ⚠️: az nincs a Telegram engedett
  reakció-emojijai között, a `setMessageReaction` elutasítaná.)
- A transzkript nem található → nincs újrainjektálás, `inbound_unconfirmed`
  `detail:"no transcript"`; folyamatonként legfeljebb EGY riasztás, reakció nincs
  (beállítási hiba, nem üzenetvesztés).
- Rég lejárt ellenőrzés (a határidő után több mint 2 ablaknyi idő, pl. a híd
  sokáig állt) → nincs újrainjektálás, `inbound_unconfirmed` `detail:"stale"` soronként; a csoport egy ellenőrzési körön belül EGY összesítő riasztást kap
  („N üzenet ellenőrizetlen maradt a híd kiesése alatt: msg=…”), reakció nélkül.
- A lezárt `chat:msg` kulcsokat (utolsó 500) a híd megjegyzi: a később
  kézbesített újrainjektálás vagy egy szerkesztett üzenet (ugyanaz a fejléc)
  nem indít új kört.

Az ellenőrzés 15 másodpercenként fut; útvonalanként egyszer olvas, és csak a
még át nem nézett bájtokat.

## send.mjs

A kimenő CLI-nek a `TELEGRAM_BOT_TOKEN` kötelező. A kézbesítési napló helyét
ugyanígy dönti el, mint a híd: `BRIDGE_INBOX_DIR`, majd
`${BRIDGE_STATE_DIR}/telegram-inbox`, végül a telepítési hely
(`<state>/sub-etha/send.mjs` → `<state>/telegram-inbox`). Ha egyik sem
állapítható meg, a küldés megy, de `3`-as kóddal jelzi, hogy nyoma nem maradt.

| Env | Default | Jelentés |
|---|---|---|
| `SUBETHA_SEND_TIMEOUT_MS` | `20000` | A Telegram-hívás időkorlátja; lejárta után a kimenet `unknown` (exit 5). |
| `SUBETHA_TELEGRAM_API` | `https://api.telegram.org` | Csak tesztnek: helyi hamis Telegram címe. |
| `SUBETHA_LENGTH_GATE` | ki | Hosszúság-kapu (H6). Bármilyen nem üres érték bekapcsolja: a határ fölötti üzenet (képnél a caption) `--why "<indok>"` nélkül exit `4`-gyel elutasított, semmi nem megy ki. |
| `SUBETHA_MAX_CHARS` | `900` | A kapu határa; érvénytelen érték esetén a default él, a kapu sosem nyílik ki csendben. |

**H6 — a kapu bekapcsolása ágensenként.** A kapu NEM globális: az ágens saját
env-fájljában kell beállítani (`SUBETHA_LENGTH_GATE=1`), a migráció 2.
lépésében, és CSAK az ágens-szabály (prompt) `--why`-ra vonatkozó
frissítése UTÁN. Fordított sorrendben az ágens olyan elutasítást kapna, amiről
a szabálya nem tud, és a válasz elveszne. A kapu nem vág és nem ír át; az
átengedett hosszú üzenet indoka naplózódik (lásd `docs/delivery-log.md`).
