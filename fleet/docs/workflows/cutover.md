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
Ágensenként, egyenként, először egy nem kritikus canaryvel, kritikus ágenst
csak idle állapotban:
```sh
fleet setup <agent> --check    # semmit nem ír, megmondja, mi hiányzik
fleet setup <agent> --no-tick  # validate → join → preflight → install → híd → plugin → titok-kapu → reconcile → doctor
```
A `fleet setup` újrafuttatható. Az `install` csak változott unitnál indítja
újra az ágenst (a postcheck csak így mondhat igazat), bukáskor az előző unit
áll vissza és indul újra; a hidat viszont minden futáskor újratelepíti és
újraindítja. Karbantartási zárat nem vesz fel. Kilépési kód: 0 kész · 3 még nem dőlt el · 1 hiba. A join
az ágens-repó fleet-fájljait is írja, ezt a repóban commitold.

A már flottán futó box új kiadásra emelése nem ez, hanem a
`fleet box-upgrade --to <tag>` (előbb `--dry-run`).

**Tartalék, ha a parancs nem fut:** a unit és a híd kézzel (a join, a
plugin és a titok-kapu ilyenkor külön lépés: `fleet join <repó> --agent <agent>`, `fleet plugin
install <agent>`, `fleet secrets hook install`):
`fleet lock <agent> --ttl 30`, `fleet install <agent>`, híd esetén
`fleet bridge install <agent>` és `systemctl --user restart
<agent>-telegram-bridge.service` (csak a híd!), `fleet doctor <agent>`
(csatorna=ok, nincs 409), végül `fleet unlock <agent>`.

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
