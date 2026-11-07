"""The guard's words to the agent in the brain's language (mentat.json agent.language: hu | en).

lang(root) -> "hu" | "en"; text(root, key, *args); kind(root, key) -> the danger's name. The
Hungarian KINDS stay in szerep_kapu; KINDS_EN is their English. A missing or unreadable
mentat.json means Hungarian (the default brain language).
"""
import json
import pathlib

from szerep_kapu import KINDS

KINDS_EN = {
    "rm-kivul": "a recursive or forced delete outside the working folder",
    "force-push": "git push --force (it rewrites the remote history)",
    "titok": "reading the content of .env or a key file",
    "post": "sending data (curl/wget POST, or mail) to an outside address",
    "env": "overriding a protected environment variable",
    "git-config": "overriding git settings (-c, config, sparse-checkout)",
    "db-iras": "writing to a database straight from the command line instead of the app's own path",
    "uj-kepesseg": "new executable code, a unit, a schedule or a new package without a fresh capability receipt: first "
                   "`python3 .mentat/bin/mentat_brain.py where --find \"<the request>\"`, then `where --decide`",
    "identitas": "the USER's identifier (e-mail) would go to a third party; leave it out, the APIs work without it",
    "elsofel": "adding the lines named in the command to your own places (elsofel.txt under ~/.mentat)",
    "beallitas": "changing the guard's or the product's own code, its folders or the hook settings",
    "szerver": "a server or a command that never ends blocks the turn: run it once (`tail -n 50`, `ping -c 3`, `up -d`), "
               "or `python3 .mentat/bin/mentat_serve.py start <name> --dir <folder> | [--port <port>] -- <command>`",
}
T = {
    "hu": {
        "secret": " — a titok útja, ami mindig nyitva: rejtett űrlap `python3 .mentat/bin/mentat_serve.py start <név> "
                  "--secret VAR`; ha a FELHASZNÁLÓ már a chatbe írta: `python3 .mentat/bin/mentat_secret.py put VAR` "
                  "(stdin); megvan-e: `mentat_secret.py has VAR`",
        "final": " — végleges kimenő lépés (küldés, levél, rögzítés): `python3 .mentat/bin/mentat_final.py preview ID "
                 "--what … --to <cím> --file PAYLOAD`, mutasd meg („Ha rendben, válaszold: <kód>”), a válasz után "
                 "`approve ID`; a fájllal (`-d @PAYLOAD`) ugyanarra a címre már nem kérdez",
        "db": " — a projekt adatbázisának beállítása (d1 create, migrations apply): `python3 .mentat/bin/mentat_web.py "
              "deploy --approved \"<a FELHASZNÁLÓ igenje>\" -- npx wrangler d1 …`; adatot az alkalmazás útján javíts",
        "own": " — ehhez külön igen kell a FELHASZNÁLÓtól, a telepítőn át (a kiadás eszközeinek frissítése); maga ne írd át",
        "rm": " — törölni a munkamappán belül szabad (ott nem kérdez); kívül csak az az út, amit a FELHASZNÁLÓ megnevez",
        "push": " — út: `git push` --force nélkül, vagy egy új ágra (`git push origin HEAD:<új-ág>`)",
        "env": " — ezt a változót a környezet adja (a unit / az /etc/environment), nem egy parancs; az eszköznek a saját kapcsolóját add",
        "gitcfg": " — nyitva: `git config user.name …` / `user.email …` és az olvasás (`--get`, `--list`); mást ne írj át",
        "out": " — út: a FELHASZNÁLÓ nevezze meg a pontos utat az üzenetében (akkor interaktívan jóváhagyja), átvételnél a BEKOTES",
        "ask": "A FELHASZNÁLÓ jóváhagyása kell — %s. Miért kérdezem: %s.",
        "why_out": "a munkamappán kívüli olvasás alapból tiltott; meglévő business átvétele a BEKOTES szerint "
                   "megy, a forrásokat a $BK eszközei szűrve olvassák",
        "why": "veszélyes vagy a védelmet gyengítő művelet",
        "self": "%s. Ez nem a FELHASZNÁLÓnak szóló kérdés: előbb keress a kérés szavaival (`where --find`), aztán "
                "dönts a nyugtáján (`where --decide … use|enable|new`); utána mehet. Ne keress kerülőutat.",
        "server": "%s. Ez nem a FELHASZNÁLÓnak szóló kérdés; a kiírt URL-t add át neki.",
        "ident": "Headless futás — %s. Ne keress kerülőutat (kódolás, változó, fájl): hagyd ki az azonosítót, vagy "
                 "írd meg a FELHASZNÁLÓnak a csatornáján.",
        "headless": "Headless futás, itt senki nem hagyhatja jóvá — %s (%s). Ne keress kerülőutat: írd meg a "
                    "FELHASZNÁLÓnak a csatornáján (Telegram), mit és miért tennél, AskUserQuestion-nel ne; "
                    "jóváhagyni egy interaktív sessionben tudja.",
    },
    "en": {
        "secret": " — the secret route that is always open: a hidden form `python3 .mentat/bin/mentat_serve.py start <name> "
                  "--secret VAR`; already pasted into the chat: `python3 .mentat/bin/mentat_secret.py put VAR` (stdin); "
                  "is it set: `mentat_secret.py has VAR`",
        "final": " — a final outbound step (send, mail, record): `python3 .mentat/bin/mentat_final.py preview ID --what … "
                 "--to <address> --file PAYLOAD`, show it (\"If it is OK, reply: <code>\"), then after the reply "
                 "`approve ID`; with that file (`-d @PAYLOAD`) to the same address it no longer asks",
        "db": " — setting up the project's database (d1 create, migrations apply): `python3 .mentat/bin/mentat_web.py "
              "deploy --approved \"<the USER's yes>\" -- npx wrangler d1 …`; fix data through the app",
        "own": " — this needs a separate yes from the USER, through the installer (a refresh of the release's tools); "
               "do not edit it yourself",
        "rm": " — deleting inside the working folder is open (no question there); outside only a path the USER names",
        "push": " — route: `git push` without --force, or to a new branch (`git push origin HEAD:<new-branch>`)",
        "env": " — this variable comes from the environment (the unit / /etc/environment), not from a command; give the tool its own flag",
        "gitcfg": " — open: `git config user.name …` / `user.email …` and reading (`--get`, `--list`); change nothing else",
        "out": " — route: the USER names the exact path in their message (then they approve it interactively); a takeover goes through BEKOTES",
        "ask": "This needs the USER's approval — %s. Why I ask: %s.",
        "why_out": "reading outside the working folder is closed by default; a takeover goes through BEKOTES, filtered",
        "why": "a dangerous step, or one that weakens the protection",
        "self": "%s. This is not a question for the USER: first search with the request's words (`where --find`), then "
                "decide on its receipt (`where --decide … use|enable|new`); then go on. Do not look for a detour.",
        "server": "%s. This is not a question for the USER; give them the URL it prints.",
        "ident": "Headless run — %s. Do not look for a detour (encoding, a variable, a file): leave the identifier out, "
                 "or write to the USER on their channel.",
        "headless": "Headless run, nobody can approve it here — %s (%s). Do not look for a detour: tell the USER on "
                    "their channel (Telegram) what you would do and why, not with AskUserQuestion; they can approve it "
                    "in an interactive session.",
    },
}


def lang(root):
    try:
        got = (json.loads(pathlib.Path(root, "mentat.json").read_text(encoding="utf-8")).get("agent") or {}).get("language")
    except (OSError, ValueError, AttributeError):
        got = None
    return "en" if got == "en" else "hu"


def text(root, key, *args):
    s = T[lang(root)][key]
    return s % args if args else s


def kind(root, key):
    return (KINDS_EN if lang(root) == "en" else KINDS)[key]
