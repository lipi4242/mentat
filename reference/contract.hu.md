# A megbeszélt feladat fájlban, ellenőrizve, mielőtt kimegy

**Mikor:** a FELHASZNÁLÓ listát, exportot, riportot, hírlevelet, meghívót vagy bármilyen több embernek szóló üzenetet kér, vagy ismétlődő kimenetet. Ami megbeszéltetek (oszlopok, mi marad ki, ki kapja, a dátumok, az alapértékek), az fájlba kerül, nem csak a chatbe, és a kimenetet ehhez méred **mielőtt** kimegy, és **mielőtt** késznek mondod. A „lefutott” vagy a „HTTP 200” nem kész.

Eszközök (a telepítő hozza; ha nincs `.mentat/bin/mentat_contract.py`, futtasd újra a telepítés 2. lépésének letöltését): `python3 .mentat/bin/mentat_contract.py` és `python3 .mentat/bin/mentat_accept.py`. A megállapodás helye `<agy>/contracts/<azonosító>.json`, az aggyal együtt commitolódik.

## Lépések

1. **Előbb a homályos szavak.** „Jövő hét”, „a vendégek”, „mindenki”: kérdezz, aztán abszolút dátumot írj időzónával. Relatív dátum: `python3 .mentat/bin/mentat_dates.py "<a kifejezés>" --tz <tz>` — 0: megvannak a dátumok, 3: felsorolja az értelmezéseket, ezekről kérdezz, 1: kérd el a dátumokat (`2026-11-02` – `2026-11-08`, `Europe/Budapest`) és pontos szűrőt. Az eszköz elutasítja a relatív dátumot és az időzóna nélküli ablakot.
2. **Tervezet:** a javaslatot JSON-ba írd, és futtasd: `mentat_contract.py draft <azonosító> --file javaslat.json` (vagy `--file -` stdinről). Kiírja a visszaolvasást; add tovább a saját szavaiddal, egy üzenetben, és kérj igent.
3. **Jóváhagyás csak az igenjére:** `mentat_contract.py approve <azonosító> --quote "<a szavai, szó szerint>" --version <N>` (N = a visszaolvasott verzió). Idézet nélkül semmi nem hagyódik jóvá (2-es kód).
4. **Minden írás előtt:** `mentat_contract.py check-write <azonosító> [--fields a,b] [--recipients x@…,y@…] [--dates ÉÉÉÉ-HH-NN,…]` — 0: belefér, 1: nem fér bele (megnevezi, mi), 2: nincs jóváhagyott megállapodás.
5. **Kiküldés és a „kész” előtt:** `mentat_accept.py <azonosító> <kimenet> [--recipients FÁJL]`. ZÖLD (0): az egy sorát mondd el a FELHASZNÁLÓNAK. PIROS (1): nem megy ki; javítsd, futtasd újra. NEM ELLENŐRIZHETŐ (2): nincs jóváhagyott megállapodás, vagy olvashatatlan a kimenet; kezeld pirosként.
6. **A FELHASZNÁLÓ változtat:** új tervezet. A `mentat_contract.py diff <azonosító> --file uj.json` előbb megmutatja a változást (3-as kód = lényegi). Lényegi változásnál új verzió lesz, ami új igent kér; igen nélkül csak a `notes` változhat. A `show <azonosító> [--json]` a mostani állapotot írja ki.

## A javaslat

```json
{
  "goal": "A november 7-i vacsora visszaigazolt vendégei, a cateringesnek.",
  "fields": ["name", "email", "date"],
  "exclude": {"fields": ["phone"], "records": [{"status": "declined"}], "values": ["+36 1 333"]},
  "records": {"source": "data/guests.csv", "key": "email", "where": {"status": "confirmed"}},
  "audience": {"who": "a visszaigazolt vendégek", "from_records": "email", "visibility": "hidden"},
  "window": {"start": "2026-11-02", "end": "2026-11-08", "tz": "Europe/Budapest", "field": "date"},
  "defaults": {"paid": ""},
  "notes": "szabad szöveg"
}
```

Csak a `goal` kötelező. A `checks` a többiből adódik: pontosan ezek az oszlopok; semmi kizárt nincs benne; minden dátum az ablakon belül, a `tz` szerint olvasva; pontosan a `source` azon rekordjai, amelyek a `where`-nek és az ablaknak megfelelnek; címzett csak az `allowed` listából (cím vagy `@domain`) és a jogosult rekordok `from_records` oszlopából; a címzettek nem látják egymást. A `checks`-et csak akkor sorold fel magad, ha egyet elhagysz, és ezt mondd ki a visszaolvasásban.

## Tervezett küldés

Küldésnél egy küldési tervet ellenőrizz (JSON): levélnél `{"to": [...], "cc": [...], "bcc": [...], "visibility": "hidden"}`, naptármeghívónál `{"guests": [...], "guestsCanSeeOtherGuests": false}`. Rejtett: mindenki `bcc`-ben, a `to`+`cc`-ben legfeljebb egy cím, vagy a `guestsCanSeeOtherGuests` kifejezetten `false` (a naptár alapból megmutatja a vendéglistát). Emberekhez menő fájl: `mentat_accept.py <azonosító> lista.csv --recipients cimzettek.txt`.

## Amit nem csinál

A kapott fájlt vagy tervet ellenőrzi; nem küld, és nem állítja meg azt a küldést, amelyik megkerüli. Pontosan azt a fájlt futtasd rajta, ami kimegy. A motor (a cases csomag) magától lefuttatja ezt az ellenőrzést, mielőtt kiküld egy listát vagy emlékeztetőt, amelynek ügye, teendője vagy CSV-táblája `contract: <azonosító>`-t visel; egyetlen emlékeztetőt `--part`-tal ellenőriz (a megbeszélt halmaz egy része: a hiányzó rekord rendben van, minden más nem). Amit magad küldesz, azt magad ellenőrzöd.
