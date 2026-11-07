# Identitás-kapu (F-41)

PreToolUse hook: ha egy hálózatra író eszközhívásban (Bash, WebFetch, WebSearch, MCP,
böngésző) a felhasználó azonosítója áll, és a cél nem első fél, a hívás nem megy ki
kérdés nélkül. Interaktív módban kérdez, headless módban (flotta, `-p`, bypass/auto) tilt.

- **Azonosítók** (generált, a SessionStart cache-eli a `~/.mentat/identitas-cache.json`-ba):
  `git config user.email`, a Claude-fiók e-mailje, a `gh` fiók publikus címe, plusz
  `~/.mentat/identitas.txt` (soronként egy, csak kézzel írható). Kódolt alakban is keresi:
  URL-kódolva, base64-ben, md5/sha1/sha256 hash-ként.
- **Első fél:** a saját e-mail-domain, a GitHub (commit, push, a saját fiók repói), a
  Google API-k, az Anthropic, a Cloudflare API, localhost, plusz `~/.mentat/elsofel.txt`
  (soronként egy host-minta, `github:<login>` vagy `mcp__<szerver>__` előtag).
- **Mód kényszerítése:** `MENTAT_ID_KAPU=ask` (mindig kérdez) vagy `deny`.
- **Az ágens nem írhatja** a cache-t, a két fájlt és a `~/.mentat/bin/identitas-kapu/` kódot
  (`vedett.py`): csak az ÍRÁS akad meg, a futtatás és az olvasás szabad, a repó saját
  `.mentat/bin`-je és `.claude/settings.json`-ja nem a kapué. A felhasználói Claude-beállítás
  (`~/.claude*/settings*.json`, `CLAUDE_CONFIG_DIR`) írása kérdés (headless: tilt).
- **Ismert korlátok** (tesztek rögzítik): futás közben összerakott, megfordított vagy
  karakterenként összefűzött érték; letöltött szkript. Ezekre a visszamenőleges szkenner
  és a fleet doctor való.

- **Dupla kapu ellen:** a plugin a `--instance plugin` kapcsolóval fut; ha a felhasználói szintű
  kapu (`~/.mentat/bin/identitas-kapu/current`, a felhasználói `settings.json`-ban `*` matcherrel
  és `onFailure: block`-kal) él, a plugin nem kérdez másodszor. Repón belüli jelző nem számít.

Tesztek: `python3 -I -m unittest discover -s plugin/hooks/identitas -q`.
Hibánál tilt (`onFailure: "block"`, Claude Code ≥ 2.1.295; F-39).

## Nem-akadó jóváhagyás (`nemakad.py`)

PermissionRequest hook: ha senki nem tud jóváhagyni, a kérés nem vár örökké. A hook
elutasítja, és a modell javaslatot kap. Változós `rm` esetén `"${D:?}/x"`, `cd … && <írás>`
esetén abszolút útvonal vagy `git -C`, minden más esetben: hagyja ki, és jelentse.
Engedélyt soha nem ad.

- **Felügyelet nélküli a futás**, ha él a `FLEET_AGENT`/`THUFIR_AGENT` (a box-unit exportálja),
  a `MENTAT_HEADLESS`, a hívás repójában a `.claude/fleet.json`, vagy a `~/.mentat/felugyelet-nelkul`
  jelző (`nemakad.py alszom 08:00`).
  Különben a hook nem ír semmit, és a kérdés a szokásos módon megjelenik.
- **Napló:** `~/.mentat/nemakad-naplo.jsonl` (maszkolt előtag), `nemakad.py naplo 12`.
- **A forrás** a `security/eszkozok/identitas/` (CISO); ez a mappa annak a másolata.

Tesztek: `python3 -I -m unittest discover -s plugin/hooks/identitas -p 'test_nemakad*.py' -q`.

## Titok-kapu és ágens-határ (`titok_kapu.py`)

PreToolUse hook, csak tilt. Nem enged titkot (kulcsfájl, más ágens átirata, környezet-kiírás) a
Claude-kontextusba. Ugyanez a hook az ágens-határ: más ágens szabályfájlját a fő ágán, a systemd
user-unitokat és a flotta-registryt kézzel nem írhatod. Összeolvasztás-módban (`fleet secrets
merge-mode`, legfeljebb 7 nap) a más ágens fő ágát író git, a helyi `tmux send-keys` és a más ágens
kódjával futó kifelé ható parancs is tilos.

- **Telepítés:** `fleet secrets hook install` a box minden `~/.claude*/settings.json`-jába, a kódot a
  `~/.mentat/bin/titok-kapu/<sha>/` alá másolja, és csak sikeres önteszt után kapcsolja be.
- **Hibánál:** a titok-ellenőrzés tilt; az ágens-határ hibája átenged, és a
  `~/.mentat/titkok/hatar-hibak.log`-ba ír egy sort.
- **Korlát:** sebességcsökkentő küszöb. Szkriptfájl, értelmező és futás közben összerakott parancs
  átmegy rajta; a valódi kontroll az utólagos állapot-ellenőrzés.
- **A forrás** a `security/eszkozok/identitas/`; a futó fájlok itt bájtra egyeznek vele
  (`tests/test_titok_telepit.py`).
