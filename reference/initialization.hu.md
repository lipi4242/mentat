# Inicializálási Eljárás

Hajtsd végre sorrendben. **Addig nem vagy kész, amíg a 4. lépés nincs kész.** A BASE: `https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/`

## 1. lépés — A döntések egyetlen üzenetben

Egy üzenetben kérdezd meg, a FELHASZNÁLÓ nyelvén (az első üzenetéé, hacsak nem kért mást):
1. Hogy hívják, és tegezd vagy magázd?
2. Milyen nevet ad neked? Adj 3 rövid javaslatot (pl. Thufir, Morzsa, Kompasz), vagy választhat sajátot.
3. Kér-e proaktív motort (reggeli összefoglaló a lejáró ügyekről)? Ha igen: az időzónája (javasold a gépét: `date +%Z`).

Más kérdés most nincs; a mentést és az ellenőrzést az eszköz intézi. `--lang`: `hu`, ha magyarul ír, különben `en` (válaszolni akkor is az ő nyelvén válaszolsz). Git-azonosság: az eszköz a már beállítottat használja; csak ha nincs, akkor áll meg, és kéri a mentésein szereplő nevet és e-mail-címet (kitalált címet soha).

## 2. lépés — Telepítés egy hívással

```bash
curl -fsSL --fail-early --create-dirs -o ".mentat/bin/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/manifest/{mentat_manifest.py,mentat_rules.py,mentat_roles.py,mentat_cli.py,mentat_scaffold.py,mentat_scaffold_check.py,mentat_init.py,mentat_init_checks.py,mentat_init_inventory.py,mentat_init_os.py,mentat_init_parts.py,mentat_verify.py,mentat_dates.py,mentat_dates_text.py,mentat_dates_words.py,mentat_brain.py,mentat_brain_read.py,mentat_brain_ops.py,mentat_brain_types.py,mentat_web.py,mentat_serve.py,mentat_serve_proc.py,mentat_serve_run.py,mentat_secret.py,mentat_secret_scan.py,mentat_final.py,mentat_final_to.py,mentat_done.py,mentat_done_sched.py,mentat_contract.py,mentat_contract_store.py,mentat_contract_terms.py,mentat_contract_text.py,mentat_accept.py,mentat_accept_checks.py,mentat_accept_load.py,scaffold-meta.json,scaffold-agents.hu.md,mentat_caps.py,mentat_caps_check.py,mentat_caps_html.py,mentat_caps_ki.py,kepessegfa-map.html,mentat_caps_index.py,mentat_caps_napi.py,mentat_caps_own.py,mentat_caps_probe.py,mentat_caps_receipt.py,mentat_caps_ref.py,mentat_caps_search.py,mentat_caps_text.py,mentat_bugreport.py,mentat_bugreport_draft.py,mentat_bugreport_env.py,mentat_bugreport_gh.py,mentat_bugreport_redact.py}" -o ".mentat/bin/capabilities/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/manifest/capabilities/{brain.json,contract.json,engine.json,google.json,suite.json,web.json}" -o ".mentat/bin/bekotes/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/bekotes/{szerep_guard.py,szerep_pin.py,szerep_rules.py,szerep_tiltott.py,szerep_git.py,szerep_bash.py,szerep_kint.py,szerep_engedely.py,szerep_hook.py,szerep_dontes.py,szerep_kapu.py,szerep_kapu_db.py,szerep_kapu_kepesseg.py,szerep_kapu_id.py,szerep_kapu_iras.py,szerep_kapu_szerver.py,szerep_kapu_fut.py,szerep_stop.py,szerep_kuldes.py,szerep_prompt.py,szerep_kapu_inline.py,szerep_szoveg.py,szerep_start_sched.py,szerep_kapu_final.py,szerep_kapu_git.py,szerep_id.py,szerep_id_bash.py,szerep_id_elsofel.py,szerep_id_halozat.py,szerep_id_javaslat.py,szerep_id_felhasznaloi.py,szerep_naplo.py,fajlszuro.py}" -o ".mentat/bin/bekotes/#1" "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/manifest/{mentat_roles.py,mentat_manifest.py,mentat_rules.py}" -o .mentat/bin/release.json "https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/release.json" && python3 -I .mentat/bin/mentat_init.py --lang hu --user "<név>" --address <tegez|magaz> --agent "<ügynök neve>" --base https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/ [--engine --tz <időzóna>]
```

A kimenetet mondd el röviden, saját szavaiddal (az utolsó sor nélkül): mit talált a mappában, mi került az első commitba, és hogy a nem commitolt változásaihoz nem nyúltál; aztán kérdezd meg, mi legyen velük. `MENTAT-INIT HIBA: …` → az az egy dolog a teendő: mondd el, javítsd, futtasd újra ugyanazt; kivétel, ha a letöltés nem egyezik a kiadással: akkor csak azt tedd, amit az üzenete mond. Nincs `python3` vagy letöltési hiba: `reference/initialization-background.hu.md`.

## 3. lépés — Bemutatkozó beszélgetés

WebFetch-eld és futtasd: `https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/intro-chat/intro-questions.hu.md` — egyszerre egy kérdés; a név és az ügynök neve már megvan. A brain-dump demót ne hagyd ki: az az aktiváló esemény.

- Entitás (ügy, ember, teendő, döntés, brain dump, konnektor): `python3 .mentat/bin/mentat_brain.py new <típus> "Cím" [--due ÉÉÉÉ-HH-NN]` — kitölti a sablont, kiírja az útvonalat. Sablont ezekhez ne olvass. Az első ügynél szabd a FELHASZNÁLÓra az `agy/cases/_meta.md` definícióját.
- A válaszokkal cseréld le az `AGENTS.md` maradék két `<… TBD>` helyőrzőjét (munka; stílus) egyetlen szerkesztéssel. `mentat:managed` blokkon belül ne írj.

## 4. lépés — Mentés

`python3 .mentat/bin/mentat_scaffold.py --lang hu --commit && python3 .mentat/bin/mentat_scaffold.py --lang hu --check` — az `OK` sor nélkül nem vagy kész: amit hiányként ír, javítsd, és futtasd újra. Remote-ot ne adj hozzá, ne pusholj.

## 5. lépés — Remote control

Ajánld fel; a `/rc`-t a FELHASZNÁLÓ gépeli be (a sessiont a Claude-fiókjához köti: asztali app, web, telefon). Ha nem indul, egy mondatban mondd el, hogy később visszatérhet rá.

## A befejezés után

Top-down összefoglaló: az agy kész, az első commit, a motor, remote control be / kihagyva. A **subagentek** és a **fejlesztési folyamat** skillként futnak (`skills/subagent`, `skills/develop`; `skills/status` a telepített elemeket mutatja).

Zárd így: *„Mostantól szólj, ha valamit érdemes elmenteni (commitolni) — vagy én ajánlom fel."*
