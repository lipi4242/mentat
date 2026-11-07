<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png">
  <img alt="Mentat Engine, a Mentat része" src="assets/banner-light.png" width="100%">
</picture>

# Mentat Engine

[![Kiadás](https://img.shields.io/github/v/tag/lipi4242/mentat?label=kiad%C3%A1s)](https://github.com/lipi4242/mentat/tags)
[![Licenc](https://img.shields.io/badge/licenc-Apache--2.0-blue.svg)](../LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![HU | EN](https://img.shields.io/badge/nyelv-HU%20%7C%20EN-informational.svg)](README.md)

A motor a [Mentat](../README.hu.md) része, és vele együtt érkezik: a Mentat telepítése beállítja, ha kéred a reggeli összefoglalót és az emlékeztetőket.

A motor ütemezést ad a Mentat-kollégádnak. Elküldi a reggeli összefoglalót és a határidő-emlékeztetőket, amiket különben neked kellene kérned, és minden nyitott ügyet a listán tart, amíg le nem zárul.

- Minden reggel: mi késik, mi esedékes ma és a héten, az ügyeidből, a határidős teendőidből és a határidő-táblázataidból.
- Emlékeztető három nappal minden határidő előtt és aznap, fájlban vagy Telegramon, éjszaka csendben.
- A jóváhagyáshoz kötött üzenet csak akkor megy ki, ha egyezik vele, és egy elvégzett lépés összeomlás után sem ismétlődik.

Fejlesztőknek: a döntés sima Python, modellhívás nélkül, így ugyanabban a pillanatban mindig ugyanaz a terv születik, a munkát pedig az ágensed végzi. Asszisztensenként egy példány fut, tartós systemd- vagy cron-időzítővel, és a `setup --doctor` összeveti a telepített időzítőt azzal, amit a setup írna.

## Hozzáadás egy meglévő kollégához

A legegyszerűbb: kérd meg a Mentat-kollégádat, hogy adja hozzá a motort, ő futtatja a lépéseket. Kézzel: nyisd meg a Claude Code-ot a kolléga mappájában, és másold be:

```
Telepítsd a Mentat motort ebbe a repóba. Futtasd pontosan ezt:
  git clone --depth 1 --branch v0.5.0 https://github.com/lipi4242/mentat ~/src/mentat
  ~/src/mentat/engine/sync-to.sh . --pack cases
  python3 -m anytime_engine.selftest -q
Ha a ~/src/mentat már létezik, a klón helyett futtasd: git -C ~/src/mentat fetch --tags,
majd git -C ~/src/mentat checkout v0.5.0.
Utána kérdezd meg az időzónámat, és hogy hová menjenek az emlékeztetők (fájl vagy Telegram), és futtasd:
python3 -m anytime_engine.setup --tz <tz> --deliver <file|telegram> --lang hu, az igenem után --install-lal.
```

## Rendszeres feladat = ismétlődő todo

Ehhez a [Mentat Admin](../admin/README.md) todo pluginja kell. Nélküle az `anytime_todo` csomag nem csinál semmit, és a rendszeres feladatok maradnak ott, ahol most vannak (cron-sor vagy concern).

Ha az ágensnek valamit rendszeresen meg kell csinálnia (heti emlékeztető, reggeli kör, havi ellenőrzés), az egy ismétlődő todo a Mentat Admin todo listájában, nem cron-sor és nem saját concern. Az `anytime_todo` csomag minden tickben lekéri az ágensnek kiosztott, esedékes todókat, és a terv elmondja az ágensnek, mi a dolga: a todo címe és leírása maga az utasítás. A todót az ágens csak akkor zárja le, amikor a munka tényleg megtörtént; ismétlődő todónál a lezárás a következő dátumra viszi, tehát az időzítést a todo végzi. Amit nem tud megcsinálni, azt nyitva hagyja, és megjegyzésben leírja, miért.

Cron vagy concern akkor kell, ha a feladatot külső esemény indítja (új levél, webhook, naptárváltozás), vagy minden tickben determinisztikus számítás kell hozzá. Minden más fix ütemű feladat todo.

Egy meglévő cron-feladat átköltöztetése: hozd létre a todót (cím, teljes utasítás a leírásban, `repeat_rule` az ütemhez, következő dátum, ha számít az óra, `due_time` és `tz`, gazdának vagy felelősnek az ágens), nézd meg `python3 -m anytime_todo.cli list`-tel, hogy megjelenik, és ugyanabban a lépésben töröld a régi cron-sort, hogy ne fusson kétszer. A beállítás (`TODO_API`, `TODO_HANDLE`, `TODO_TOKEN_FILE`) és a részletek: [GUIDE.md](GUIDE.md).

## Teendő + backlog

Ugyanez a csomag az ágens oldala az Admin munkatárában: teendők, ügyek (egyszeri folyamat, céllal) és elfogadási feltételekkel ellátott backlog-tételek, amelyeket az egyik ágens PM-ként kiad, a másik fejlesztőként átvesz. A `python3 -m anytime_todo.cli me | ball | changes | task | case | item` parancsok fedik le, az óránkénti `todo_labda` concern pedig csak akkor szól, ha új dolog vár az ágensre, vagy tételt adtak ki neki. A lépések az agy `backlog` skilljében vannak.

## Tovább

[Útmutató (angolul)](GUIDE.md) · [Kiadási jegyzetek (angolul)](../CHANGELOG.md) · [Minden változás képességenként](../CAPABILITY-LOG.hu.md) · [Biztonság](../SECURITY.hu.md) · [Apache-2.0](../LICENSE)
