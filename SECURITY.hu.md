# Biztonsági irányelv

[English version](SECURITY.md)

## Támogatott verziók

| Verzió | Támogatott |
|---|---|
| 0.5.x | igen |
| régebbi | nem |

## Sérülékenység bejelentése

Privátban jelezd, ne nyilvános issue-ban vagy pull requestben.

Használd a [**Report a vulnerability**](https://github.com/lipi4242/mentat/security/advisories/new)
gombot (a repó **Security** fülén; GitHub privát sérülékenység-bejelentés). Csak a karbantartók
látják. Írd le, mit találtál, hogyan reprodukálható, és melyik verziót vagy commitot futtattad.

Egy Mentat-ágens `bug-report` skillje biztonsági hibát sosem tesz nyilvános issue-ba: ha a hiba
szivárgásnak vagy egy védelem megkerülésének tűnik, megáll, és ide irányít.

Pár napon belül visszaigazolást kapsz. A javítás a támogatott ágon patch kiadásként érkezik, a
tanácsadó pedig a javítás elérhetővé válása után publikálódik. Ha nem kéred másképp, a
tanácsadóban név szerint megköszönjük.

## Egy kiadás ellenőrzése

Minden `vX.Y.Z` kiadási tag egyszer jön létre, és soha nem mozdul el és nem törlődik (ezt egy
repó-ruleset kényszeríti ki); a GitHub Release a közzététel után nem változtatható. A forrásarchívum
mellett ott a `SHA256SUMS` és egy aláírt build-provenance tanúsítvány:

```
sha256sum -c SHA256SUMS
gh attestation verify mentat-vX.Y.Z.tar.gz -R lipi4242/mentat
```

## Mire vonatkozik

Ez a repó csak a termék. Ami egy-egy telepítéshez tartozik (Telegram-bot token, Cloudflare-titkok,
ágens-tokenek, az admin példányfájlja), az nincs benne, és soha nem kerülhet bele. Ha mégis ilyet
találsz itt, ugyanígy, privátban jelezd.

Részenként a legfontosabbak:

- **Agy** (a gyökér): a telepítés a `.mentat/bin/` mappába tölti az eszközöket, és mindegyiket
  összeveti a `release.json` sha256-listájával, mielőtt bármi lefutna. Ha egy módosított fájl
  át tud jutni ezen, az ide tartozik.
- **Motor** (`engine/`): az `engine/sync-to.sh` másolja az ágens repójába. Írás a célrepón
  kívülre, vagy olyan csomag futtatása, amelynek a verziótartományát a motornak el kellene utasítania.
- **Flotta** (`fleet/`): a saját szervereden fut, és a megadott tokennel beszél a Telegram Bot
  API-val. A token kiszivárgása, parancs futtatása olyasvalakinek, aki nincs a híd engedélylistáján,
  vagy írás egy ágens saját fájljain kívülre.
- **Admin** (`admin/`): a saját Cloudflare-fiókodon fut. Adat olvasása vagy módosítása admin-kulcs
  nélkül, vagy ha egy ágens-token többhöz fér hozzá, mint a saját pluginja.

## Ismert korlátok

A szerep-őr (`MENTAT_ROLE`, `reference/bekotes/szerep_guard.py`) a véletlen hozzáférés ellen
véd, nem biztonsági határ. Egy szerep, amely szándékosan meg akarja kerülni, törölheti az ágens
`.mentat/` mappáját (vagy futtathat `git clean -fdx`-et), ami után az őr nem fut, vagy indíthat
egy beágyazott sessiont más szereppel (`MENTAT_ROLE=<másik> claude -p`). Az adat fizikai
elzárása (egy szerep csak azt látja, amit neki csatolnak) egy későbbi kiadás terve.
