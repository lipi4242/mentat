# Initialization — background and fallbacks

Read only when a step of `initialization.md` got stuck.

## No `python3`, or a fetch fails (Step 1)

Say so. Without Python, build the same by hand from `reference/manifest/scaffold-agents.en.md` and `scaffold-meta.json` under BASE (replace `{BASE}` and `{LANG}` in AGENTS.md; the shape of `mentat.json`: `reference/mentat-json.md`). On a failed fetch never invent a structure. Write the brain's notes by hand from `reference/templates/<type>.en.md` then.

## Why this order

- `--check` already proves that `CLAUDE.md` loads `AGENTS.md`; the live probe in Step 4 shows it with a real fresh session (once: without a login it fails anyway).
- `AGENTS.md` is not loaded into this session yet, so `initialization.md` hands you its rules.
- `mentat.json` is intent (committed), `.mentat/local.json` a machine fact (gitignored): see `reference/mentat-json.md`.
