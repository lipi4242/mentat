---
name: doctor
description: Egy flotta-ágens állapota a négy jel szerint (processz, ütemezés, csatorna, RC), és javítás kívülről — újraindítás postcheckkel, poller leölése, karantén feloldása. Használd, ha egy ágens néma, nem válaszol, vagy a tulajdonos kéri, hogy nézd meg.
---

# /fleet:doctor — egy ágens állapota és javítása

Fejlesztő ágensnek: így nézel meg és javítasz egy másik ágenst anélkül, hogy
a tmux pane-ből ítélnél.

## Diagnózis

Azon a boxon, ahol az ágens fut (ssh, vagy ha ott vagy, helyben):

```bash
fleet doctor <agent>      # fleet = a checkout bin/fleet-je (README: ~/.local/bin/fleet)
```

Az öt jel és a jelentésük. Minden jel egészsége `healthy` · `pending` ·
`unknown` · `unhealthy`, és az ágensé a LEGROSSZABB jelé. Csak a `healthy` OK
(kilépési kód 0); a `pending` (még nem dőlt el) és az `unknown` (nem mérhető —
a kimenet megmondja, miért) nem az. Kivétel az **RC: opcionális** — nem
mérhetően `n/a` (➖), és nem rontja a kilépési kódot.

| jel | healthy | pending | unhealthy | unknown |
|---|---|---|---|---|
| processz | `up` — a claude fut a várt `--remote-control` névvel | — | `down` | nincs /proc (nem Linux) |
| ütemezés (a flotta timerén is: `schedule_owner: fleet`) | `armed` / `n/a` | friss indulás, periódus + 3 perc még nem telt le | `stale` — a tick kimaradt, vagy a türelmi idő után sincs tick-nyom | a processz indulása nem ismert |
| csatorna | `ok` / `n/a` | — | `conflict` (409 — másik poller) / `stale` | nincs health.json |
| RC (opcionális) | `connected` / `n/a` (nincs esemény a processz indulása óta) | — | `disconnected` | — |
| auth | `ok` (friss ágensnél: a telepítéskori `claude auth status`, 24 óráig) | — | `expired` | nincs assistant-üzenet / session.id, és nincs friss telepítési bizonyíték |

**A pane nem bizonyíték arra, hogy dolgozik** — a transzkript mtime-ja, a
journal és a nyugták azok. Arra viszont igen, hogy NEM: ha a claude egy
indítási ablaknál áll (trust, Bypass, téma, login), a doctor ezt hibának
írja ki, a megelőző kulccsal együtt; javítás: `fleet setup <agent>`.

## Javítás

1. Ha csak egy dolog rossz és van rá célzott javítás, azt: poller → `kill
   <pid>`; 409 poller nélkül → `systemctl --user restart <híd-unit>`; a tick
   nem húzódott fel → küldd be a `loop_cmd`-et (`fleet reconcile --agent
   <agent>` ezt megteszi).
2. Ha restart kell: **kívülről**, soha az ágens saját sessionjéből.
   ```bash
   fleet doctor <agent> --fix    # reconcile egy ágensre + postcheck
   fleet restart <agent>         # vagy: célzott újraindítás + postcheck (soha ne pkill)
   ```
   A `--fix` csak akkor ír sikert, ha a javítás UTÁN újramérve minden jel
   `healthy`. A postcheck a restart mellékhatásait nézi (poller, 409, auth, és
   hogy a restart UTÁN landolt-e tick); a `pending` várakozás, a türelmi idő
   után bukás. Ha piros, a restart NEM kész — nézd meg a problémát, ne indíts újra megint.
3. Költségvetés: 3 restart/óra/ágens. Ha elfogyott, a reconcile riaszt és
   megáll — ilyenkor ember kell, ne kerüld meg. A `fleet stop` utáni egy
   visszaindítás nem számít bele a 3/órába, és a kimerült keretet a doctor
   nem-healthy-ként mutatja.
4. Karantén (két bukott postcheck): `fleet unquarantine <agent>` csak akkor,
   ha megértetted és elhárítottad az okot.

## Mielőtt hozzányúlsz egy dolgozó ágenshez
- Nézd meg, idle-e (transzkript mtime > 10 perc). Egy futó release vagy egy
  félbehagyott ügyfél-levél restartot nem ér meg.
- Tegyél rá karbantartási zárat (`fleet lock <agent>`), hogy a reconcile ne
  dolgozzon alattad; a zár 120 perc után magától lejár.
