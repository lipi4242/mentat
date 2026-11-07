# Cutover — egy box átállítása a flotta (Mentat fleet) felügyeletére

Két vezérlő nem futhat egyszerre, és a tulajdonjog átadása kimondott lépés,
nem mellékhatás.

## 0. Előfeltétel
- Egy Mentat-checkout (alapból `~/src/mentat`; a példák `fleet`-nek hívják: `ln -s
  ~/src/mentat/fleet/bin/fleet ~/.local/bin/fleet`), `fleet --version`.
- **Ha a boxon fut korábbi felügyelő** (saját watchdog-timer): MIELŐTT bármit
  telepítenél, `echo watchdog > ~/.config/fleet/controller`. A `fleet install`
  a tulajdonjog-fájlt csak akkor írja (`reconcile`), ha NINCS — egy meglévőt
  nem ír felül, így a két vezérlő nem futhat egyszerre.
- A registry beállítva: `echo /út/a/registryhez > ~/.config/fleet/registry`
  (vagy `FLEET_REGISTRY` a timer-unitokban), és `bin/fleet validate` zöld.
- `echo <box-kulcs> > ~/.config/fleet/host` (a `boxes.json` kulcsa), vagy
  `FLEET_HOST` a timer-unitban. Ismeretlen host = csak megfigyelés.
- `bin/fleet release` — a release-tuple felírása.

## 1. Megfigyelés
```sh
fleet reconcile --observe
fleet doctor
```
Minden sor `noop`/`skip`, vagy olyan beavatkozás, amit te is megtennél. Ha
nem, előbb a registry vagy a mérés javul, nem a cutover.

## 2. Unitok és hidak
Ágensenként, egyenként, először egy nem kritikus canaryvel:
```sh
fleet lock <agent> --ttl 30
fleet install <agent>          # unit + drop-in (mentés .bak-…) + felügyelet + postcheck
fleet bridge install <agent>   # ha van híd
systemctl --user restart <agent>-telegram-bridge.service   # csak a híd!
fleet doctor <agent>           # csatorna=ok, nincs 409
fleet unlock <agent>
```
A `fleet install` újraindítja az ágenst, ha a unit változott (a postcheck
csak így mondhat igazat); változatlan unitnál nem nyúl a futó processzhez.
Kritikus ágenst csak idle állapotban. Bukáskor az előző unit áll vissza és
indul újra.

## 3. Tulajdonjog átadása
Ha a boxon fut egy korábbi felügyelő (saját watchdog-timer), előbb azt
állítsd le. Utána:
```sh
echo reconcile > ~/.config/fleet/controller
```
A `fleet-reconcile.timer`-t az első `fleet install` már felhúzta (a
checkout tényleges útvonalával), a régi `agent-liveness.timer`-t levette: a
liveness funkciói (OOM-védelem, tick re-arm) a reconcile-ban futnak.
Egy teljes kör után: `journalctl --user -u fleet-reconcile -n 40`.

## 4. Rollback
```sh
systemctl --user disable --now fleet-reconcile.timer
rm ~/.config/fleet/controller
```
Ettől a box felügyelet nélkül marad, amíg a korábbi felügyelőt vissza nem
kapcsolod. A régi unitok a `.bak-<idő>` fájlokban; a régi hidak a
`~/.config/<agent>/sub-etha.bak-<idő>/` könyvtárakban.
