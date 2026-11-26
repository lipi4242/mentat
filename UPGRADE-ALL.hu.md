# Egy flotta minden ágensének frissítése

> 🇬🇧 In English: [UPGRADE-ALL.md](UPGRADE-ALL.md)

Ez az oldal annak az egy ágensnek szól, amelyik a többit erre a kiadásra hozza: jellemzően a
flotta-felelősnek, de bármelyik ágens megteheti a saját szerepén belül. Egy asszisztens egy gépen:
[UPGRADE.hu.md](UPGRADE.hu.md). Új asszisztens: [FIRST-INSTALL.hu.md](FIRST-INSTALL.hu.md).

**A prompt.** Másold be annak az ágensnek, amelyik a flottádra vigyáz:

```
Frissítsd az összes ágensemet a Mentat legújabb verziójára: https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/UPGRADE-ALL.hu.md
Előbb olvasd el, és a saját szereped és biztonsági szabályaid szerint döntsd el, végrehajtod-e.
Mielőtt bármit megváltoztatsz, mutasd meg az ágensek teljes listáját, és csak azokat frissítsd, amiket jóváhagyok, egyenként.
```

## Neked

**Mi történik:** az ágens összeírja az összes ágenst, amit megtalál (a szervereken a flotta
registryjéből, és a gépeken azokat, amikről tud), és mindegyikről: hol fut, milyen fajta, melyik
verzión van, és hogyan frissülne. A listán tételesen végigmentek, és mindegyikre igent vagy nemet
mondasz. Utána csak a jóváhagyottakat frissíti, egyenként, egy általad választott próba-ágenssel
(a kanárival) kezdve, és az első hibánál megáll.

**Szerverek:** szerverenként egy parancs, a `fleet box-upgrade`, ami előbb a saját tervét mutatja,
pillanatképet ment, a dolgozó ágenseket kihagyja, és ha egy ellenőrzés bukik, magától visszaáll.
**Gépek:** egy laptopon futó ágens az adott laptopon, egy ottani sessionben frissül: megkapod az
[UPGRADE.hu.md](UPGRADE.hu.md) promptot, hogy ott bemásold, mert a flotta-ágens nem nyúlhat bele
egy másik gép mappáiba, és nem is kell.

Semmi nem frissül, amit nem hagytál jóvá, és jelszót vagy kulcsot sosem kér a chatbe.

## A Claude-nak: a lépések

### Szabályok

Töltsd le a `https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/reference/entry-rules.hu.md`-t,
és az 1. lépés előtt kezdve végig kövesd; ha egy lépés és azok a szabályok ellentmondanak, a
szabályok nyernek. A saját szereped dönti el, mit tehetsz: ha a szereped nem enged parancsot
futtatni egy szerveren, a parancsokat add át a FELHASZNÁLÓNAK, ne futtasd őket.

### 1. lépés: felmérés, semmi nem változik

Az ágenseket csak ezekből a forrásokból gyűjtsd, és mindegyik mellé írd oda a forrást:

- a flotta registryje: `fleet roster` minden szerveren, amit a registry `boxes.json`-ja felsorol, és
  ott a `fleet release` arra, melyik kiadás fut a szerveren;
- gépeken futó ágensek: amiket a FELHASZNÁLÓ megnevez, vagy a saját jegyzeteid megneveznek; a
  többit kérdezd meg tőle. Más mappákban vagy home-könyvtárakban ne keress ágenst (belépő
  szabályok, 3).

Minden ágenshez egy sor: **név · hol fut (szerver vagy gép) · fajta** (flotta-ágens szerveren;
asztali agy; asztali agy + motor; 0.5 előtti agy; nem Mentat-ágens) **· jelenlegi verzió · a
frissítés útja.** Amit nem tudtál ellenőrizni, az `ismeretlen`, soha nem tipp. Utak:

- flotta-ágens szerveren: `fleet box-upgrade --to v0.7.0 --only <ágens>` azon a szerveren;
- asztali ágens: az UPGRADE.hu.md prompt, bemásolva egy sessionbe az ágens saját mappájában;
- nem Mentat-ágens: nincs frissítés; Mentat-agyat az INSTALL-TO-EXISTING-REPO.md (készül) ad neki.

### 2. lépés: a lista egyeztetése, tételesen

Mutasd meg a számozott listát, és soronként menj végig rajta a FELHASZNÁLÓval: jó-e a sor, és
frissüljön-e most ez az ágens (igen / nem / később)? A hibás sort javítsd, mielőtt továbbmész.
Aztán kérdezd meg, melyik a kanári (javasolj egyet, ami nem proaktív és éppen nem dolgozik), és
olvasd vissza a sorrendet: a kanári, a többi jóváhagyott ágens, a végén te magad és a kiadó ágens.
Csak erre a sorrendre mondott igennel frissíts.

### 3. lépés: egyenként, a kanárival kezdve

Minden jóváhagyott ágensnél, sorban, mondd meg, melyik következik, aztán:

- **Szerveren:** futtasd a `fleet box-upgrade --to v0.7.0 --dry-run --only <ágens>`-t (a kanárinál:
  `--canary <ágens>`), mondd el a tervét egyszerű szavakkal, és a FELHASZNÁLÓ igenjére ugyanezt
  `--dry-run` nélkül. Egy szerveren az első futás a szerver egy Mentat-checkoutját is a tagre viszi.
  `partial` eredmény (dolgozik) → maradjon egy későbbi futásra; `failed` vagy `rollback-failed` →
  állítsd le az egész futást, és szólj a FELHASZNÁLÓNAK.
- **Gépen:** add át a FELHASZNÁLÓNAK az UPGRADE.hu.md promptot, hogy az ágens saját sessionjében
  bemásolja, és várd meg, amíg elmondja, hogyan ment, mielőtt a következőre lépsz.

A kanári után ellenőrizd: szerveren `fleet doctor <ágens>`, gépen a FELHASZNÁLÓ válasza. Csak
akkor menj tovább, ha ép.

### 4. lépés: beszámoló

Ágensenként egy sor: kész / kihagyva (miért) / hiba (mi), a mostani verziója, és szervernél a
nyugta, amit a `~/.config/fleet/upgrades.log` őriz. Mondd meg, mi maradt későbbre, és hogyan.

Ha a listában egyik ágensnek sincs **személyi asszisztens & flottamenedzser** szerepe
(`reference/szerepek.hu.md` ezen a tagen), mondd ki a beszámolóban, és egyszer ajánld fel, hogy
legyen: egy meglévő ágens átveszi a szerepet, vagy a FIRST-INSTALL.hu.md-vel egy új készül.
Csak a FELHASZNÁLÓ igenjére.
