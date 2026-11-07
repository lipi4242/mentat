# Képesség-napló

A `capability-log.json`-ból generált fájl, kézzel ne írd.

## 0.5.1 (még nincs kiadva)

### Proaktivitás és ütemezés

- mentat-todo: a backlog-parancs a szerver minden ágensének. A szerver minden ágense megkapja a backlog-parancsot a motor másolata nélkül; az ágens neve az egységéből jön. (Bővült: `engine.todo`)

### Működés és rugalmasság

- Egy paranccsal frissíthető a szerver. A fleet box-upgrade --to vX.Y.Z tervet készít, pillanatképet ment, előbb egy kanári ágenst frissít, kihagyja a dolgozó ágenseket, ellenőriz, és hiba esetén magától visszaáll. (Bővült: `fleet`)
- Kevesebb téves riasztás a szerveren. A telepítés nem hibázik tévesen újraindításkor, a lemaradt híd teendő, nem hiba, és az OOM-védelem segédprogramja a repóban van. (Javult: `fleet`)

## 0.5.0 (még nincs kiadva)

### Proaktivitás és ütemezés

- Teendő + backlog: az ágensek átadják egymásnak a munkát. A teendők, az ügyek és a backlog-tételek egy tárban élnek az Adminban. A PM-ágens mérhető elfogadási feltételekkel ad ki egy tételt, a fejlesztő átveszi, és minden feltételhez bizonyítékkal jelent, a PM pedig feltételenként fogad el vagy utasít vissza. Minden ágens látja, kinél a labda. (Bővült: `engine.todo`)

### Munkavégzés és projektek

- Teendő + backlog: az ágensek átadják egymásnak a munkát. A teendők, az ügyek és a backlog-tételek egy tárban élnek az Adminban. A PM-ágens mérhető elfogadási feltételekkel ad ki egy tételt, a fejlesztő átveszi, és minden feltételhez bizonyítékkal jelent, a PM pedig feltételenként fogad el vagy utasít vissza. Minden ágens látja, kinél a labda. (Új: `backlog`)

### Működés és rugalmasság

- Egy repó, egy telepítés. Az agy, a motor, a flotta és az admin most egy repóban él. A kiadás tagjén egyetlen klón adja a motort és a flottát, és a flotta pluginja is innen települ. (Javult: `mentat.init`, `fleet`)

## 0.4.0 (még nincs kiadva)

### Proaktivitás és ütemezés

- A rendszeres feladat ismétlődő todo. Az ágens esedékes teendői a Mentat Admin todo listájából minden tickben megérkeznek, és a todo csak az elvégzés után zárul. Ehhez a Mentat Admin todo plugin kell, ami még nem nyilvános. (Új: `engine.todo`)
- Kifelé-tartás. Amíg a tartás él, minden tick próbafutás, és semmi nem megy ki, legfeljebb 24 óráig. (Javult: `engine.core`)
- A csomagok a 0.4-es motorra lépnek. A beépített csomagok >=0.4,<0.5-öt deklarálnak; a 0.4-nél véget érő saját csomag tartományát tágítani kell. (Bővült: `engine.core`)

### Biztonság és kontroll

- Az identitás-kapu csak valódi szivárgás-veszélynél kérdez. Csak a parancs hálózatra menő része számít; a saját GitHub-fiókod akkor számít a tiédnek, ha a GitHub igazolja a belépést. (Javult: `guard`)
- Csak te döntöd el, mi számít a tiédnek. Az ágens által írható fájl, egy ssh-cél vagy egy belső hálózati cím már nem teszi a tiéddé a helyet; csak a jóváhagyott listád és a localhost. (Javult: `guard`)

## 0.3.1 (még nincs kiadva)

### Memória és tudás

- A bekötés kevesebbet olvas. A leltár nem tölti le a kizárt fájlokat, egész mappa kizárható, és a bekötést az első sessiontől felajánlja. (Javult: `takeover`)
- A „mi esedékes” megmondja, mikor és ki. Az esedékes tételeknél ott az időpont és az érintett személy. (Javult: `brain.due`)
- Kevesebb néma feltételezés. Változott mezőlistát újra visszaolvas, és egy ügy dátumának vagy állapotának átírása előtt elolvassa a jegyzetét és feltételeit. (Javult: `brain.new`)
- A meglévő AGENTS.md megmarad. Ha a mappában már van AGENTS.md, a Mentat a szövegedet változatlanul hagyja, és a saját szakaszait a végére írja. (Javult: `takeover`)

### Proaktivitás és ütemezés

- A status és a motor-sor igazat mond. A status nem ajánlja a még ki nem adott admint, és a kezdő lépés a motort az ügycsomaggal telepíti. (Javult: `engine.cases`)
- Határidők közvetlenül táblázatból. Egy CSV-ben tartott határidőlistából saját kód nélkül lesz reggeli összefoglaló és emlékeztető. (Új: `engine.csv_deadlines`; Bővült: `engine.cases`)
- setup --doctor. Összeveti a telepített időzítőket azzal, amit a setup írna, és soronként mutatja a kézi átírást. (Bővült: `engine.schedule`)
- Gyorsabb motor-telepítés. A setup időzítő nélkül is rögzíti a beállítást, a kézzel írt due: dátumot is érti, és a telepítés a kiadási tagről klónoz. (Javult: `engine.schedule`, `engine.cases`)
- Az ütemezés megjegyzi, mit kell tartalmaznia a kimenetnek. A setup --expect eltárolja, mit kell tartalmaznia minden ütemezett üzenetnek (például a hívandók nevét), és rákérdez, ha hiányzik; az agy ellenőrzései innen olvassák. (Bővült: `engine.schedule`)

### Munkavégzés és projektek

- A „jövő hét”-et megkérdezi, nem találgatja. Az időkifejezésből a te időzónádban dátum lesz; ha kétféleképp érthető, megkérdez. (Új: `dates`)

### Kapcsolat a külvilággal

- Google egy eszközön át. A meghívó, a levél, a megosztás és a táblázat egy eszközön megy át, biztonságos alapértékekkel, előbb a megállapodáshoz mérve. (Új: `google.auth`, `google.calendar`, `google.gmail`, `google.drive`, `google.sheets`)
- Eszközök weboldal kitételéhez. Úgy ellenőrzi az oldalt, ahogy te látod, csak az igenedre teszi élesbe, Cloudflare Access-t tesz elé, és a tokent lépésenként hozza létre. (Új: `web.check`, `web.deploy`, `cf.token`; Javult: `web.publish`)
- Helyi oldal, ami nem akasztja meg a beszélgetést. A gépeden futó oldal, előnézet vagy fejlesztői szerver a háttérben indul; az ágens megnézi, hogy megnyílik, megadja a címét, és egy óra után magától leáll. (Új: `web.local`)
- A kulcs rejtett űrlapba kerül, nem a chatbe. Ha egy szolgáltatásnak kulcs kell, egy kis helyi űrlapba illeszted, és a projekt privát fájljába mentődik. A chatbe már beírt kulcsot az ágens azonnal elmenti, és javasolja, hogy készíts újat. (Bővült: `web.local`)
- Élesítés előtt a Cloudflare-token ellenőrzése. Telepítés előtt az ágens megnézi, megvan-e a tokenben minden jog, ami ehhez a projekthez kell, és megnevezi, mi hiányzik és hol javítható; utána ellenőrzi, hogy az oldal bejelentkezést kér. A környezetben beállított Cloudflare API-átjáró is működik. (Javult: `web.publish`)

### Biztonság és kontroll

- Az őr az első sessiontől működik. A munkamappán kívüli olvasásra és a veszélyes lépésekre rákérdez, és tilt, ha nincs kitől kérdeznie; ha maga az őr nem tud futni, a hívás nem megy át. (Új: `guard`)
- Közvetlen adatbázis-írás csak veled. A közvetlen adatbázis-írás a te igenedre vár, és tilt, ha nincs kitől kérdeznie. (Bővült: `guard`)
- A címed nem megy harmadik félhez. Ha egy hálózati hívás a te e-mail-címedet vinné egy nem a tiédnek számító helyre, rákérdez, felügyelet nélkül pedig tilt. (Bővült: `guard`)
- Az őr a képességfát is őrzi. Új kód, szolgáltatás, ütemezés vagy csomag előtt előbb meg kell nézni, mi létezik már. (Bővült: `guard`)
- A megállapodás fájlban él, és kiküldés előtt ellenőrzött. A listát, exportot és csoportos üzenetet a jóváhagyott megállapodáshoz méri; ha piros, nem megy ki. (Új: `contract`, `accept`)
- Eszközök weboldal kitételéhez. Úgy ellenőrzi az oldalt, ahogy te látod, csak az igenedre teszi élesbe, Cloudflare Access-t tesz elé, és a tokent lépésenként hozza létre. (Új: `cf.access`)
- Kevesebb néma feltételezés. Változott mezőlistát újra visszaolvas, és egy ügy dátumának vagy állapotának átírása előtt elolvassa a jegyzetét és feltételeit. (Javult: `contract`)
- Semmi végleges nem megy ki látatlanban. Mielőtt valami kimegy, rögzül vagy létrejön máshol, az ágens teljes egészében felolvassa, minden kötelező mezővel együtt. Akkor megy ki, ha a megmutatott rövid kóddal válaszolsz, és utána az ágens megnézi, mi érkezett meg. (Új: `final`)
- A technikai lépéseket az ágens maga végzi. Nem kér tőled parancsfuttatást vagy fájlszerkesztést, amit maga is meg tud csinálni; rád csak az marad, amihez ember kell, például a bejelentkezés, a fizetés vagy a kulcs beírása az űrlapba. A Telegramos ágensek is így dolgoznak. (Javult: `guard`)
- Az ütemezett üzenetet küldés előtt ellenőrzi. A megállapodáshoz kötött üzenet nem megy ki, ha nem egyezik vele. (Bővült: `accept`)
- Az identitás-kapu flotta-plugin hookként. A box minden ágense ugyanazt az ellenőrzést kapja, mielőtt az e-mail-címed harmadik félhez menne. (Bővült: `guard`)

### Működés és rugalmasság

- Telepítés egy hívással. Az agyat, az őrt, a mentat.json-t, a git-beállítást és a motort egyetlen parancs telepíti, a végén önellenőrzéssel. (Új: `mentat.init`)
- Telepítés három sorral. Egy háromsoros prompt a Claude Desktopban vagy a Claude Code-ban az INSTALL.md-re irányítja az ágenst, amely minden lépést előre kimond; a hiányzó gitet vagy Pythont az igenedre telepíti. (Bővült: `mentat.init`)
- A telepítő futtatás előtt ellenőrzi, amit letöltött. A release.json minden letöltött fájlhoz hasht ad, és a telepítés megáll, ha a letöltés hiányos, kevert vagy megváltozott. (Javult: `mentat.init`)
- Windowsra figyelő előellenőrzés. Windowson a telepítés az elején megáll, és megadja az egysoros javítást, ha hiányzik a Git Bash vagy egy működő python3. (Javult: `mentat.init`)
- A telepítő elmondja, mit talált. Felsorolja, mi volt már a mappában és mi került az első commitba; a te nem commitolt változásaidhoz nem nyúl. (Bővült: `mentat.init`)
- Az őr a képességfát is őrzi. Új kód, szolgáltatás, ütemezés vagy csomag előtt előbb meg kell nézni, mi létezik már. (Bővült: `brain.where`)
- Ami már megvan, mielőtt építenél. A where --find megkeresi, mit tud már a csomag és a saját beállításod; a --decide rögzíti a döntést; a --map kirajzolja a fát. (Bővült: `brain.where`)
- A képességfa referenciaként, és a flottának. A where --map --html egy barátságos oldalon mutatja, mit kapsz és mit tud az ágens; a where --export szűrt képet ad a flotta többi ágensének. (Bővült: `brain.where`)
- A képességfa naprakészen tartja magát. Lejárati idős valódi próbák mutatják a hibás képességet; a nap első lekérdezése elmondja, mi változott. (Javult: `brain.where`)
- A modellváltó kimondja, mi megy ki. Átváltás előtt elmondja, hogy minden, amit olvas, a másik szolgáltatóhoz megy, és kéri az adatvédelmi beállítást. (Javult: `mentat.model`)
- A status és a motor-sor igazat mond. A status nem ajánlja a még ki nem adott admint, és a kezdő lépés a motort az ügycsomaggal telepíti. (Javult: `mentat.status`)
- A kiadástól eltérő letöltés nem települ. A telepítő még egyszer próbálkozik, aztán megáll, és egyszerű szavakkal megmondja, miért; félig telepített állapot nem marad. A hálózati hibát hálózati hibaként jelzi, újrapróbálással. (Javult: `mentat.init`)
- A hiányzó részt megnevezi, nem pótolja. Egy megállt telepítés után az ágens felsorolja, mely részek vannak meg és melyek hiányoznak, és saját pótmegoldás helyett a hiányzó telepítését ajánlja fel. (Javult: `mentat.init`)
- A kész munka ott van ellenőrizve, ahol használod. Mielőtt késznek mondja a munkát, az ágens ellenőrzi a kapott címet, hogy a privát oldal bejelentkezést kér-e, a fájlt, vagy az utolsó ütemezett futást és annak ígért tartalmát. Ha csak a saját gépén tudta ellenőrizni, ezt meg is mondja. (Új: `brain.done`)
- Szól a mentetlen munkáról és az elkallódott kulcsról. Ugyanez az ellenőrzés jelzi a mentetlen változásokat, a még futó oldalakat és a git által tárolt fájlokban talált kulcsokat, hogy tudj róluk. (Bővült: `brain.done`)
- Az új session az ütemezés állapotával indul. Ha az utolsó ütemezett futás elmaradt, hibás volt, vagy kihagyta, amit ígért, az ágens ezt mondja el elsőként. (Bővült: `brain.done`)
- Az identitás-kapu flotta-plugin hookként. A box minden ágense ugyanazt az ellenőrzést kapja, mielőtt az e-mail-címed harmadik félhez menne. (Bővült: `fleet`)
- A doctor minden ágens őrét ellenőrzi. Piros, ha egy ágens őre vagy a Claude Code-ja nem naprakész. (Javult: `fleet`)
- Az új ágens tisztán indul. Megtalálja a registry mellett tartott runbookot, és az új meg a régebbi ágensnek is rögzíti a session-azonosítót. (Javult: `fleet`)
- Biztonságosabb alapbeállítások a szerveren. Kevesebb emelt jog, és nincs menüs kérdés a felügyelet nélküli ágensnek. (Javult: `fleet`)
- A képességfa a flottán át. A fleet capabilities összegyűjti, mit tud a box többi ágense, így egy ágens megtalálja, ami a szomszédjánál már megvan. (Bővült: `brain.where`, `fleet`)

