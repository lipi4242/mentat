# A Mentat használata

Milyen vele egy átlagos hét, hol futhat, és milyen helyzetekre szokták beállítani. A háttér (hogyan épül fel a memória) a [how-it-works.hu.md](how-it-works.hu.md)-ben van.

## Egy átlagos nap

Nyisd meg a Claude Code-ot az ágens mappájában, és beszélj vele úgy, mint egy kollégával, aki már egy ideje veled dolgozik. Parancsokat nem kell tudnod. Amit a leggyakrabban mondanak neki, területenként:

- Memória és tudás. „Jegyezd fel: ...”, vagy egy hosszú, rendezetlen üzenet arról, ami a fejedben jár. Előbb szó szerint elmenti a szöveget, utána a helyére teszi a benne talált személyeket, teendőket, döntéseket és ügyeket. Az „Úgy döntöttünk, hogy ...” külön polcra kerül: ha később olyat kérsz, ami ellentmond neki, emlékeztet a dátumra és az okra, és te felülbírálhatod.
- Proaktivitás és ütemezés. „Mi esedékes a héten?” A jegyzeteiből válaszol, időponttal és az érintettekkel, és minden sornál megmondja, melyik jegyzetből vette. A „Minden hónap 10-én szólj, hogy fizessem be az X-et” ügy lesz; ha a motor is telepítve van, az emlékeztető kérés nélkül megjön a reggeli összefoglalóban.
- Munkavégzés és projektek. A „Csináljunk egy kis eszközt, ami ...” a `projects/` alatt kap helyet. Egy nagy, nem teljesen tisztázott kérés rögzített eljáráson megy át: előbb kérdések, aztán elfogadási feltételek, utána a munka.
- Kapcsolat a külvilággal. „Hívd meg hármukat a csütörtöki megbeszélésre”, „oszd meg a táblázatot ...-val”: a Google saját könyvtárán át, rejtett vendéglistával, az egyeztetett címzettekhez mérve.
- Biztonság és kontroll. „Küldd el hármuknak a nyitott tételek listáját.” Listánál, exportnál és többeknek szóló üzenetnél előbb leírja, miben egyeztetek (mely sorok, mi marad ki, ki kapja, mely napokra), és megvárja az igenedet. Küldés előtt a kész anyagot ehhez méri; ha valami nem egyezik, nem megy ki. A nehezen visszacsinálható lépések előtt is rákérdez: ha a mappáján kívül olvasna vagy törölne, ha force-pusholna, ha közvetlenül adatbázisba írna, vagy ha az e-mail-címedet egy nem a tiédnek számító szolgáltatáshoz küldené. Ha nincs kitől kérdeznie (ütemezett futás egy szerveren), ezeket nem csinálja meg.
- Működés és rugalmasság. „Van már erre valami?” Mielőtt bármi újat építene, megnézi, mit tud már a csomag és a saját projektjeid (`where --find`). „Mi van itt telepítve?” A `status` a `mentat.json`-ból válaszol.

## Hol futhat

Az agy egy privát git repó, ezért ugyanaz az ágens több helyen is élhet. Ezeket a felállásokat használjuk és támogatjuk:

| Felállás | Mi kell hozzá | Mire jó |
|---|---|---|
| A saját gépeden | Claude Code (asztali alkalmazás vagy terminál); Windowson a Git for Windows is | Kezdésnek. Nem technikai felhasználónak is működik, a telepítés néhány perc. |
| Több gépen | Ugyanaz a privát repó (például GitHubon) mindegyiken klónozva; az ágens gitbe ment, a másik gépen kezdés előtt lehúzod a változásokat | Egy embernek laptoppal és asztali géppel, vagy egy ágensnek, aki több családi gépen segít. |
| Szerveren, folyamatosan | Egy Linux szerver a [flotta](https://github.com/lipi4242/mentat/tree/v0.6.0/fleet) futtatójával; Telegram a beszélgetéshez | Ütemezve dolgozik, és a telefonodon is válaszol, akkor is, ha a géped ki van kapcsolva. |
| Több session egy gépen | Több Claude Code session ugyanabban a mappában; ha kell, sessionönként egy szerep (`MENTAT_ROLE=<szerep> claude`) | Két dolgon egyszerre dolgozni. A sessionök egy közös hosszú távú memóriát használnak. |
| Telefonról vagy webről | `/rc` (remote control) a sessionben | A gépen elindított session folytatása máshonnan. |

Egy szabály minden felállásra érvényes: a motor ütemezése csak egy helyen fusson. Ha két gép is tickel ugyanannak az ágensnek, az emlékeztetők kétszer mennek ki. Szerveren ezt a flotta tartja kézben; saját gépen a `setup --doctor` megmutatja, mi van telepítve.

## Tipikus helyzetek

- Egy idős szülő számítógépének segítése. Az ágens az ő gépén, az ő nyelvén fut, ismeri a számára fontos embereket és fiókokat, és minden kockázatos lépés előtt kérdez. A család egy másik tagja egy másik gépről ugyanezt az ágenst éri el.
- Egy régi gépből kis szerver. A flotta futtatójával éjjel-nappal futtatja az ágenst, és Telegramon beszélsz vele.
- Egyszemélyes vállalkozás. Ügyek az ismétlődő kötelezettségekre (számlák, megújítások, táblázatban tartott határidők), reggeli összefoglaló, és egy ágens, amely a [bekötés](bekotes/BEKOTES.hu.md) szerint átveszi a vállalkozás meglévő repóit és jegyzeteit.
- Kis weboldal vagy eszköz egy klubnak, családnak, csapatnak. Az ágens megépíti, kiteszi a Cloudflare-re egy bejelentkezés mögé, amelyen csak az általad megnevezett emberek jutnak át, és úgy ellenőrzi, ahogy ők látni fogják. Élesbe csak az igenedre megy ([publish-web.hu.md](publish-web.hu.md)).
- Közös naptár vagy körlevél, amelyből nem szivároghat cím. A meghívó és a csoportos levél rejtett vendéglistával megy ki, a Google saját könyvtárán át, az egyeztetett címzettlistához mérve ([google.hu.md](google.hu.md)).

## Új verzióra lépés

Minden kiadásnak van [CHANGELOG](../CHANGELOG.md)-bejegyzése, benne a „You need to” résszel, ha tőled is kell valami, és van [képesség-naplója](../CAPABILITY-LOG.hu.md), amely megmondja, melyik képesség hogyan változott. Add oda az ágensnek az új kiadás CHANGELOG-ját, és kérd meg, hogy végezze el a „You need to” lépéseit. Amíg ezt nem teszed meg, a telepített ágensen semmi nem változik, mert a telepítés egy kiadási taghez van kötve.
