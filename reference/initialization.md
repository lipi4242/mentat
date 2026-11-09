# Initialization Procedure

Run these steps in order. **You are not done until step 4 is done.** BASE: `https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/`

## Step 1 — The decisions in one message

Ask in one message, in the USER's language (that of their first message, unless they named one):
1. Their name, and formal or informal address?
2. What name do they give you? Offer 3 short ideas (e.g. Thufir, Scout, Compass), or their own.
3. Do they want the proactive engine (a morning summary of what is due)? If yes: their timezone (suggest the machine's: `date +%Z`).

No other question now; saving and the checks are the tool's job. `--lang`: `hu` if the USER writes Hungarian, otherwise `en` (you still answer in their language). Git identity: the tool uses the one already set; only when none is set does it stop and ask for the name and e-mail on their saves (never a made-up address).

## Step 2 — Install in one call

```bash
curl -fsSL --fail-early --create-dirs -o ".mentat/bin/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/manifest/{mentat_manifest.py,mentat_rules.py,mentat_roles.py,mentat_cli.py,mentat_scaffold.py,mentat_scaffold_check.py,mentat_init.py,mentat_init_checks.py,mentat_init_inventory.py,mentat_init_os.py,mentat_init_parts.py,mentat_verify.py,mentat_dates.py,mentat_dates_text.py,mentat_dates_words.py,mentat_brain.py,mentat_brain_read.py,mentat_brain_ops.py,mentat_brain_types.py,mentat_web.py,mentat_serve.py,mentat_serve_proc.py,mentat_serve_run.py,mentat_secret.py,mentat_secret_scan.py,mentat_final.py,mentat_final_to.py,mentat_done.py,mentat_done_sched.py,mentat_contract.py,mentat_contract_store.py,mentat_contract_terms.py,mentat_contract_text.py,mentat_accept.py,mentat_accept_checks.py,mentat_accept_load.py,scaffold-meta.json,scaffold-agents.en.md,mentat_caps.py,mentat_caps_check.py,mentat_caps_html.py,mentat_caps_ki.py,kepessegfa-map.html,mentat_caps_index.py,mentat_caps_napi.py,mentat_caps_own.py,mentat_caps_probe.py,mentat_caps_receipt.py,mentat_caps_ref.py,mentat_caps_search.py,mentat_caps_text.py,mentat_bugreport.py,mentat_bugreport_draft.py,mentat_bugreport_env.py,mentat_bugreport_gh.py,mentat_bugreport_redact.py}" -o ".mentat/bin/capabilities/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/manifest/capabilities/{brain.json,contract.json,engine.json,google.json,suite.json,web.json}" -o ".mentat/bin/bekotes/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/bekotes/{szerep_guard.py,szerep_pin.py,szerep_rules.py,szerep_tiltott.py,szerep_git.py,szerep_bash.py,szerep_kint.py,szerep_engedely.py,szerep_hook.py,szerep_dontes.py,szerep_kapu.py,szerep_kapu_db.py,szerep_kapu_kepesseg.py,szerep_kapu_id.py,szerep_kapu_iras.py,szerep_kapu_szerver.py,szerep_kapu_fut.py,szerep_stop.py,szerep_kuldes.py,szerep_prompt.py,szerep_kapu_inline.py,szerep_szoveg.py,szerep_start_sched.py,szerep_kapu_final.py,szerep_kapu_git.py,szerep_id.py,szerep_id_bash.py,szerep_id_elsofel.py,szerep_id_halozat.py,szerep_id_javaslat.py,szerep_id_felhasznaloi.py,szerep_naplo.py,fajlszuro.py}" -o ".mentat/bin/bekotes/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/manifest/{mentat_roles.py,mentat_manifest.py,mentat_rules.py}" -o .mentat/bin/release.json "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/release.json" && python3 -I .mentat/bin/mentat_init.py --lang en --user "<name>" --address <tegez|magaz> --agent "<agent name>" --base https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/ [--engine --tz <timezone>]
```

(`tegez` = informal, `magaz` = formal.) Tell the USER the output briefly, in your own words (without the last line): what was found in the folder, what went into the first commit, and that their uncommitted changes were left alone — then ask what should happen with those. `MENTAT-INIT HIBA: …` → that one thing is the task: say it, fix it, run the same again; a download that does not match the release is the exception: do only what its message says. No `python3` or a download error: `reference/initialization-background.en.md`.

## Step 3 — Intro chat

WebFetch and run: `https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/intro-chat/intro-questions.en.md` — one question at a time; the name and the agent name are already known. Do not skip the brain-dump demo: it is the activation event.

- An entity (case, person, todo, decision, brain dump, connector): `python3 .mentat/bin/mentat_brain.py new <type> "Title" [--due YYYY-MM-DD]` — fills the template and prints the path. Do not read templates for these. With the first case, fit `brain/cases/_meta.md` to the USER.
- With the answers, replace the two remaining `<… TBD>` placeholders in `AGENTS.md` (work; style) in a single edit. Never write inside a `mentat:managed` block.

## Step 4 — Save

`python3 .mentat/bin/mentat_scaffold.py --lang en --commit && python3 .mentat/bin/mentat_scaffold.py --lang en --check` — not done without the `OK` line: fix what it lists and run it again. Do not add a remote, do not push.

## Step 5 — Remote control

Offer it; the USER types `/rc` (it links this session to their Claude account: desktop app, web, phone). If it does not start, say so in one sentence and that they can come back to it later.

## When you are done

Top-down summary: the brain is ready, the first commit, the engine, remote control on / skipped. **Subagents** and the **development process** run as skills (`skills/subagent`, `skills/develop`; `skills/status` shows the installed building blocks).

Close with: *"From now on, tell me when something is worth saving (committing) — or I will offer."*
