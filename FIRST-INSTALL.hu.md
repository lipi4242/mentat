# A Mentat első telepítése

> 🇬🇧 In English: [FIRST-INSTALL.md](FIRST-INSTALL.md)

Ez az oldal egy üres mappába rendez be új asszisztenst. Már van egy (bármilyen régi Mentat-agy)? Az [UPGRADE.hu.md](UPGRADE.hu.md) kell. Egy egész ágens-flotta: [UPGRADE-ALL.hu.md](UPGRADE-ALL.hu.md).

Ezt az oldalt ketten olvassák: te, és a Claude, amelyik telepít. Az első fele neked szól. A
második fele az a lépéslista, amit a Claude követ, így előre látod, mit fog csinálni.

## Neked

Ami kell: Claude Desktop (a Code fülével) vagy Claude Code, fizetős Claude-előfizetéssel. Más
nem. Ha a gépedről hiányzik a git vagy a Python, a Claude szól, és az igenedre feltelepíti.

**Erősen ajánljuk: az első asszisztensed legyen a személyi asszisztensed és flottamenedzsered.**
Ez egy olyan ágens, amely minden új projektben, ötletben vagy feltárásban egyszerre a fejlesztőd,
a product managered és a kiadó ágensed, mindegyikhez a saját agyát használja, és közben a többi
ágensedre is vigyáz. Miért:

- **egy agy minden projektedhez:** amit az egyikben megtanul, a következőben már tudja;
- **gyors fejlesztés:** egy új ötletnél nincs átadás ágensek között, még aznap elindul;
- **egyben tartja a flottát:** ha később több ágensed lesz, egyikük mindet ismeri, frissíti
  ([UPGRADE-ALL.hu.md](UPGRADE-ALL.hu.md)), és észreveszi, ha valamelyik elnémul.

A szerep, a feladatai és a Szerep önképe a szerep-térképben van: `reference/szerepek.hu.md`.
Választhatsz más szerepet is; a Claude rákérdez.

Mit csinálj:

1. Nyisd meg a Claude Desktopot, menj a Code fülre, és válassz egy új, üres mappát (például
   `Asszisztens`). Claude Code-ban: hozd létre a mappát, nyiss benne terminált, és írd be: `claude`.
2. Másold be ezt:

```
Telepítsd nekem a Mentat asszisztenst ebbe a mappába.
A lépések itt vannak: https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/FIRST-INSTALL.hu.md
Minden lépés előtt mondd el, mit csinálsz.
```

A Claude ezután megkérdez pár dolgot (a neved, hogyan hívd), berendezi a mappát, és röviden
megismerkedik veled. A végén egy második, vadonatúj Claude-session ellenőrzi, hogy emlékszik-e
mindkét névre. Ez néhány perc.

Mi fut a gépeden: a Claude ebből a GitHub-repóból (ebből a kiadásból) letölti a Mentat saját
eszközeit a mappa `.mentat/bin/` alá, minden fájlt összevet a kiadás ujjlenyomat-listájával
(sha256), és csak utána futtatja őket.

Mihez nyúl: csak ehhez a mappához (ha kéred a motort, a Mentat ezen kiadása egyszer a saját
mappádba kerül, a `src/mentat` alá, és a motor onnan másolódik ide). Két kivétel van, mindkettőre előbb rákérdez: a git vagy a
Python telepítése a rendszered saját telepítőjével, és Windowson utána a Claude újraindítása.
Jelszót, kulcsot vagy kódot sosem kér a chatbe.

**Később, ha kéred: teendők + backlog (Mentat Admin).** Nem kötelező webes felület, ahol te és
az ágenseid teendőket, hosszabb ügyeket és elfogadási feltételekkel ellátott backlogot vezettek,
egy fizetős feladatkezelő helyett. A gépeden vagy a saját Cloudflare-fiókodon fut. Az
[Admin gyorsindításával](admin/README.md#quickstart-look-at-it-on-your-machine-about-a-minute-and-a-half)
kezdd, utána [kösd be az ágensedet](admin/docs/plugins/todo/INSTALL.md) (a két leírás angol).
A saját gépeden az `npm run connect -- --local` (az `admin/worker` mappában) háttérszolgáltatásként
futtatja tovább a terminál bezárása után is, Linuxon és macOS-en. Windowson ilyen szolgáltatás
nincs: ott az Admin csak addig fut, amíg a terminálja nyitva van.
Semmi nem települ belőle, amíg nem kéred.

## A Claude-nak: a lépések

### Szabályok a telepítés egészére

Töltsd le a `https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/reference/entry-rules.hu.md`-t, és az 1. lépés előtt kezdve az egész telepítés
alatt kövesd; ha egy lépés és azok a szabályok ellentmondanak, a szabályok nyernek. Ehhez az
oldalhoz két külső helyet neveznek meg: az 1. lépés rendszertelepítőit (winget, `xcode-select`,
apt/dnf), csak a githez és a Pythonhoz; és ha a FELHASZNÁLÓ kéri a motort, az egy Mentat-klónt
ezen a tagen.

### Az 1. lépés előtt: az első asszisztens szerepe

Ha ez a FELHASZNÁLÓ első Mentat-asszisztense, nagyon egyértelműen ajánld, hogy a **személyi
asszisztens & flottamenedzser** legyen (az okok a „Neked” részben: egy agy minden projekthez,
gyors fejlesztés, egyben tartja a flottát); a meghatározása a szerep-térkép,
`reference/szerepek.hu.md` ezen a tagen: onnan olvasd, ne fogalmazd újra. Egyszer kérdezz rá, a 2. lépés kérdéseivel együtt; a
FELHASZNÁLÓ más szerepet is választhat. A választást a bemutatkozó beszélgetésben (2. lépés, 3.)
rögzítsd az ágens szerepeként.

### 1. lépés: a git és a Python ellenőrzése

Futtasd: `git --version` és `python3 --version`. Windowson hiányzónak számít az a `python3`,
amelyik azt írja, hogy "Python was not found", vagy a Microsoft Store-t nyitja meg. Ha mindkettő
válaszol (Python 3.9 vagy újabb), jöhet a 2. lépés.

Ha valami hiányzik, mondd meg a FELHASZNÁLÓNAK, mi az, mi az egy parancs, és hogy a parancs a
nevében elfogadja a csomag licencét; az igenje után futtasd. Windowson nevezd meg a
Python-csomagot: a `9NQ7512CXL7T` a Microsoft Store-ból a Python Install Manager.

| Rendszer | git | Python |
|---|---|---|
| Windows (PowerShell) | `winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements` | `winget install 9NQ7512CXL7T -e --accept-package-agreements --accept-source-agreements` |
| macOS | `xcode-select --install` (megnyílik egy ablak: Telepítés; a python3-at is hozza) | ugyanaz |
| Linux | a FELHASZNÁLÓ terminálban futtatja: `sudo apt install -y git python3` (Fedora: `dnf`) | ugyanaz |

- Windows: a Windows megkérdezheti, hogy "Engedélyezi, hogy ez az alkalmazás módosításokat hajtson
  végre?". Ez a telepítő, a FELHASZNÁLÓ az Igenre kattint. Utána a Claude-ot újra kell indítani,
  hogy megtalálja a Git Basht: kérd meg a FELHASZNÁLÓT, hogy zárja be teljesen a Claude-ot, nyissa
  meg újra ugyanebben a mappában, és másolja be ugyanazt a három sort. Az 1. lépéstől kezded újra,
  és most átmegy. Az ezutáni első `python3 --version` egy percig is eltarthat, mert letölti a
  Python futtatókörnyezetét.
- Windows winget nélkül: add meg a FELHASZNÁLÓNAK a hivatalos oldalakat,
  `https://git-scm.com/download/win` és `https://www.python.org/downloads/windows/`.
- macOS: várd meg, amíg az ablak jelzi, hogy kész, aztán ellenőrizz újra.

### 2. lépés: az agy berendezése

Töltsd le a
`https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/reference/initialization.hu.md`
fájlt (angol nyelvű FELHASZNÁLÓNÁL: `initialization.md`), és kövesd a végéig. Röviden ezt csinálja:

1. egy üzenetben felteszi a pár valódi kérdést (nevek, megszólítás, kér-e emlékeztetőket a
   motortól);
2. letölti a kiadás eszközeit a `.mentat/bin/` alá, és lefuttatja a `mentat_init.py`-t. Ez előbb
   minden letöltött fájlt összevet a `release.json` sha256-listájával, és eltérésnél megáll;
   utána jönnek a gépi ellenőrzések: git, Windowson Git Bash, `python3` ott, ahol a Claude Code hookjai
   futtatják, a Claude Code verziója, a szabad hely. Ha `MENTAT-INIT HIBA: …` sorral áll meg, az
   az egy dolog a feladat: mondd el a FELHASZNÁLÓNAK, javítsd (ha telepít valamit, az igenjével),
   és futtasd újra — kivéve, ha a letöltés nem egyezik a kiadással: akkor csak azt tedd, amit az
   üzenet mond (azt sem te, sem a FELHASZNÁLÓ nem javíthatja vagy engedheti el, és a Mentat részeit
   semmi nem pótolja);
3. lefut a rövid ismerkedés, elmenti az első commitot, és felajánlja a távvezérlést (`/rc`).

Semmi nem kerül fel sehová, és távoli repót sem ad hozzá.

### Amit ne ajánlj fel

- A motor asztali gépen háttér-időzítő nélkül települ: akkor dolgozik, amikor a FELHASZNÁLÓ kéri
  ("mi esedékes?"), és minden új Claude-session egyszer bepótolja. macOS-en és Linuxon a
  FELHASZNÁLÓ később hozzáadhatja az ütemezőt (`python3 -m anytime_engine.setup --tz <időzóna>
  --install`); onnantól óránként fut, amíg a gép ébren van. Windowson nincs háttér-ütemezés. Ezt
  mondd meg, ha a motort választja.
- A flotta (mindig futó ágens, Telegram) Linux-szerverre való, nem erre a gépre. Itt ne ajánld fel.
  Ha a FELHASZNÁLÓ rákérdez: `https://github.com/lipi4242/mentat/tree/v0.7.0/fleet`.
