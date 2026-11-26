---
name: runtime
description: A saját futásidőd és túlélésed always-on flotta-ágensként — mi indít újra, mi jár le, hogyan kérj újraindítást, mit ellenőrizz induláskor. Használd a startup skilledből, vagy ha nem érted, miért indultál újra.
---

# /fleet:runtime — amit magadról tudnod kell

Systemd `--user` + tmux alatt futsz egy Linux boxon (vagy egy fejlesztői
gépen, felügyelet nélkül). A registry (`agents.json` a `FLEET_REGISTRY`
könyvtárban)
mondja meg, hogy `active` vagy `dormant` vagy — ezt a `fleet reconcile` 5
percenként érvényesíti.

## Induláskor (a startup skilled tegye meg)
1. **Ütemezés.** A `/loop` és minden `CronCreate` jobod **7 nap után lejár**,
   és a `--resume` **nem hozza vissza** a lejártakat. Fegyverezd fel
   mindet, amit a munkádhoz használsz — ne csak a ticket.
2. **Kimaradás.** Ha a `data/state/last-tick.json` vagy a heartbeat több
   órás rést mutat, kimaradtál: jelezd a tulajdonosnak egy sorban, és
   ellenőrizd újra a nyitott tételeidet, ne feltételezz folytonosságot.
3. **RC.** Ha a session `Remote Control disconnected`-et ír, a natív
   csatornán nem látnak. Ezt csak egy kívülről kért restart javítja.

## Minden tick végén
- **Kiment-e a válasz?** Futtasd
  `node ~/.config/<te>/sub-etha/delivery.mjs` (a mai kézbesítési napló,
  `~/.config/<te>/telegram-inbox/delivery-<ma>.jsonl` összesítése). Ha
  `MEGVÁLASZOLATLAN` sort ír, néma vagy: a válaszaid a pane-ben ragadtak, és
  minden felügyeleti jel zöld marad. Küldd ki `send.mjs --reply-to <msg>`-gel,
  röviden. Az `UNKNOWN` sor elindult, de vissza nem igazolt küldés (timeout
  vagy leállt folyamat): lehet, hogy kiment; ha számít, küldd újra. Ez a
  legolcsóbb detektor az „él, de senki nem hallja" hibaosztályra.

## Amit soha
- `systemctl restart`, `systemd-run` vagy saját restart-szkript a saját
  unitodra a saját sessionödből — a kill-session téged öl meg a parancs
  közepén, és a felügyelet költségvetése sem látja. Helyette lásd lent:
  `fleet request-restart`.
- Egy másik ágens hídját, unitját, session.id-ját piszkálni.
- A tmux pane-ből ítélni a saját vagy más működését.
- **`AskUserQuestion`-t használni.** Headless tmux alatt a menüt senki nem
  látja; a híd következő beinjektált sora + Enter az alapértelmezett opciót
  választja, és „Igen"-t kapsz a tulajdonos nevében, amit ő sosem adott
  (2026-09-24). Kérdés Telegramon, válasz Telegramon.

## Ha újraindulás kell
`fleet request-restart` (csak a saját ágensedre megy), vagy szólj Thufirnak,
a flottamenedzsernek, aki ugyanezt teszi. Jelölőt tesz le, semmi mást: a
restartot mindig a timer-reconcile végzi, Thufirnál is, soha nem a saját
session. A köröd vége után (rövid tétlenség) `--resume`-mal indít újra:
a beszélgetés megmarad, postcheck nézi, és az első üzenet megmondja, miért
indultál újra. Külön keretből fogy (3 / 6 óra), nem a crash-restartokéból;
ha elfogyott, nem indul újra, és a tulajdonos jelzést kap.

## Ami magától történik
- Ha a processzed meghal: a reconcile újraindít (3/óra), és postcheckkel
  nézi, hogy jó-e a restart (RC, poller, 409, tick).
- Ha a betöltött promptod (CLAUDE.md + @include-lánc, AGENTS.md,
  `.claude/rules|commands|skills|agents`, `.claude/settings.json`) tartalmilag
  változott az indulásod óta (pl. egy box-frissítés után), és a változás
  kiadott (commitolt) és 15 perce stabil: tétlenkor a reconcile `--resume`-mal
  újraindít, dolgozás közben megvár (6 óra után jelez). Kézi, nem commitolt,
  fiók-szintű vagy hooks-változásra nem indít újra, csak jelez. Az első üzenet (`[fleet] Újraindultál…`) felsorolja a változott
  fájlokat. A `.claude/settings.local.json` nem számít.
- Ha a transzkripted 10 MB fölé nő: a következő indulás **friss** lesz
  `--resume` helyett (a 153 MB-os resume vitte el a boxot 2026-08-07-én).
  Az állapotod a repóban, a `data/`-ban és a dokumentumokban éljen, ne a
  chat-előzményben.
- Ha a memóriád 1,1 GB fölé nő: a reconcile jelzi; idle állapotban tervezett
  restart jöhet.
- Ha 12 periódusnyi ideig nem tickelsz: riasztás megy a tulajdonosnak.
