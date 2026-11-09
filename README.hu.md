<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png">
  <img alt="Mentat: AI-kollégák, akiket te raksz össze" src="assets/banner-light.png" width="100%">
</picture>

# Mentat

[![Kiadás](https://img.shields.io/github/v/tag/lipi4242/mentat?label=kiad%C3%A1s)](https://github.com/lipi4242/mentat/releases)
[![Licenc](https://img.shields.io/badge/licenc-Apache--2.0-blue.svg)](LICENSE)

[English](README.md)

A Mentat a saját Claude-előfizetéseddel fut, a Claude Desktopban vagy a Claude Code parancssorában, és egyetlen prompttal telepíted. Windowson, Macen és Linuxon is működik, és a telefonodról a Claude appon át is beszélhetsz vele. Ha szeretnéd, átáll egy másik modellre, például az OpenRouteren át a DeepSeekre, amit használat szerint fizetsz ([hogyan](reference/how-it-works.hu.md#más-modellen-futtatva)).

## Mit fizetsz, és kinek

A Claude-csomagodat az Anthropicnak fizeted, vagy annak a modellszolgáltatónak, akire átállsz. A beszélgetéseidet ez a szolgáltató dolgozza fel, a saját feltételei szerint. A jegyzeteid és az ágens memóriája a gépeden, egy mappában maradnak. A Mentat nekünk semmit nem küld: nincs benne telemetria, és csak akkor megy ki a netre, amikor a GitHubról letölti magát és a frissítéseit, vagy amikor az általad bekötött szolgáltatásokat éri el. A Mentat független, nyílt forráskódú projekt, nem az Anthropic terméke, és az Anthropic nem is támogatja hivatalosan.

## Az ötlet

Az AI-kollégáidat te rakod össze, és te döntöd el, milyen ágenst indítasz. Elsőnek személyi asszisztenst javaslunk, aki a többi ágensedre is figyel. Ha egy projekt megnő, kaphat saját agyat és saját csapatot szerep-ágensekből, akik közös munkatérben dolgoznak. A [szerep-térkép](reference/szerepek.hu.md) megmutatja a szerepeket, és azt, hogyan adják át egymásnak a munkát.

## Hét dolog, amit tud

### A te Claude-csomagod, vagy egy másik modell
<!-- illustration: subscription / model switch -->
Azon a Claude-előfizetésen fut, amit már most is fizetsz. Egy OpenRouter-kulccsal egy mondatra átáll egy általad választott nyílt modellre, például a DeepSeekre, és egy másikra vissza.

### Kész szerepek egy termékcsapathoz
<!-- illustration: roles -->
Asszisztens, PM, fejlesztő és kiadó ágens: ezek rögtön használhatók. Mindegyik tudja, hol ér véget a dolga, és kinek adja tovább a munkát, így a fejlesztő nem mergel, az eredményt pedig a PM fogadja el.

### Minden ágensnek saját Telegram
<!-- illustration: fleet + Telegram -->
Szerveren minden ágens kaphat saját Telegram-botot: ír neked, és te is írhatsz neki. A flotta életben tartja őket, és újraindítja, amelyik leáll. Ehhez a részhez szerver kell.

### Szabályok, amiket elolvasol és átírsz
<!-- illustration: rules -->
A szabályai és a döntéseid sima szövegként vannak a mappájában. Ha mondasz neki egy új szabályt, leírja, és ha egy korábbi döntéseddel ellentétesen lépne, megáll és rákérdez.

### Alágensek, ha kéred
<!-- illustration: sub-agents -->
Egy feladatra behív egy karaktert: egy ügyfelet, aki végigmegy a termékeden és visszajelez, vagy egy külső szakértőt, például jogászt vagy designert, aki hozzászól egy döntéshez.

### Kevés tokent használ
<!-- illustration: token use -->
Amit szkript is el tud végezni, azt szkript végzi, így a rutinlépésekhez nem kell a modell. Szerveren az ágens csak akkor ébred fel, ha van munka, ezzel egy kisebb Claude-csomagot is kímél.

### Őrök a kockázatos lépéseknél
<!-- illustration: security -->
Nem nyitja meg a titkos fájljaidat, megkérdez, mielőtt kinyúlna a mappájából, és mielőtt egy levél vagy megosztott fájl kimegy, ellenőrzi a címzetteket. Amit a weben vagy egy fájlban olvas, az neki adat, nem utasítás.

## Backlog, teendők és ügyek

### Backlog
<!-- screenshot: backlog -->
Ami a következő fejlesztés. A PM vezeti a listát, a fejlesztő elvisz egy tételt, az eredmény pedig minden elfogadási feltételhez bizonyítékkal jön vissza.

### Teendők
<!-- screenshot: todo -->
A te és az ágenseid napi feladatai. Mindig látod, kinél van a labda.

### Ügyek
<!-- screenshot: cases -->
Hosszabb ügyek határidővel, például egy szerződés vagy egy hivatali vita. Minden ügy a lezárásig magával viszi a következő lépést és a dátumát.

Mindhárom a választható admin webalkalmazásban él, a gépeden vagy a saját Cloudflare-fiókodon ([admin](admin/README.md), angolul). Nélküle az ágens jegyzetként tartja az ügyeket a mappájában.

## A laptopodon és egy szerveren

A laptopodon akkor dolgozik, amikor a Claude nyitva van: emlékszik, a szabályaid szerint dolgozik, intézi a dolgokat a Google Naptáradban, Gmailedben, Táblázataidban és Drive-odon, és a nyitott sessiont a telefonodról is eléred. Háttér-időzítője ott nincs, így reggeli összefoglalót és emlékeztetőt magától nem küld; ha megkérdezed, „mi esedékes?”, elmondja.

Egy kicsi, mindig futó Linux szerver adja a többit: a reggeli összefoglaló és a határidő-emlékeztetők időre jönnek, magától utánajár a dolgoknak, minden ágensnek lehet saját Telegramja, és egy összeomlott ágens kb. egy perc múlva újra fut.

A Google-ről: olvassa és módosítja a naptáreseményeidet, levelet küld, a leveleidnek pedig a feladóját, tárgyát és dátumát látja (a szövegüket nem), a Drive-fájljaidat és táblázataidat olvassa és szerkeszti. Mindegyiket csak akkor köti be, ha kéred ([részletek](reference/google.hu.md)).

## Telepítés

Nyisd meg a Claude Desktopot, menj a Code fülre, és válassz egy új, üres mappát. Másold be:

```
Telepítsd nekem a Mentat asszisztenst ebbe a mappába.
A lépések itt vannak: https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/INSTALL.hu.md
Minden lépés előtt mondd el, mit csinálsz.
```

A Claude minden lépés előtt elmondja, mit fog csinálni, és mielőtt bármit telepítene, ami a gépedről hiányzik, megkérdez. Fizetős Claude-csomag kell hozzá. Minden lépés részletesen: [INSTALL.hu.md](INSTALL.hu.md).

## Meglévő vállalkozás bekötése

Mondd neki: „Kösd be magad a <név> businessbe.” A [bekötés](reference/bekotes/BEKOTES.hu.md) szerint dolgozik: megkérdezi, mit olvashat, és csak azt olvassa. Az a dolga, hogy a gépeden máshol ne kutasson, a védelme pedig kérdez, mielőtt kinyúlna a mappájából.

## Hibajelentés és biztonsági hiba

Kérd meg az ágensedet, hogy „jelentse be ezt a hibát”: megírja a jelentést titkok és személyes adatok nélkül, és semmit nem tesz fel, amíg nem mondasz igent. [Hibajelentést](https://github.com/lipi4242/mentat/issues/new/choose) magad is nyithatsz. Biztonsági hibát privátban jelezz, soha ne nyilvános issue-ban: [SECURITY.hu.md](SECURITY.hu.md).

## Változások

A kiadási jegyzetek és a frissítési lépések a [CHANGELOG.md](CHANGELOG.md)-ben vannak (angolul), a képességenkénti változások a [CAPABILITY-LOG.hu.md](CAPABILITY-LOG.hu.md)-ben.

## Tovább

[Hogyan működik](reference/how-it-works.hu.md) · [Használat](reference/usage.hu.md) · [Szerepek](reference/szerepek.hu.md) · [Biztonság](SECURITY.hu.md) · [Apache-2.0](LICENSE)
