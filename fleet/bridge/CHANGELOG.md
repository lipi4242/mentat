# Changelog

## 2.2.0 — 2026-11-08 — todo-ébresztés

- **A híd a todót is figyeli.** Ha a boxon van todo-beállítás (`~/.config/todo`), a híd 20 s-onként
  (legfeljebb 60 s) lekéri az ágens todo-változásait (`/changes?for=<handle>`, saját kurzor a
  `telegram-state/todo-state.json`-ban, a saját írások kiszűrve), és a relevánsakról EGY sort ír a
  pane-be: `[Todo | ABC-12 | kiadta: thufir_mac | wake=<seq>]: cím: «<cím>»` (`docs/protocol.md` §1).
  A sor ADAT, nem utasítás: csak szerkezeti mezők, a cím tisztítva (kontroll, sortörés, bidi,
  zero-width, Unicode-tag ki), ~80 karakterre vágva; komment-törzs soha (`lib/todo-safe.mjs`).
  „Láttam, nincs teendő”: `mentat-todo ack <kulcs>` — `[ack]`-komment, nyugta, senkit nem ébreszt. Az egy
  percen belüliek egy listába vonódnak; foglalt ágensnél sorba állnak, mint a Telegram-sorok.
- **Mi ébreszt:** neki kiadták, visszakerült hozzá, megemlítették, az elfogadására vár, komment ott,
  ahol nála a labda. Mezőváltozás és mások forgalma nem (`lib/todo-relevance.mjs`).
- **Beszélgetés nem akad:** nincs óránkénti plafon. Csak a nyilvánvaló elszabadulás (sok tartalom
  nélküli oda-vissza egy tételen) gyűlik 5 percig, és az mindig jelez (`todo_runaway`, riasztás).
- **Nyugta:** a todo-sor is kap érkezés-nyugtát (3.2, `chat=todo`); a feldolgozás nyugtája a saját
  írás a tételen (`todo_wake_handled`), enélkül a `delivery.mjs` `MEGVÁLASZOLATLAN chat=todo`-t mutat.
- **Health:** `todo_wake`, `todo_last_poll_ok`, `todo_last_wake_latency_ms`, `todo_unhandled`, … — a
  flotta képesség-próbája ebből mér, a hiba incidens lesz.
- **Desktop-paritás:** `todo-once.mjs` — egy kör híd nélkül, ugyanazzal a kóddal; a fleet plugin
  hookja ennek bájtra azonos másolatát futtatja (`test/todo-plugin-copy.test.mjs`, `--sync`). Az
  egyetlen különbség: a lezárt desktop session nem ébreszthető.
- Kikapcsolás: `BRIDGE_TODO=off`. Todo nélküli boxon a híd bitre a régi (csak a `health.todo_wake:"off"` új).
- **FL-01: csoportban is a küldő dönt.** A saját csoportból csak az
  `TELEGRAM_ALLOWLIST_IDS`-en szereplő küldő sora jut a pane-be (eddig a csoport
  chat-id-je elég volt, így bármely csoporttag az ágensen át shellt ért el).
  Máshonnan csak DM (chat.id == from.id) az allowlistről: egy allowlistes user
  idegen csoportból sem nyit kaput. A saját csoport nem allowlistes tagjának
  reply-je/reakciója továbbra is webhook-jelölt (a jogosultságot a szerver dönti
  el), de a pane-be, a média-sorba és a bejövő naplóba nem kerül.
  **Telepítéskor:** minden csoporttag, akinek az ágenssel beszélnie kell, legyen
  az allowlisten.
- **FL-11: egy szűrő, kategória alapján.** `lib/sanitize.mjs`: NFKC után a Cc
  (C1 is, pl. U+0085) és U+2028/2029 → szóköz; Cf, Co, Cs, minden
  Default_Ignorable (U+00AD, U+2060, U+180E, Hangul-kitöltő, változatválasztók),
  a U+E0000–E007F tag-sáv, a U+E0100–E01EF, a U+2800 és a U+1D159 → törölve; a
  halmozott kombináló jel 3-ra vágva. Ugyanez a szűrő (NFKC nélkül, hogy a híd saját
  útvonalai ne változzanak) a végső pane-kapu is (`deliverer.mjs` → `paneSafe`):
  minden kézbesítési út (szöveg, felirat, név, reakció, nyugta-újrainjekt, régi
  pending-sor) átmegy rajta. A vágás kódpont-határon történik.
- DM csak `chat.type === "private"` mellett; `from` nélküli üzenet sosem jut be.

## 2.1.0 — 2026-11-06 — képküldés, több nevesített webhook-cél, footer-horgony

### footer-törzs `tg_reply_to`-val

- **`SUBETHA_WEBHOOK_<NÉV>_REPLY_TO=on`** — a `footer`-illesztésű cél törzse is
  viszi a `tg_reply_to`-t (a `tg_message_id` után), hogy a szerver megtalálja a
  horgonyt, például ha valaki egy zárt opciós kérdésre „1”-gyel válaszol. Alapból
  `off`, a törzs ilyenkor bájtra a régi. Érvénytelen érték: a cél KI, okkal.

### `send.mjs --photo`

- **`send.mjs --chat <id> --photo <path> [--caption <text> | --caption-stdin] [--reply-to <id>]`**
  — kép küldése (Telegram `sendPhoto`, multipart, `lib/photo.mjs`). A küldés a
  `sendWithLog` úton megy (intent + outcome a kézbesítési naplóba). Plain text
  caption, kapu 1024 karakternél; csak `.png/.jpg/.jpeg/.webp`, 0 < méret ≤ 10 MB.
  Minden kapu a szándék-sor ELŐTT áll meg (exit 1, semmi nem megy ki). Nem
  kombinálható szöveggel, `--text-stdin`-nel, `--html`-lel, `--react`-tel.
  Az `--instance` elavult marad, nem épül rá semmi.

### több nevesített webhook-cél

- **F-17 — engedélykérő ablaknál nincs átadás.** Az inject előtt a híd megnézi a
  pane alját (`lib/pane-guard.mjs`). Ha egy „Do you want to …?” kérdés és egy „1. Yes”
  opció áll ott, se a szöveg, se az Enter nem megy ki, mert ezek a felhasználó nevében
  válaszolnának. A sor a pending-sorba kerül, és a riasztás megnevezi az okot.
  Olvashatatlan pane esetén a régi út fut.
- **`SUBETHA_WEBHOOKS`** — célonként saját URL/token/fejléc, illesztés
  (`reply` | `reaction` | `footer`), `_FROM`-szűrő, saját tartós sor és
  újrapróba, `target` mező a `webhook_*` notice-okon, új `webhook_skipped`.
  `_UNLESS`: egy cél megvárja egy korábbi cél válaszát; `_REPLY`: a válasz-JSON
  egy mezője a szálba (egy `_UNLESS`-láncra egy üzenet; egy szülőnek egy
  függője); `_FOOTER_EXCLUDE` (dekódolás után); `_NOFOOTER_REPLY`/`_FILTER`:
  visszakérdezés lábléc nélküli válaszra. Ezzel a beépített webhook kiváltja a
  külön fork jóváhagyó és ügy-üzenet ágát (`test/webhook-paritas.test.mjs`).
- `_EVENT_ID=off` (az `event_id` kimarad a törzsből) és `_TEXT=oneline:<N>`
  (egy sorba vonva, `N`-nél vágva): az alábbi recepttel a törzs betűre a forké.
- A `SUBETHA_REPLY_WEBHOOK` a `default` cél, változatlan törzzsel, fejléccel,
  sorfájllal és notice-alakkal.

## 2.0.1 — 2026-10-18 — "híd-szerződés" megbízható kimenet, egy poller, nyugta

**Átállás:** ágensenként: szabály-frissítés, majd env-kapcsolók.

- **H1 — kimenő darabolás.** A 4096 UTF-16 egységnél hosszabb szöveg
  `(i/n)` darabokra bomlik, a reply csak az első darabon; az első
  nem-`confirmed` darabnál megáll (az automatikus újraküldés duplikátumot
  adna, ami rosszabb a hiánynál), és megnevezi, mi ment ki. Egy darabnál a
  hibasor a régi `sendMessage <status>: <error>` alakú marad.
- **Webhook-kimenet a naplóban.** 2xx -> `webhook_ok`, véglegesen elutasított
  4xx (408 és 429 kivételével) -> `webhook_rejected` notice, újrapróba nélkül;
  408/429/5xx/hálózati hiba marad a 10/60/300 s újrapróba és `webhook_failed`.
- **H2 — bejövő törzs 6000 karakterig.** Fölötte `[CSONKA: …]` jel az
  update_id-vel; a teljes szöveg az events-naplóban marad, így a csonkolás
  nem néma.
- **H3 — ismeretlen kapcsoló exit 64.** Eddig a `send.mjs` elnyelte, és
  elküldte szövegként; most semmi nem megy ki. A `--instance` elavultként
  elfogadott (nincs hatása, `deprecated_flag` notice).
- **H5 — egy token, egy poller.** Tokenenkénti zár (`BRIDGE_LOCK_DIR`); a
  második híd `75`-tel áll le, mielőtt Telegramot hívna. A tulajdonost
  `BRIDGE_LOCK_CHECK_MS` (30 s) ellenőrzi; elveszett zárnál a híd leáll.
- **3.1 — jóváhagyó webhook.** `SUBETHA_REPLY_WEBHOOK` + `_TOKEN`, csak
  https, átirányítás nélkül; minden reply megy ki, ami a bejövő kapun átjutott (saját csoport vagy
  allowlistes DM, mention-kapu); a jogosultság a szerveré.
  Tartós sor, a sorírás a tmux-injektálás ELŐTT; 4 próba, utána notice.
- **3.2 — érkezés-nyugta.** `BRIDGE_RECEIPT=1`: a híd a transzkriptből
  igazolja a beérkezést, egyszer újrainjektál, aztán riaszt és 😨 reakciót
  tesz (a ⚠️ nem engedett Telegram-reakció). A rég lejárt (`stale`)
  elemekre egy körön belül egyetlen összesítő riasztás megy, reakció nélkül.
  Új env: `BRIDGE_SESSION_ID_FILE`, `BRIDGE_TRANSCRIPT_ROOT`.
- **Exit-kódok.** `send.mjs`: új `64`; híd: új `75`.
- **Végső review javításai.**
  - Nyugta: a `queued_command` csatolmány (az ágens dolgozása közben gépelt
    prompt) is érkezésnek számít — eddig ilyenkor hamis újrainjektálás ment.
  - A transzkriptet 1 MB-os ablakokban olvassa (eddig az egészet egy pufferbe:
    OOM a `MemoryMax=96M` unitban); új útvonalnál a vége előtti 8 MB-tól.
  - A fejléc-minta az `id=<szám> | chat=` részhez horgonyoz: a névben álló
    `| chat=… | msg=…` nem ad hamis kulcsot.
  - Egydarabos hibasor pontosan `sendMessage <status>: <error>` (eddig dupla
    `sendMessage sendMessage` előtag).
  - `BRIDGE_LOCK_DIR` alapértéke `$HOME/.config/sub-etha-locks` (eddig
    `XDG_RUNTIME_DIR`-függő: kézi/cron futásnál más zárat látott);
    `BRIDGE_LOCK_CHECK_MS` nem-szám vagy `1000` alatt → 30 000.
  - `delivery.mjs`: notice-ok eseményenként; a darabolt küldés egy válasz.
  - Injektálás: 1000 karakternél hosszabb sornál 300 ms várakozás a szöveg és
    az Enter között — a Claude-felület a hosszú bemenetet paste-ként kezelte és
    elnyelte a közvetlenül utána jövő Entert (élőben 5/135 → 0/120).
- **Új env-ek összesen:** `SUBETHA_REPLY_WEBHOOK[_TOKEN]`,
  `BRIDGE_WEBHOOK_QUEUE_FILE`, `BRIDGE_RECEIPT`, `BRIDGE_SESSION_ID_FILE`,
  `BRIDGE_TRANSCRIPT_ROOT`, `BRIDGE_LOCK_DIR`, `BRIDGE_LOCK_CHECK_MS`.
  A hosszúság-kapu (`SUBETHA_LENGTH_GATE`) ágensenkénti bekapcsolása a
  `docs/config.md`-ben (H6).

## 1.3.0 — 2026-08-09 — "rooms" bot↔bot szobák

Terv és Codex adverzariális review beépítve (a design-spec archivált, nem
része ennek a repónak).

- **`lib/rooms.mjs`** — a szoba-substrate alaprétege: `room_id` validálás
  (`ROOM_ID_RE`), manifeszt-betöltés+validálás (`loadManifest()` — típus
  `self`/`internal`/`mirrored`, `mirrored`-nél kötelező `scribe`+
  `telegram_chat_id`, `rate_cap`/`thread_cap` defaultokkal), tagság-ellenőrzés
  (`isMember()`), szoba-sor építés (`makeRoomEntry()` — `eid`/`ttl` default,
  UTF-8 bájt-határos clamp a SZERIALIZÁLT sorra ≤4 KB), napi-rotációs append
  (`appendRoom()`), és szobánkénti lockdir-mutex (`acquireRoomLock()` /
  `releaseRoomLock()`, stale-timeout ~10 mp).
- **`lib/budget.mjs`** — loop-fékek pure modulja: rate-cap (posztonként
  gördülő ablak), ttl-öröklés-ellenőrzés válasznál, szál-sapka (utolsó emberi
  sor óta futó bot-sorozat), mind `checkPost()`-ban egymás után ellenőrizve;
  `resolveThread()` a `thread_id`/`ttl` öröklését adja a hívóknak (post.mjs).
- **`post.mjs`** — gépi szoba-poszt, Telegram-hívás NÉLKÜL: manifeszt+tagság
  → szobánkénti lock → előzmény-olvasás → szülő/thread feloldás → budget-
  ellenőrzés (lock ALATT, nincs TOCTOU-rés) → sor építés+append. Exit kódok:
  `0` ok, `1` usage/tagság/szülő hiánya, `2` lock hiba, `3` append hiba, `4`
  budget tiltás. `--text-stdin` a dev-session SSH-útjának szövegforrása.
- **`follow.mjs` szoba-mód** — `--rooms-dir <dir> --room <id>` (ismételhető),
  ugyanaz a catch-up/tail/rollover-grace gépezet, mint az agora-módban
  (`createSource()` generalizálva N példányra, egy dir+prefix
  peldányonként — nincs duplikált tail-logika).
- **`listen.mjs` több-forrás** — az agora mellett `--room <id>` (ismételhető)
  + `--rooms-dir`/`--remote-rooms-dir` egy MÁSODIK, önálló gyerek-folyamatot
  és önálló `since`-vízjelet indít (sosem közös watermark az agorával). Szoba-
  sor formátum: `[room <id> | origin from/instance ...]`. Bot-eredetű
  szoba-sor NEM indít kört (`lib/rounds.mjs` `origin`-tudatos), csak megjelenik
  — kivéve címzett/`requires_response`, ami "NEKED szol" jelölést kap.
- **`bridge.mjs` scribe-írás** — indításkor felderíti, mely telepített
  `mirrored` szobákban ő a scribe (`discoverScribeRooms()`), és a bejövő
  emberi Telegram-üzenetet a meglévő agora IN mellé a szoba-naplóba is beírja
  (`scribeRoomsIn()`, `origin: "human"`, `tg_key` a kereszt-forrás deduphoz),
  best-effort, `rooms.<id>.last_room_write_ok/_error` health-jellel. Szoba-
  követés a hídban NINCS.
- **`room-listen.mjs`** — box-oldali kézbesítő démon, agentenként EGY
  folyamat (nem a híd — a Telegram-poller blast radiusát nem növeljük). A
  tagsági szobák naplóját követi (follow.mjs `createSource` gépezet) és
  sanitizált sorként injektálja a saját tmux sessionbe (`lib/inject.mjs`,
  a híd inject-útjának kiemelt magja). Tartós, szobánkénti kurzor
  (`room-cursor-<room-id>.json`), ami csak sikeres kézbesítés UTÁN lép;
  közös pending-sor a szobák között; hiányzó/korrupt manifeszt vagy nem-tagság
  → hangos leállás (systemd Restart hozza vissza).
- **`docs/protocol.md`** — új §7 (szobák: manifeszt, szoba-sor séma —
  `reply_to_eid` vs. `reply_to` szétválasztva, `tg_key` kereszt-forrás dedup,
  ttl/thread_id öröklés, loop-fékek, scribe-szemantika+health, kézbesítési
  szerződés, "kézi inject tilos" elv). A fejlesztői-session útmutató (ebben a fában nincs) — új §6–7
  (több-forrás `listen.mjs` a valós flagekkel, `post.mjs` SSH-n át, exit
  kódok táblája).
- Codex adverzariális review beépítve a tervezés és implementáció közben
  (tartós kurzor, forrásonkénti watermark, budget lock alatt, kereszt-forrás
  dedup, thread-mintázat, scribe-health, azonosítás agent-néven).
- Tesztek: 106 → **215** (`node --test`).

## 1.2.0 — 2026-08-09 — "agora" több-példányos válasz-protokoll

Terv és Codex adverzariális review beépítve (a design-spec archivált, nem
része ennek a repónak).

- **`lib/sanitize.mjs`** — a `bridge.mjs`-ből kiemelve, önálló modul (1.2
  előkészítés); a `listen.mjs` innen importálja ugyanazt a sanitize-logikát,
  hogy az agora-stream tartalma se tudjon hamis protokoll-sort vagy
  vezérlőkaraktert csempészni a sessionbe.
- **`lib/agora.mjs`** — az agora-sor formátuma: `eid`-alapú dedup-kulcs,
  `appendAgora()` (egy `appendFileSync`/sor, max ~4 KB, egyszeri retry, sosem
  dob), `parseAddressedTo()` (`@<instance>:` cím-parse), `INSTANCE_RE`
  validáció.
- **`bridge.mjs`**: bejövő agora-sorok (`agoraIn()`) sikeres
  kézbesítés/enqueue után — szöveg, szerkesztés, reakció és média (`[media]`
  jelölővel, fájl-út nélkül).
- **`send.mjs`**: `--instance <id>` (kimenő prefix + OUT agora-sor,
  **prefix-előbb-aztán-vágás** sorrendben), `--text-stdin` (a dev-session
  SSH-útjának kizárólagos szövegforrása — fix argv, injection-mentes), és
  **exit code 3**: küldés/reakció sikeres, de az OUT agora-sor írása
  elhasalt — hangos jelzés a dupla-válasz kockázatról.
- **`follow.mjs`** — box-oldali stream-szerver: catch-up (`--since`, több
  napfájlon átívelően, átfedéssel) + élő tail (poll-alapú, ~500ms), UTC
  éjféli átfordulásnál 2 perc kegyelmi idővel a tegnapi fájlra; stdout
  kizárólag agora-JSONL, minden diagnosztika stderr-re.
- **`lib/rounds.mjs`** — a "ki válaszoljon?" 3 körös, csend felé húzó
  állapotgépe (t=0 / +30s / +60s), I/O-mentes és determinisztikusan
  tesztelt: a 2. kör mindig elsül (kiegészítés-eset is), a 3. kör csak
  válasz nélküli bejövőre; `--reply-to`-korreláció adja a "megválaszolt"
  definíciót; reakció sosem válasz; címzett üzenetre nincs kör.
- **`listen.mjs`** — dev-session-oldali figyelő: SSH-cső indítása fix
  argv-vel, sorpuffer, `eid`-dedup, auto-reconnect exponenciális backoffal +
  catch-up, kör-emlékeztetők kiírása.
- **`docs/protocol.md`** — új §6 (agora: sor-formátum, fájl/rotáció,
  címzés, kör-protokoll) + §2 kiegészítés (`--instance`, `--text-stdin`,
  exit 3). A fejlesztői-session útmutató (ebben a fában nincs) — új: hogyan indít egy Mac-session
  figyelőt és küld a boxon át.
- Tesztek: 42 → **106** (`node --test`).

## 1.1.0 — 2026-08-09
- send.mjs: reaction-támogatás (`--react <emoji> --message <id>`,
  setMessageReaction) — az emoji-nyugta agent-szabályokhoz (pl. media
  assistant) kell a stock plugin kivezetése után.


## 1.0.1 — 2026-08-09 — Codex kód-review javítások

Adverzariális kód-review a cutover kapujaként (2 × P1, 6 × P2, 1 × P3) —
a teljes verdikt és a tételenkénti feloldás a belső review-naplóban van (ebben a fában nincs).

- **[P1] `saveJsonStrict()`** — a tartósság-kritikus írók (média-sor enqueue,
  pending, album-puffer) többé nem nyelik le az írási hibát. A poll-ciklus
  őszinte lett: egy update feldolgozási hibája megszakítja a köteget, és az
  **offset nem lép a hibás update fölé** — az újra le fog jönni. A nem
  kritikus írók (health, offset-mentés, retention) szándékosan maradtak
  lenyelők: egy health-írás hibája nem döntheti meg a hidat.
- **[P1] `loadJsonQuarantine()`** — sérült állapotfájl nem íródik felül némán:
  karanténba kerül (`<path>.corrupt-<epoch>`), és a híd **riaszt a csoportba**
  a karantén-útvonallal. A visszajátszás forrása az `events-*.jsonl`.
- **[P2] `getMe` validálás** — érvénytelen válasz esetén FATÁLIS kilépés.
  Korábban `BOT_USERNAME=""` maradt, és a mention-kapu **minden** csoport-
  üzenetet némán eldobott, miközben az offsetet léptette.
- **[P2] `lib/gating.mjs` — pontos mention-illesztés.** Telegram `entities`
  alapján, szóhatáros + kis/nagybetű-érzéketlen visszaeséssel: a
  `@botnev_evil` többé nem nyitja a kaput, a `@BOTNEV` viszont igen.
- **[P2] `edited_message`** — bekerült az `allowed_updates`-be (a lista
  LECSERÉLI az alapértelmezettet, eddig a javított üzenetek sosem értek be).
  A sor végén `| szerkesztett` jelölő; a mention-kapu rájuk is érvényes.
- **[P2] `last_event_error` health-mező** + a `docs/protocol.md` kimondja:
  a `last_poll_ok` a POLLOZÁST bizonyítja, a `last_delivered` a KÉZBESÍTÉST —
  a fogyasztó a kettő RÉSÉRE riasszon.
- **[P2] `sanitize()` az interpolált mezőkre is** — a küldő `first_name`-je
  (`who`) és a reakció-emoji lista is átmegy rajta; egy újsoros profilnév
  többé nem injektálhat önálló, hamis sort a tmux sessionbe. Új tiszta
  `buildReactionLine()`.
- **[P2] Korlátos at-least-once — dokumentálva.** A telt pending-sor (alap
  500) a legrégebbit dobja, hangos riasztással; a napló marad a visszajátszási
  forrás. Új `docs/protocol.md` §4 (Tartóssági szerződés).
- **[P3] `send.mjs` argv-parser** — `--` opció-lezáró; hiányzó opció-érték a
  sor végén használati hiba (exit 1); nem numerikus `--reply-to` hangos hiba
  (korábban `NaN` → az üzenet némán, reply nélkül ment ki).
- Tesztek: 16 → **42** (`node --test`).

## 1.0.0 — 2026-08-09
- Kötelező env-k (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_GROUP_CHAT_ID`,
  `TELEGRAM_ALLOWLIST_IDS`, `TMUX_SESSION`, `BRIDGE_STATE_DIR`) hiánya
  fatális induláskor — rossz agent alá indított híd sose induljon el rossz
  konfiggal.
- Csoportban mention-kapu (`BRIDGE_REQUIRE_MENTION`): csak `@botnév`-es
  vagy a bot üzenetére adott reply jut be, alapból.
- Tartós média-sor (`lib/mediaqueue.mjs`) + album-puffer: a letöltés
  összeomlás-biztos, restart után folytatja.
- `fetch` timeout mindenhol (`AbortSignal.timeout`) — elakadt hívás nem
  fagyaszthatja némán a pollert.
- `health.json` életjel-fájl a flotta-audithoz (`lib/health.mjs`).
- `BRIDGE_AGENT_LABEL`: több telepített híd esetén a `selfAlert` a saját
  nevében szól, nem egy fix néven.
- Pending-sor mélység-sapka (`BRIDGE_MAX_PENDING`) — egyszeri riasztással,
  ha a sor tele van.
- Méret-ellenőrzés letöltés előtt (`BRIDGE_MAX_FILE_BYTES`) — a `getFile`
  válaszból kiolvasott méret is ellenőrizve, nem csak a letöltött tartalom.
- **Új: `send.mjs`** — kanonikus kimenő CLI, plain text (nincs
  `parse_mode`, nincs formázás-injekció), 4096 karakteres vágás,
  **reply targeting** (`--reply-to`) a bejövő `msg=`/`reply_to=` mezőkhöz
  kapcsolódva.
- Új kontraktus-doksik: `docs/config.md` (teljes env-szerződés),
  `docs/protocol.md` (inject-formátum, kimenő szerződés, egy-token-egy-
  poller szabály, health-szerződés).

## 0.9.0 — 2026-08-09
- Import: egy ágens telegram-bridge.mjs-e a boxrol, valtozatlanul.

## 1.5.0 — 2026-09-17

- A híd core-ja a flotta-repóba költözött (`bridge/`). A szoba-réteg
  (post, follow, room-listen, session-listen, budget, rounds, session-state) az
  archivált sub-etha repóban marad; a `bridge.mjs` scribe-funkciója rooms-dir
  nélkül tétlen.
- `send.mjs --html`: Telegram-HTML küldés a `lib/html.mjs` szűrőjén át — csak az
  engedett tagek (b i u s code pre a blockquote tg-spoiler) maradnak, minden más
  escape-elődik. Alapból továbbra is plain text, parse_mode nélkül.

## 1.5.1 — 2026-09-17

- `sanitize`: a bejövő szöveg plafonja 1500 → 4096 (a Telegram sajátja), és a
  vágás többé nem néma — a sor végén `[…csonkítva: +N karakter, …]` jel.
  (Egy ágens jelentése: egy 2473 karakteres feladatleírás jelzés nélkül félbeszakadt.)

## 2.0.0 — 2026-10-14 — kézbesítési napló, az agora kivezetése (TÖRŐ)

Az agora (`lib/agora.mjs`), a szobák (`lib/rooms.mjs`),
a példány-azonosság (`lib/iid.mjs`), az `@instance:` címzés, a `follow` és a
testvér-példány fan-out megszűnt, a tesztjeikkel együtt. Ágensek között a
natív Claude Code csatorna (`ListAgents` / `SendMessage`) megy, nem a híd.

- **Új: kézbesítési napló** — `telegram-inbox/delivery-YYYY-MM-DD.jsonl`
  (ugyanaz a könyvtár, ahol az `agora-*.jsonl` volt). Sortípusok: `inbound`
  (a híd írja), `intent` (a `send.mjs` írja a Telegram-hívás ELŐTT),
  `outcome` (`confirmed` / `failed` / `unknown`, Telegram `message_id`-vel).
  A válasz a bejövőhöz `reply_to`-val kötődik. Kimenet nélküli szándék =
  `unknown`: ha a `send.mjs` a kérés után összeomlik, a küldés nem tűnik el.
  Séma: `docs/delivery-log.md`. Kód: `lib/delivery-log.mjs`, `lib/outbound.mjs`.
- **Új: `delivery.mjs`** — napi összesítő: megválaszolatlan bejövők és
  bizonytalan küldések (exit 2, ha van ilyen). A `fleet bridge install`
  telepíti a `bridge.mjs` és a `send.mjs` mellé.
- **`send.mjs`**: a `--instance` kapcsoló és a `[<példány>] ` előtag megszűnt.
  Új exit kód: `5` = `unknown` (a kérés elment, válasz nem jött; lehet, hogy
  kiment). A `1` most azt is jelenti, hogy a Telegram elutasította (nem ment
  ki). A `3` jelentése: kiment, de a kézbesítési napló nem íródott. A napló
  helye env nélkül a telepítési helyből származik (`<state>/sub-etha/` →
  `<state>/telegram-inbox`). Új env: `SUBETHA_SEND_TIMEOUT_MS` (alap 20 s).
- **`bridge.mjs` szétszedve** (1020 → 137 sor): `lib/telegram.mjs`,
  `lib/media.mjs`, `lib/lines.mjs`, `lib/deliverer.mjs`, `lib/albums.mjs`,
  `lib/handlers.mjs`, `lib/inbox.mjs`, `lib/poll.mjs`. A bejövő viselkedés
  (inject-formátum, offset-szemantika, pending, album, health) változatlan,
  kivéve: a scribe-írás és az iid-fájl írása megszűnt, a `BRIDGE_AGENT_NAME`
  env és a `BRIDGE_WRITE_IID` / `--write-iid-file` hatástalan.
- **Health**: `last_agora_error` és `rooms.*` helyett `last_delivery_log_error`.
- **Szabálysablon és runtime skill**: a „kiment-e a válasz?" ellenőrzés az
  OUT-sorok számolása helyett a `delivery.mjs`-t futtatja (fleet 1.1.0).

### Migráció a boxokon

1. A box fleet-leader checkoutjának frissítése után `fleet bridge install
   <ágens>` minden ágensre (a `reconcile` hidat nem telepít), majd
   `systemctl --user restart <ágens>-telegram-bridge`. A `fleet bridge status`
   mutatja, hol maradt 1.x. A telepítés a teljes `sub-etha/` könyvtárat
   cseréli, a régi példány (benne `lib/agora.mjs`, `rooms.mjs`, `iid.mjs`) a
   `.bak-<idő>` mappába kerül.
2. `fleet upgrade <repo>` minden ágens-repóra: a szabályfájl új verziója a
   `delivery.mjs`-re hivatkozik. Amíg ez nem fut le, a régi szabály a már
   nem íródó `agora-*.jsonl`-t számolja, és **minden ágenst némának lát.**
3. Aki `send.mjs --instance`-t hív (dev-session szkriptek, régi `listen.mjs`
   SSH-hívás), az 2.0-tól szöveg részeként küldi el a kapcsolót: vedd ki.
4. Az `agora-*.jsonl` fájlokat senki nem olvassa már; a retention (14 nap)
   magától elviszi őket. Az `<state>/iid.env` és egy esetleges `rooms/`
   könyvtár kézzel törölhető.
5. Ha valami a `send.mjs` kilépési kódját nézi: az `5` (unknown) új. A
   `fleet` riasztója (`alerts.py`) csak a `0`-t és a `3`-at veszi
   kiküldöttnek, `5`-nél stderr-re is ír — ez így szándékos.
