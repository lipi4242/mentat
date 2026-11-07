# `fleet setup` — mit csinál, és mit ír

Háttér-olvasmány; a használathoz a README „Kihelyezés egy boxra” része elég.
Csak akkor olvasd, ha a setup egy lépésnél megállt, és a kiírt sor nem elég.

## A lánc

| lépés | mit tesz | megáll, ha |
|---|---|---|
| registry | `FLEET_REGISTRY` / `~/.config/fleet/registry` | nincs beállítva, vagy nincs benne az ágens |
| validate | `fleet validate`; más ágensek hibái csak megjegyzés | EZ az ágens (vagy a registry egésze) hibás |
| join | `.claude/rules/fleet.md`, `.claude/fleet.json`, a plugin a repó settingsében; `mentat.json` esetén a szinergiák és a tick ütemezésének átvétele (`schedule_owner: fleet`) | a workdir nem git repó |
| preflight | `fleet preflight` + tmux | bármelyik találat (tmux: a sor megadja a telepítő parancsot) |
| install | lent részletezve | a sor megmondja az okot és a javító parancsot; minden visszaáll |
| híd | `fleet bridge install` + újraindítás, ha a registryben van `bridge.unit` | — |
| plugin | `claude plugin marketplace add` + `install`, az ágens fiókjába | soha: hiba esetén megjegyzés |
| első tick | ha a flotta ütemez, és még nincs `last-tick.json`: `systemctl --user start fleet-tick-<név>.service` (`--no-tick`: kihagyja) | — |
| reconcile, doctor | a felügyelet első köre és az ítélet | — (a doctor ítélete adja a kilépési kódot) |

## Az install, kézi lépések nélkül

1. **tmux**: a unit a `/usr/bin/tmux`-ot hívja. Ha nincs, a hiba a csomagkezelő
   parancsát adja (`sudo apt-get install -y tmux` stb.); a setup nem telepít.
2. **Login a unit szemével**: a `claude auth status` a unit környezetével fut
   (a unit által törölt `ANTHROPIC_API_KEY`/`CLAUDE_API_KEY`/
   `CLAUDE_CODE_OAUTH_TOKEN` nélkül, a fiók `CLAUDE_CONFIG_DIR`-jével, az
   ágens env-fájljának tokenjével). Ha így nincs login, de a telepítő
   shelljében vagy a systemd user manager környezetében van
   `CLAUDE_CODE_OAUTH_TOKEN`, az a `~/.config/<név>/claude-auth.env`-be kerül
   (0600; a unit pane-shellje betölti, a híd nem). Régi unit-sablonnál
   (a claude-auth.env betöltése előtt) az ágens env-fájljába, figyelmeztetéssel.
   A token sosem jelenik meg a kimenetben vagy parancssorban. Ha sehol nincs:
   `fleet auth <név>` abban a shellben, ahol a claude be van jelentkezve.
3. **Az első indítás ablakai előre elfogadva** (a fiók könyvtárában;
   `shared` = `~/.claude.json` + `~/.claude/settings.json`, nevesített fiók =
   `~/.claude-<fiók>/` alatt mindkettő). Csak a hiányzó kulcsot írja, a többi
   megmarad, hibás JSON-t nem ír felül:

   | fájl | kulcs | ablak |
   |---|---|---|
   | `.claude.json` | `hasCompletedOnboarding`, `theme` (ha nincs) | téma, bevezető |
   | `.claude.json` | `projects[<workdir>].hasTrustDialogAccepted` | workspace trust |
   | `.claude.json` | `remoteDialogSeen` | Remote Control |
   | `settings.json` | `skipDangerousModePermissionPrompt` | Bypass Permissions |
   | `settings.json` | `hooks.SessionStart` → `bin/capture-session-id.sh` | — (a `--resume` alapja) |

   A kulcsok a Claude Code 2.1.x binárisából mérve (2026-10-16). Új verzió új
   ablakot hozhat — ezért a 4. pont.
4. **A pane-t is nézi**: a processz után a tmux-pane szövegét; ha a claude egy
   ismert ablaknál áll (`fleet.pane.DIALOGS`), az hiba, visszaállítással. A
   `fleet doctor` ugyanezt nézi minden futáskor.

## A doctor ítélete

- **RC opcionális**: nem mérhetően `n/a` (➖), a kilépési kódot nem rontja (a
  transzkript a visszakapcsolódást nem naplózza; a postcheck sem követeli).
- **Ütemezés, ha a flotta ütemez**: a `last-tick.json` kora a
  `fleet-tick-<név>.timer` periódusához mérve (`OnCalendar`, vagy a registry
  `tick_period_s`), `proactive: false` mellett is. Ugyanaz a frissesség-szabály
  (`schedule_verdict`) és ugyanaz a csend-riasztás (reconcile), mint a claude
  saját loopjánál; a türelmi idő a timer élesítésétől számít. A restart utáni
  postcheck ezt nem várja meg (a claude újraindítása nem hat a timerre).
- **Auth friss ágensnél**: amíg az ágens nem válaszolt (nincs transzkript),
  a telepítéskori sikeres `claude auth status` 24 óráig bizonyíték.

## Ha megállt

| sor | teendő |
|---|---|
| `hiányzik a tmux` | a kiírt csomagkezelő-parancs, aztán `fleet setup <név>` |
| `nincs bejelentkezve … fleet auth <név>` | abban a shellben: `fleet auth <név>`; vagy `claude auth login` |
| `… ablaknál áll a tmux-ban` | a sor megnevezi a kulcsot; ha az megvan, ez egy új ablak — jelentsd |
| `plugin: NEM települt … privát repó` | `gh auth login && gh auth setup-git`, majd újra `fleet setup <név>` |
| doctor `pending` | az első tick / processz még nem dőlt el: `fleet doctor <név>` pár perc múlva |
