# Google: Naptár, Gmail, Drive, Táblázatok

**Mikor:** a FELHASZNÁLÓ a Google-fiókjában szeretne valamit: meghívót, levelet, megosztott fájlt, táblázatot. Minden módosítás a `.mentat/bin/mentat_google.py`-on megy át; nincs nyers API-hívás, nincs `gws`/`curl` írás, nincs saját OAuth-kód vagy visszahívó szerver. Ami más emberekhez jut el, ahhoz előbb jóváhagyott megállapodás kell (`reference/contract.hu.md`).

## Egyszer: az eszközök

```bash
curl -fsSL --create-dirs -o ".mentat/bin/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.5.0/reference/manifest/{mentat_google.py,mentat_google_auth.py,google_api.py,google_secrets.py,google_signin.py,google_people.py,google_calendar.py,google_mail.py,google_drive.py}"
python3 -m pip install --user google-auth-oauthlib   # csak a bejelentkezéshez kell; ha hiányzik, az eszköz szól
```

## Egyszer: a Google-projekt (üzenetenként egy lépés, várd meg a „kész”-t)

A konzol feliratai változnak: azt mondd el, mit keressen, és ha egy gomb nincs ott, ahol mondtad, kérdezd meg, mit lát.

1. console.cloud.google.com → új projekt (bármilyen névvel).
2. APIs & Services → Library: csak azt kapcsold be, ami kell: Google Calendar API, Gmail API, Google Drive API, Google Sheets API.
3. Google Auth Platform (OAuth consent screen): alkalmazásnév és az e-mailje; közönség **External** (Workspace-fióknál választható az **Internal**); a Test users alatt add hozzá a FELHASZNÁLÓ saját címét.
4. Clients → Create client → Application type: **Desktop app** → Create → **Download JSON**.
5. Kérd meg, hogy a letöltött fájlt tegye a munkamappába (fájlként, ne a chatbe illesztve), aztán: `python3 .mentat/bin/mentat_google_auth.py import-client <fájl>`. A `.secrets/google/client.json` helyre kerül (0600, git-ignorált). Ha a JSON mégis a chatbe került, kérd meg, hogy csináljon új client secretet (Clients → a kliens → új secret, a régit törölje).

## Bejelentkezés

- **A böngésző ezen a gépen van:** `mentat_google_auth.py login [--scopes calendar,gmail,drive,sheets]`. Előre mondd el, hogy megnyílik egy böngészőablak; az eszköz legfeljebb `--timeout` másodpercig vár (alapból 300), és kimondja, ha feladta.
- **Másik gépen futsz** (szerveren, a FELHASZNÁLÓ a telefonján vagy a laptopján van): a `mentat_google_auth.py login --remote` (3-as kód) egyetlen linket ír ki: küldd el. Miután engedélyezte, a böngészője egy be nem töltődő oldalra jut; ez így rendben van. A címsorból a teljes címet küldje vissza, és 10 percen belül futtasd: `mentat_google_auth.py finish "<cím>"`. A címben egyszer használható kód van, a használattal elhasználódik.
- Technikai FELHASZNÁLÓ választhat SSH-alagutat is: `login --no-browser --port 8765`, az ő oldalán `ssh -L 8765:localhost:8765 <ez a gép>`.
- Sikernél az eszköz megírja a `<agy>/connectors/google.md` jegyzetet a titok valódi helyével és a megadott jogokkal. Ha a consent screen Testing állapotban van, a bejelentkezés 7 nap után lejár: futtasd újra a logint.

## A hívások

| Igény | Parancs (`python3 .mentat/bin/mentat_google.py …`) |
|---|---|
| Meghívó | `calendar create --title T --start 2026-11-07T19:00:00 --end … --tz Europe/Budapest --notify none\|externalOnly\|all --contract ID --guests contract` |
| Módosítás | `calendar update ESEMÉNY_ID --notify … [--title/--start/--end] --contract ID` |
| Levél | `gmail send --contract ID --to a@…,b@… [--cc] [--bcc] --subject S --body-file F` |
| Megosztás | `drive share FÁJL_ID` / `sheets share TÁBLA_ID --contract ID --email a@… --role reader\|commenter\|writer --notify yes\|no` |
| Táblázat írása | `sheets write TÁBLA_ID --range 'Munkalap1!A1' --file sorok.csv --contract ID` |
| Ki látja | `drive read FÁJL_ID` |

- A `--guests contract` pontosan a megállapodás jogosult embereit veszi. A vendégek nem látják egymást, hacsak a megállapodás nem mondja: `audience.visibility: visible` (`--guests-see-each-other`). A `--notify` kötelező: kérdezd meg a FELHASZNÁLÓT, kapjanak-e e-mailt.
- **Több külső levélcímzett:** `visibility: hidden` (privát csoportlevél) esetén mindenki Bcc-be kerül; `visible` esetén látják egymást; ha egyik sincs megadva, az eszköz ASK-kal (3-as kód) megáll: kérdezd meg, melyik, és írd újra a megállapodást.
- Megosztás csak név szerint; az eszköz sosem oszt meg „bárki, akinél a link van” vagy egész domain szinten, és figyelmeztet, ha a fájl már így van megosztva.
- Mindkét sort add tovább: mi ment ki és ki látja, valamint a READ BACK sort (mi van most a Google-nél). Kódok: 0 kész, 1 piros (semmi nem ment ki), 2 nincs jóváhagyott megállapodás, 3 előbb kérdezz, 4 nincs bejelentkezve.

## Amit nem csinál

Nem töröl, nem olvas levéltörzset és a módosított eseményen túl naptárat, és nem állítja meg a mellette futó nyers API-hívást (az őr a `curl` POST előtt kérdez, egy Python-szkriptet nem állít meg).
