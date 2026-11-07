# Google: Calendar, Gmail, Drive, Sheets

**When:** the USER wants something done in their Google account: an invitation, a mail, a shared file, a sheet. Every change goes through `.mentat/bin/mentat_google.py`; no raw API call, no `gws`/`curl` write, no OAuth code or callback server of your own. Anything that reaches other people needs an approved contract first (`reference/contract.md`).

## Once: the tools

```bash
curl -fsSL --create-dirs -o ".mentat/bin/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.5.1/reference/manifest/{mentat_google.py,mentat_google_auth.py,google_api.py,google_secrets.py,google_signin.py,google_people.py,google_calendar.py,google_mail.py,google_drive.py}"
python3 -m pip install --user google-auth-oauthlib   # only the sign-in needs it; the tool says so if it is missing
```

## Once: the Google project (one step per message, wait for "done")

The console changes its labels; describe what the USER should look for, and if a button is not where you said, ask what they see.

1. console.cloud.google.com → create a project (any name).
2. APIs & Services → Library: enable only what is needed: Google Calendar API, Gmail API, Google Drive API, Google Sheets API.
3. Google Auth Platform (OAuth consent screen): app name and their e-mail; audience **External** (a Workspace account may choose **Internal**); under Test users add the USER's own address.
4. Clients → Create client → Application type **Desktop app** → Create → **Download JSON**.
5. Ask them to put the downloaded file into the working folder (a file, not pasted into the chat), then: `python3 .mentat/bin/mentat_google_auth.py import-client <file>`. It goes to `.secrets/google/client.json` (0600, git-ignored). If the JSON was pasted into a chat anyway, have them make a new client secret (Clients → the client → add a secret, delete the old one).

## Sign-in

- **The browser is on this machine:** `mentat_google_auth.py login [--scopes calendar,gmail,drive,sheets]`. Tell the USER first that a browser window opens; the tool waits at most `--timeout` seconds (default 300) and says when it gave up.
- **You run on another machine** (a server, the USER is on their phone or laptop): `mentat_google_auth.py login --remote` (exit 3) prints one link: send it. After they allow access their browser lands on a page that does not load; that is expected. They send you the whole address from the address bar, you run `mentat_google_auth.py finish "<address>"` within 10 minutes. The address holds a one-time code that is spent on use.
- A technical USER may prefer an SSH tunnel: `login --no-browser --port 8765` and `ssh -L 8765:localhost:8765 <this machine>` on their side.
- On success the tool writes `<brain>/connectors/google.md` with the real secret location and the granted scopes. A consent screen in Testing status expires the sign-in after 7 days: run login again.

## The calls

| Need | Command (`python3 .mentat/bin/mentat_google.py …`) |
|---|---|
| Invitation | `calendar create --title T --start 2026-11-07T19:00:00 --end … --tz Europe/Budapest --notify none\|externalOnly\|all --contract ID --guests contract` |
| Change it | `calendar update EVENT_ID --notify … [--title/--start/--end] --contract ID` |
| Mail | `gmail send --contract ID --to a@…,b@… [--cc] [--bcc] --subject S --body-file F` |
| Share | `drive share FILE_ID` / `sheets share SHEET_ID --contract ID --email a@… --role reader\|commenter\|writer --notify yes\|no` |
| Write a sheet | `sheets write SHEET_ID --range 'Sheet1!A1' --file rows.csv --contract ID` |
| Who sees it | `drive read FILE_ID` |

- `--guests contract` takes exactly the contract's eligible people. Guests never see each other unless the contract says `audience.visibility: visible` (`--guests-see-each-other`). The `--notify` choice is required; ask the USER whether people get an e-mail.
- **Several outside mail recipients:** with `visibility: hidden` (a private group mail) everyone goes in Bcc; with `visible` they see each other; without either the tool stops with ASK (exit 3): ask the USER which one, draft the contract again.
- Sharing is by name only; the tool never shares with "anyone with the link" or a whole domain, and it warns when the file already is.
- Pass on both lines: what went out and who sees it, and the READ BACK line (what Google now holds). Exit: 0 done, 1 red (nothing was sent), 2 no approved contract, 3 ask first, 4 not signed in.

## What it does not do

It does not delete, does not read mail bodies or the calendar beyond the event it changed, and does not stop a raw API call made around it (the guard asks before a `curl` POST, a Python script is not stopped).
