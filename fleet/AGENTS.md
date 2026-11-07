# fleet-leader — az always-on ágensek futtatásának terméke

Ez a repó egy ágensflotta harmadik komponense (a Mentat AI Brain és az
anytime reducer mellett): tagság, szabályok, névsor, kérés, felügyelet,
kihelyezés. Nincs mögötte always-on ágens — systemd-timerekből fut, a tudás
írásban áll, és aki dolgozik vele, innen indít egy sessiont.

A **registry nincs a repóban**: a `FLEET_REGISTRY` környezeti változó vagy a
`~/.config/fleet/registry` fájl mutat rá (`fleet.registry_dir()`). Tesztekhez
és kipróbáláshoz: `examples/registry/` (kitalált ágensek). Személyes vagy
flotta-specifikus adat (nevek, IP-k, bot-nevek, útvonalak) ide nem kerülhet.

## Térkép

| réteg | hol | mit tud |
|---|---|---|
| **Registry (kívül)** | `$FLEET_REGISTRY/agents.json`, `boxes.json`, `accounts.json`, `runbooks/`, `units/` | HOL és HOGYAN fut egy ágens — emberi jóváhagyású sáv a registry saját repójában |
| **Futtató** | `src/fleet/` (stdlib), `bin/fleet` | `reconcile` (5 perces timer, az EGY vezérlő: kívánt állapot, OOM-védelem, tick re-arm, duplikáció-riasztás), `postcheck`, `doctor`, `roster`, `render`, `init` (registry-bejegyzés a repóból), `setup` (a teljes kihelyezés egy parancsa), `install` (tranzakció zöld postcheckig; első indítás ablakai, auth a unit szemével), `auth`, `stop`/`wait-up`/`restart` (egy ágens, célzottan), `bridge install`, `join/upgrade` (mentat.json-szinergiák), `secrets` (titok-leltár, jóváhagyott kulcsmozgatás, titok-kapu), `status`, `validate`, `preflight` |
| **Híd** | `bridge/` (Node) | Telegram ↔ tmux: `bridge.mjs`, `send.mjs` (`--html` szűrt formázás) |
| **Plugin** | `plugin/`, `.claude-plugin/marketplace.json` | skillek az ágensekbe: `roster`, `request`, `doctor`, `new-agent`, `runtime`; SessionStart hook |
| **Sablonok** | `templates/` | unit (RC + strict-mcp beépítve), drop-in, `rules/fleet.md.tmpl`, systemd-timerek |
| **Eljárások** | `docs/workflows/` | new-agent, cutover, zero-touch-setup |

## Az öt szabály, amit drágán tanultunk

1. **Egy sikertelen mérés sosem nézhet ki üres eredménynek.** Minden jelnek van
   `unknown` értéke, és az nem `down` és nem `ok`. A be nem állított registry
   hiba, nem üres flotta.
2. **A kívánt állapotot érvényesítjük, nem csak újraindítunk.** `dormant` = áll
   és letiltva; a `systemctl disable` önmagában nem üzen a felügyeletnek.
3. **A restart nem kész, amíg a postcheck nem zöld.** RC, poller, 409, tick.
4. **A felírás nem kötés.** Ami számít, az alatt teszt van (`tests/`,
   `bridge/test/`). Ültess szándékos hibát, mielőtt zöldre hivatkozol.
5. **A tmux pane-ből sose ítélj.** Transzkript, journal, nyugta.

## Fejlesztés itt

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src python3 -m unittest discover -s src/fleet -p 'test_*.py' -q
node --test "bridge/test/*.test.mjs"
FLEET_REGISTRY=examples/registry PYTHONPATH=src python3 -m fleet.cli validate
```

Kódot PR-ral szállítasz; a sajátodat nem mergeled.

## A boxon

```sh
fleet doctor            # minden ágens a jelekkel
fleet reconcile --observe
fleet doctor <agent> --fix
fleet release --show    # mi fut: sha, híd, plugin
```

(`fleet` = `<checkout>/bin/fleet`; a checkout helye nem kötött.)
A tulajdonjog a `~/.config/fleet/controller` fájlban van (`reconcile`).
Amíg nem az, a reconcile csak megfigyel. Új box: `docs/workflows/cutover.md`.
