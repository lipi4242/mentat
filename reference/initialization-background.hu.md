# Inicializálás — háttér és tartalék utak

Csak akkor olvasd, ha az `initialization.hu.md` egy lépése elakadt.

## Nincs `python3`, vagy a letöltés hibát ad (1. lépés)

Mondd ki a hibát. Python nélkül a BASE alatti `reference/manifest/scaffold-agents.hu.md` és `scaffold-meta.json` alapján hozd létre kézzel ugyanazt: az `{BASE}` és `{LANG}` cseréje az AGENTS.md-ben; a `mentat.json` alakja: `reference/mentat-json.hu.md`. Letöltési hibánál soha ne találj ki szerkezetet. Az agy jegyzeteit ilyenkor a `reference/templates/<típus>.hu.md` sablonokból, kézzel írd.

## Miért ez a sorrend

- A `--check` már igazolja, hogy a `CLAUDE.md` betölti az `AGENTS.md`-t; a 4. lépés élő próbája ezt egy valódi friss sessionnel is megmutatja (egyszer, mert bejelentkezés nélkül úgyis hibázik).
- Az `AGENTS.md` ebben a sessionben még nincs betöltve, ezért a szabályait az `initialization.hu.md` adja át.
- A `mentat.json` szándék (commitolt), a `.mentat/local.json` gép-tény (gitignored): lásd `reference/mentat-json.hu.md`.
