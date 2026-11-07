---
name: new-agent
description: Új ágens létrehozása a három komponensből (Mentat AI Brain, anytime reducer, fleet) — repó, agy, motor, flottatagság, opcionálisan kihelyezés egy boxra. Használd, ha a tulajdonos új ágenst kér.
---

# /fleet:new-agent — új ágens a három komponensből

Egy ágens három választható részből áll, mind az egy Mentat-repóban
(`lipi4242/mentat`, egy klón: `~/src/mentat`); fork vagy tükör esetén azt a
fiókot írd a helyére (a fleet plugin marketplace-e: `FLEET_MARKETPLACE_REPO`):

| komponens | hol a repóban | mit ad |
|---|---|---|
| **Mentat AI Brain** | a gyökér (`INSTALL.md`, `reference/`) | `AGENTS.md` + `brain/` tudásmappák, a személyiség és a munkamód |
| **anytime reducer** | `engine/` | proaktív motor: concernek, triggerek, állapot, heartbeat |
| **fleet** | `fleet/` | flottatagság: szabályok, névsor, kérés, felügyelet, kihelyezés |

A klón, ha még nincs (a kiadás tagjén): `git clone -q --depth 1 --branch v<verzió>
https://github.com/lipi4242/mentat ~/src/mentat`.

## 0. A kötelező kérdések (ezeket KÉRDEZD MEG, ne döntsd el)
1. **Név** (slug: kisbetű, szám, kötőjel) és **szerep** egy mondatban.
2. **Melyik komponensek** kellenek a háromból.
3. Ha fleet: **melyik boxra** kerüljön (a registry `boxes.json`-ja), vagy
   egy fejlesztői gépen marad felügyelet nélkül (`supervision: none`).
4. Ha fleet: **kell-e Telegram-híd** (saját bot, a tulajdonos BotFatherén).
5. Ha reducer: **milyen kadencia** (`tick_period_s`).

## 1. Repó
```bash
gh repo create <fiókod>/<név>-assistant --private --clone
cd <név>-assistant && git commit --allow-empty -m "chore: <név> születik"
```

## 2. Agy (ha kell)
Kövesd a bootstrap eljárást: `WebFetch
https://raw.githubusercontent.com/lipi4242/mentat/v0.5.0/reference/initialization.md`
és hajtsd végre a repóban (AGENTS.md, brain/, intro-chat). Jegyezd fel a
verziót (a README-ben áll), a `fleet join --brain <verzió>` ezt teszi a
manifestbe.

## 3. Motor (ha kell)
```bash
~/src/mentat/engine/sync-to.sh "$PWD"        # vendorolt másolat + VENDORED.md
```
Aztán `entry.py` a gyökérben (a sablon a repó README-jében), egy `concerns/`
mappa, és `python3 entry.py --validate` zöld.

## 4. Flottatagság
```bash
fleet join "$PWD" --agent <név> --brain <v> --reducer <v>
```
Ez teszi be a `.claude/rules/fleet.md`-t, a `.claude/fleet.json`-t és a
plugin engedélyezését. Commitold.

## 5. Registry + kihelyezés (ha boxra kerül)
1. PR a registry-repódba (amire a `FLEET_REGISTRY` mutat): egy bejegyzés az
   `agents.json`-ban (`agent, unit, session, workdir, model, host, status,
   rc_name, proactive, loop_cmd, tick_period_s, telegram_bot, bridge,
   runbook`) és egy runbook `runbooks/<név>.md` (a runbook útvonala a
   registry könyvtárához relatív). Ez emberi jóváhagyású sáv.
2. A boxon, merge után: a registry-checkout frissítése (`git pull`), aztán
   ```bash
   fleet setup <név> --check  # nem ír; mi hiányzik (tmux, login, első indítás)
   fleet setup <név>          # validate → join → preflight → install → híd → plugin → reconcile → doctor
   ```
   Egy összefoglaló sorral zár (0 kész · 3 függő · 1 hiba + a javító parancs).
   A bot-token a `~/.config/<név>/telegram.env`-ben él (0600). Ha a unit nem
   lát Claude-logint: `fleet auth <név>` abban a shellben, ahol a claude be
   van jelentkezve. Leállítás/újraindítás csak `fleet stop|restart <név>`.
3. Az első tick megérkezéséig `fleet doctor` `pending`-et mutat; utána
   `armed`. Ha `stale` marad: a startup skill nem húzta fel a loopot.

## Mit ne
- Ne másolj motort kézzel egy másik ágensből (verziótlan másolat).
- Ne tedd a bot-tokent a repóba.
- Ne kapcsold be a telegram-plugint a repóban.
