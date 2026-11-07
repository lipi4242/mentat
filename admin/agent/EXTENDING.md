run: `cd worker && npm run model -- add-field … ` / `npm run model -- new …` — one command does the rest. Full syntax (types, :min=, :label=, --ref, examples): `npm run model -- --help`.

```bash
npm run model -- add-field cases osszeg --type integer --min 0 --label "Összeg (Ft)" --repo <agent repo>
npm run model -- new ugyfelek --label "Ügyfelek" --field nev:text:required --field email:email --repo <agent repo>
npm run model -- new szamlak --label "Számlák" --ref ugyfel --field osszeg:integer:min=0 --field esedekes:date --repo <agent repo>
```

Agree the fields with the user first (units; is it required; which entity does it point at). Add
`--check` to see what it would do without changing anything.

Each run: validates the request (a clear error, nothing written), edits `config/models.json`
once, writes the `09NN` migration, migrates the local database (backup first), checks the
running admin (`/api/meta` lists it without `pending`; one invalid value is refused by the
admin), commits both files on the local branch `peldany` (never push it), and ends with the
list/form URL and the commands you use — quote those to the user, nothing else. A line saying
`FAILED`, `NOT committed` or `not probed` names the next step; rerunning the same command is safe.

- Types: `text textarea email date number integer checkbox select ref`. `--min/--max` (numbers),
  `--options a,b` (select), `--ref <entity>` (ref), `--pattern <regex>` (text), `--required`.
  In `new`: `--field name:type[:required|min=N|max=N|options=a|b|ref=entity|label=Text]`.
- A new entity needs a token with its scope: the output prints the exact `npm run connect` rebind
  when your token does not see it yet.
- Renaming, retyping or deleting a field is not this command: ask the user, write that migration
  by hand.

