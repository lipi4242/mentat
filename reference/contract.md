# The agreed task in a file, checked before it goes out

**When:** the USER asks for a list, an export, a report, a newsletter, an invitation or any message to several people, or for a recurring output. What was agreed (columns, what stays out, who receives it, the dates, the defaults) goes into a file, not just the chat, and the output is checked against it **before** it goes out and **before** you call it done. "It ran" or "HTTP 200" is not done.

Tools (the installer fetches them; if `.mentat/bin/mentat_contract.py` is missing, run initialization step 2's download again): `python3 .mentat/bin/mentat_contract.py` and `python3 .mentat/bin/mentat_accept.py`. The contract lives at `<brain>/contracts/<id>.json` and is committed with the brain.

## Steps

1. **Resolve the vague words first.** "Next week", "the guests", "everyone" — ask, then write absolute dates with the time zone. A relative date: `python3 .mentat/bin/mentat_dates.py "<the phrase>" --tz <tz>` — exit 0 gives the dates, exit 3 lists the readings to ask about, exit 1 means ask for the dates (`2026-11-02` – `2026-11-08`, `Europe/Budapest`) and the exact filter. The tool refuses relative dates and a window without a time zone.
2. **Draft:** write the proposal as JSON and run `mentat_contract.py draft <id> --file proposal.json` (or `--file -` from stdin). It prints the read-back; pass it on in your own words, one message, and ask for a yes.
3. **Approve only on their yes:** `mentat_contract.py approve <id> --quote "<their words, verbatim>" --version <N>` (N = the version you read back). Without a quote nothing is approved (exit 2).
4. **Before each write:** `mentat_contract.py check-write <id> [--fields a,b] [--recipients x@…,y@…] [--dates YYYY-MM-DD,…]` — exit 0 fits, 1 does not fit (it names what), 2 there is no approved contract.
5. **Before it goes out and before "done":** `mentat_accept.py <id> <output> [--recipients FILE]`. GREEN (exit 0): say the one line to the USER. RED (exit 1): it does not go out; fix it, run it again. CANNOT CHECK (exit 2): no approved contract or an unreadable output — treat it as red.
6. **The USER changes something:** draft again. `mentat_contract.py diff <id> --file new.json` shows the change first (exit 3 = material). A material change makes a new version that needs a new yes; only `notes` can change without one. `show <id> [--json]` prints the current state.

## The proposal

```json
{
  "goal": "The confirmed guests of the 7 November dinner, for the caterer.",
  "fields": ["name", "email", "date"],
  "exclude": {"fields": ["phone"], "records": [{"status": "declined"}], "values": ["+36 1 333"]},
  "records": {"source": "data/guests.csv", "key": "email", "where": {"status": "confirmed"}},
  "audience": {"who": "the confirmed guests", "from_records": "email", "visibility": "hidden"},
  "window": {"start": "2026-11-02", "end": "2026-11-08", "tz": "Europe/Budapest", "field": "date"},
  "defaults": {"paid": ""},
  "notes": "free text"
}
```

Only `goal` is required. `checks` is derived from the rest (exactly these columns; nothing left out is in it; every date inside the window, read in `tz`; exactly the records of `source` that match `where` and the window; recipients only from `allowed` — addresses or `@domain` — and the eligible records' `from_records` column; recipients cannot see each other). List `checks` yourself only to drop one, and say so in the read-back.

## A planned send

For a send, check a send plan (JSON): `{"to": [...], "cc": [...], "bcc": [...], "visibility": "hidden"}` for mail, or `{"guests": [...], "guestsCanSeeOtherGuests": false}` for a calendar invitation. Hidden means: everyone in `bcc`, at most one address in `to`+`cc`, or `guestsCanSeeOtherGuests` explicitly `false` (a calendar shows the guest list by default). A file that goes to people: `mentat_accept.py <id> list.csv --recipients to.txt`.

## What it does not do

It checks the file or plan you give it; it does not send, and it does not stop a send that skips it. Run it on the exact file that goes out. The engine (the cases pack) runs this check by itself before it sends a list or a reminder whose case, todo or CSV table carries `contract: <id>`; a single reminder is checked with `--part` (one part of the agreed set: a missing record is fine, everything else is not). Anything else you send yourself, you check yourself.
