Mentat súgó · v1 (2026-11-13)

MIT TUDOK
[[A fő funkciók listája ide kerül. Addig: https://github.com/lipi4242/mentat/blob/main/reference/usage.hu.md]]
Parancsot nem kell tudnod: úgy beszélj velem, mint egy kollégával.

KEZDD EZZEL
1. /mentat status
   Elvárt: a szerepem, a todo, az ütemező és a következő lépés, négy sorban.
   Ha hibát ír: python3 .mentat/bin/mentat_cli.py status (megmondja, mi hiányzik vagy hibás).
2. Mondd: „Jegyezd fel: holnap 10-kor felhívom Annát.”
   Elvárt: elmentem, és megmondom, melyik jegyzetbe került.
   Ha nem tudom elmenteni: python3 .mentat/bin/mentat_cli.py status, a brain sor „present” legyen.
3. Mondd: „Van már erre valami: minden reggel írd ki, mi esedékes.”
   Elvárt: python3 .mentat/bin/mentat_brain.py where --find alapján megmondom, mi van meg és mit kell bekapcsolni.
   Ha semmit nem talál: nincs ilyen képesség, és megkérdezem, építsük-e meg.

PARANCSOK
/mentat status   ki vagyok, mi van bekapcsolva, mi a következő lépés
/mentat todo     a todo és a backlog bekapcsolása, lépésről lépésre
/whoami          a státuszsor tartalma (az asztali alkalmazásban is)
/fleet:roster    a flotta társai, ha flottában futok
Dokumentáció: https://github.com/lipi4242/mentat/tree/main/reference

== todo
A TODO ÉS A BACKLOG BEKAPCSOLÁSA (először helyben, a saját gépeden)
Kell hozzá: git, curl, python3, Node.js 22+ és a Mentat checkout (~/src/mentat, az admin README gyorsindítása szerint).
1. A függőségek: cd ~/src/mentat/admin && npm ci --prefix worker && npm ci --prefix admin
2. A bekötés egy paranccsal: cd worker && npm run connect -- --repo <ennek az ágensnek a mappája> --url http://localhost:8787 --local --plugins todo
   Elvárt: a végén egy rövid blokk (kész / következő / belépés). Az admin szolgáltatásként fut tovább (macOS: launchd, Linux: systemd), a terminál bezárása után is.
   Ha hibát ír: ugyanez --check kapcsolóval csak felsorolja, mi hiányzik; npm run status mutatja a szolgáltatás állapotát.
3. Ellenőrzés az ágens mappájában: mentat-todo me
   Elvárt: az ágens saját todo-azonosítója (@név), --as nélkül.
4. Belépés egyszer: npm run login-link (a worker mappában), a linket nyisd meg, és a Résztvevők oldalon hozd létre a saját azonosítódat.
5. /mentat status
   Elvárt: Todo: bekapcsolva (@név).
Később, ha a telefonodról vagy több gépről is el akarod érni: ugyanez a parancs --remote --url https://<az admin címe> kapcsolóval, egy Cloudflare-példányra.
