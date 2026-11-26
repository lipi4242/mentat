# Repó-felállás: az ajánlás lépése

Telepítési leírásba beemelhető szakasz. A háttér és az ábra: `reference/repo-felallas.hu.md`.

Ha a gazdának van vagy lesz kódbázisa, vagy egynél több ágenst tervez, a telepítés végén tedd fel
ezt a két kérdést, és várd meg a választ:

1. „Mások klónozzák vagy telepítik a végtermékedet a GitHubról?”
   - Nem: javasold az **A mintát**. A kódbázis repója kapja a Mentat-agyat, az asszisztensek és a
     többi Mentat pedig egy közös `agents` repóba kerülnek, mindegyik a saját mappájába. Mondd
     ki, hogy ez a javasolt út.
   - Igen: ajánld a **B mintát**. A kódbázis egy csak kiadásra szolgáló repóra és egy dev repóra
     válik, az agy a dev repóban van, és mellette ugyanúgy ott a közös `agents` repó.
2. „Lesz-e ágens, amit egyszer átadsz valakinek, vagy amelynek az adata más tulajdonosé?” Ha igen,
   az saját repót kap; a többi a közös `agents` repóba megy.

Ha üres mappába telepítesz, és a gazda több ágenst tervez, ajánld fel, hogy ez a mappa legyen
az `agents` repó első ágens-mappája (`agents/<név>/`). A gyökérbe ne kerüljön személyiséget
hordozó `CLAUDE.md`.

Meglévő repóba telepítésnél nézd meg, melyik mintához áll közelebb, és csak azt mondd el, mi
térne el tőle. Semmit ne költöztess, ne nevezz át, és új repót se hozz létre a gazda igenje
nélkül.

A választást rögzítsd döntésként: `python3 .mentat/bin/mentat_brain.py new decision
"Repó-felállás"`. Bele: melyik minta, melyik ágens kapott saját repót és miért, és hogy melyik
gépen fut a flotta. Utána két-három mondatban mondd el a gazdának, mit választott, és hogy
később is lehet rajta változtatni.
