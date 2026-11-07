# Hogyan működik a Mentat

A [README](../README.hu.md) háttere: hogyan épül fel a memória, milyen a személyisége, kiket hívhat segítségül, és mi kapcsolható még hozzá. Az induláshoz egyiket sem kell elolvasnod.

## Hogyan működik a memória

Ezt érdemes megérteni, mielőtt bármit telepítesz, mert minden más ebből következik.

### A kontextus a rövid távú memória

A kontextusablak az asszisztensed **munkamemóriája**. Kicsi, ideiglenes, és ez az egyetlen dolog,
amit tényleg érdemes optimalizálni: azt akarod, hogy pontosan az legyen benne, amivel éppen
dolgozol — és semmi más.

Ezért nem egy óriási, mindent tudó asszisztenst akarsz. Azt akarod, hogy a **megfelelő dolgok
töltődjenek be a megfelelő pillanatban**.

### A repó a DNA

Minden, ami a repóban van fájlszinten — az `AGENTS.md`, a konvenciók, a keretrendszerek — az
asszisztens **DNA-ja**. Ez az alapszemélyiség, és ugyanaz marad, akárhány sessiont nyitsz.

Indíts három agentet ugyanabban a repóban, és mind a három **ugyanazzal a személyiséggel** indul.
A munkamemóriájuk viszont más-más dologgal telik meg, ezért más-más dologban lesznek jók: az egyik
a pénzügyeidben mélyed el, a másik egy ajánlatot ír, a harmadik egy hibát javít. Azonos DNA,
eltérő rövid távú memória.

### A hosszú távú memória közös

És itt a lényeg: ez a három agent **egyetlen hosszú távú memórián osztozik**. Ha az egyik megtanul
valamit, mindegyiké lesz. Amit az egyik kedden kiderít egy ügyfélről, azt a másik pénteken már
tudja, anélkül hogy elmondanád neki.

Az agy tehát **halmozódik**, nem szétforgácsolódik a sessionök között.

### Az agy chunkokban tárol

Az emberi memória sem tart mindent egyszerre a fejében. A dolgok **chunkokban** ülnek, alvó
állapotban, amíg valami relevánssá nem teszi őket — és akkor az egész chunk visszatér: egy név, egy
illat, egy film, amire húsz éve nem gondoltál.

Az itteni agy ugyanígy épül fel. Egy mappa, és minden **entitástípus** kap benne egy sajátot. Az
egyes **entitások** a fájlok:

| Entitástípus | Mi él benne |
|---|---|
| `brain-dump` | A nyers gondolatfolyamaid — szó szerint mentve, feldolgozás előtt |
| `exploration` | Egy téma, amit többször körbejársz, de még nem döntés |
| `person` | Valaki, akinek a részletei rendre számítanak |
| `todo` | Egy konkrét, befejezhető dolog |
| `decision` | Valami, amit eldöntöttél — külön polcon, hogy kiderüljön, ha eltérnél tőle |
| `case` | Ügy: amit el kell intézni és követni — egyszer, vagy havonta (számla minden 10-éig) |
| `specification` | Egy változtatás több mozgó alkatrésszel |
| `connector` | Hogyan érd el a Gmailt, a naptáradat, a todo-appodat |
| `procedure` | Egy visszatérő feladat, egyszer leírva |
| `subagent` | **Egy perszóna, akit újra hívhatsz** — lásd lent |

**Az entitástípusok a polcok; az entitások az, ami rajtuk áll.** Új típus pedig akkor születik, ha
a valóság megköveteli: ha folyton olyasmiről beszélsz, aminek nincs polca, az asszisztens javasol
egyet. Nem talál ki polcokat, amikre sosem volt szükséged.

### Tud szakembert felvenni

Van munka, amit jobb, ha nem te csinálsz. A **subagent** egy újrahasználható
perszóna: szakértő, valaki, aki az üzletet ismeri, egy felelős gazda, vagy egy
ügyfél, aki kívülről nézi a munkádat.

Nem promptok. Mindegyiknek saját agya van:

| Fájl | Mit tartalmaz |
|---|---|
| `persona.md` | ki ő, mit kell tudnia, **miben dönt** |
| `history.md` | a közös munkátok: miben segített, mi lett belőle |
| `personal-history.md` | a saját múltja — szakmai háttér, vagy egy ügyfélút |
| `decisions/` | döntési rekordok, amik alakították, hogy ki ő |

Ebből két dolog következik. **Megmaradnak** — egy egyszer felépített perszóna
érték, nem eldobható, és minden használat után jobb lesz. És **kaphatnak
hatáskört**: területet, amiben döntenek, nem csak tanácsot adnak. Ettől ér
többet meghívni valakit, mint téged kérdezni.

Egy ügyfél-perszóna, akinek van útja — *ezt az e-mailt kapta, így válaszolt
rá* —, a következő vázlatodat **annak az embernek a következő darabjaként**
nézi át, nem elszigetelt tárgyként. Ez más review, mint egy általános.

### Tudja, hogyan kell nagy munkát levezényelni

Ha egy kérés **nagy szkópú és nincs végigspecifikálva**, a kollégád nem kezd
találgatni. Eljárást futtat: megkérdezi, milyen fejlesztési módot szeretnél,
mennyire akarod alakítani a specifikációt, és ki válaszoljon a dizájn-kérdésekre
— te, ő maga, vagy egy külső szakértő modell.

Onnantól a munka **teljes körű acceptance criteriával**, **bizonyíték-formmal**
(minden feltételhez teszt kell, és a tesztről meg kell mutatni, hogy tud bukni)
és **elkülönített worktree-vel** megy ki — hogy a zöld mérés a repóról szóljon,
ne egy gépről. Reviewer-perszónák több körben átnézik az eredményt, és a
visszajelzésük rögzül, így az egész út auditálható marad.

**A szakértő perszónák kérdés-szűrőként is működnek**: a fejlesztő fejlesztőfejjel
kérdez, és olyat is megkérdezne, amihez egy tervező jobban ért. Azt a szakértő
dönti el, nem kerül eléd — így csak az a néhány kérdés jut hozzád, amire
tényleg csak te tudsz válaszolni.

### Magától frissül

Nem kézzel iktatsz. Amikor beszélsz az asszisztenssel, átfésüli, amit mondtál, entitásokért — egy
ember, egy feladat, egy döntés, egy nyitott kérdés —, és ugyanabban a körben létrehozza vagy
frissíti a fájlokat. Ha hosszú, kusza gondolatfolyamot küldesz neki, **először a nyers szöveget
menti el**, szó szerint, és csak azután szedi ki belőle a struktúrát.

Egy entitástípus máshogy viselkedik: a **döntés**. Ha egyszer meghoztad, és később elsodródsz tőle,
az nem megy át némán. Az asszisztens megállít: *„ezt 6-án döntötted el, és azt mondtad, számít.
Felülírjuk?"* Bármikor felülbírálhatod. Csak észrevétlenül nem sodródhatsz el.

### Hogyan beszélj vele

**Reaktív mód** a megszokott: nyitsz egy sessiont, és együtt dolgoztok. Úgy beszélj hozzá, ahogy
egy okos új kollégát eligazítanál — előbb a kontextus, aztán amit kérsz. Ne tömöríts. A hosszú,
csapongó üzenet **jobb**, mint a rendezett, mert az agy egészben elmenti, és utána bányássza ki.

**Proaktív mód** az, amikor nélküled cselekszik, ütemezetten. Ehhez kell az
[motor](https://github.com/lipi4242/mentat/tree/main/engine) (lásd lejjebb). De ilyenkor sem vagy
kizárva: nyithatsz mellé egy sessiont, és intézhettek együtt ügyeket, miközben a háttérben ketyeg.

## A személyiség

Az asszisztensed úgy viselkedik, mint egy MBB-tanácsadó (McKinsey / BCG / Bain), keresztezve egy
dűnebeli mentáttal: fegyelmezett, felülről lefelé kommunikál, mintázatokban gondolkodik, és
allergiás a ceremóniára.

Azokkal a keretrendszerekkel érkezik, amiket ez maga után von — Pyramid Principle, 80/20, MECE,
First Principles, Say It With Charts —, és használja is őket. Tegyél fel egy homályos kérdést, és
egyetlen tisztázó kérdést kapsz vissza, nem öt bekezdésnyi köntörfalazást.

## Remote control

Írd be a Claude Code sessionbe, hogy `/rc`. Visszajelzi, hogy távvezérelt, és onnantól ugyanazt a
sessiont eléred a Claude asztali appjából, a webről és a telefonodról is.

Érdemes korán bekapcsolni. Egy asszisztens, akihez csak egyetlen terminálablakból tudsz szólni,
olyan asszisztens, akit el fogsz felejteni használni.

## Más modellen futtatva

Alapból a kollégád Claude-on fut. Kérésre („állj át DeepSeekre”, „vissza Claude-ra”)
átállítja magát egy mért nyílt modellre OpenRouteren át, és vissza. A `skills/model`
skillt használja: egy parancs, egy élő próba, ami igazolja, hogy a válasz az új
modelltől jön, és visszaállás, ha nem. Csak ez az ágens változik; a közös
Claude-belépés és a gép többi ágense marad, ahogy volt.

Ma mérve (elfogadási tesztsor, 3 = elvárt): **DeepSeek V4.1 Flash 3,62**, a Claude
Opus 5.5 3,69-e mellett, nagyjából tizenötöd ennyi vagy még kisebb költségért. Kell hozzá egy
keretlimites OpenRouter-kulcs; a kolléga elmondja, hogyan add át úgy, hogy ne a
chatbe másold.

## A pulzus: a motor

A fentiek elmét adnak az asszisztensednek. Pulzust nem.

Alapból **reaktív**: éles, amikor beszélsz hozzá, és tetszhalott, amikor nem. Nem veszi észre a ma
reggel érkezett számlát, mert semmi nem ébresztette fel, hogy megnézze.

A [**motor**](https://github.com/lipi4242/mentat/tree/main/engine) a másik fele — egy
determinisztikus tick, ami ütemezetten elsül, és azt kérdezi: *„van most bármi, amit érdemes
csinálni?"*, majd az itt felépített agyból válaszolja meg.

| | Mit ad az asszisztensednek | Nélküle |
|---|---|---|
| **az agy** | memória, struktúra, személyiség | asszisztens, aki minden sessionben elfelejt |
| **a motor** | szívverés — proaktív mód | asszisztens, aki csak akkor létezik, amíg gépelsz |

Itt kezdd. A motort akkor tedd hozzá, amikor megelégelted, hogy mindig neked kell kezdeményezned —
ahogy egy új kollégának is akkor adod oda a saját naptárát, amikor már megtanulta a munkát.

## Háttériroda: az admin

Az admin a Mentat teendő- és backlog-kezelője: opcionális felület és adatbázis az agy mellett, a
gépeden vagy a saját Cloudflare-fiókodon ([admin/README.md](../admin/README.md), angolul). Itt élnek a
teendők, az ügyek és a backlog-tételek, és mindegyiknél látod, kinél a labda. Egy ágens PM-ként
kiadhat egy backlog-tételt egy másiknak, az fejlesztőként átveszi, és a jelentés minden elfogadási
feltételhez bizonyítékkal jön vissza (a `backlog` skill). Admin nélkül az agy az ügyeket
Markdown-jegyzetként tartja.
