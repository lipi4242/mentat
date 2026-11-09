---
name: model
description: Melyik modellen fut ez az ágens — Claude (alap) vagy egy mért nyílt modell OpenRouteren át —, átállás és visszaállás egy paranccsal, élő próbával. Használd, ha a FELHASZNÁLÓ modellt váltana, olcsóbb vagy Claude-független futást kér, vagy azt kérdezi, min futsz.
---

# Skill — `model`

**Mikor:** a FELHASZNÁLÓ azt kéri, hogy „állj át DeepSeekre”, „fuss olcsóbb modellen”, „vissza Claude-ra”, vagy megkérdezi, min futsz.

Ez csak **ezt az ágenst** (ezt a repót) állítja át. A közös Claude-belépéshez (`~/.claude`) nem nyúl, ezért ugyanazon a gépen a többi ágens Claude-on marad. Egy másik ágenst úgy állítasz át, hogy **neki** szólsz.

## 1. lépés — Az eszköz

Ha hiányzik a `.mentat/bin/mentat_model.py` (nincs commitolva):

```bash
mkdir -p .mentat/bin
for f in mentat_model.py mentat_model_cfg.py mentat-models.json; do curl -fsSL https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/reference/manifest/$f -o .mentat/bin/$f; done
```

## 2. lépés — Mit ajánlasz

`python3 .mentat/bin/mentat_model.py list` — csak a **mért** modelleket ajánld, a sor megjegyzésével (pont az Opushoz képest, ár). Ha a FELHASZNÁLÓ mást kér, mondd meg, hogy az nincs mérve; csak kifejezett kérésre használd a `--force`-ot.

## 3. lépés — A kulcs

A FELHASZNÁLÓ **soha nem gépel parancsot**: emberi nyelven beszéltek, a parancsokat te futtatod.

`python3 .mentat/bin/mentat_model.py status` → ha a `KEY missing`:

- Kérd meg, hogy az openrouter.ai-on hozzon létre egy **külön, keretlimites** kulcsot ennek az ágensnek.
- **Ha ugyanazon a Macen vagy, ahol ő ül:** kérd meg, hogy másolja a vágólapra, és szóljon („kész”). Ekkor TE futtatod: `python3 .mentat/bin/mentat_model.py key --clipboard` — a kulcs így nem kerül a beszélgetésbe. Utána kérd meg, hogy másoljon valami mást a vágólapra.
- **Távoli ágensnél** (csak üzenetben elérhető): mondd meg őszintén, hogy az üzenetbe írt kulcs a beszélgetésnaplóban és a csatornán is megmarad; ha így is kéri, **privátban** küldje (csoportban soha), és add át stdin-en (`printf '%s\n' "<kulcs>" | python3 .mentat/bin/mentat_model.py key`). Javasold a kulcs keretlimitjét.

A kulcsot soha ne írd vissza, és ne tedd fájlba magad.

## 4. lépés — Átállás

**Átváltás előtt mondd el a FELHASZNÁLÓNAK:** innentől minden, amit ez az ágens olvas (agy, fájlok, beszélgetés), az OpenRouterhez és az általa választott szolgáltatóhoz megy. Kérd meg, hogy az openrouter.ai **Settings → Privacy** alatt állítsa be: csak zero-data-retention végpontok, és tiltsa a bemenetből tanuló szolgáltatókat.

`python3 .mentat/bin/mentat_model.py use <modell-id>` — beállítja ennek a repónak a `.claude/settings.local.json`-ját (git-ignorált, 0600), és egy élő próbával ellenőrzi, hogy a válasz tényleg a kért modelltől jön. Ha nem, mindent visszaállít (`ROLLED BACK`), és az ágens a régi modellen marad: ezt mondd meg, ne próbáld kerülőúton.

## 5. lépés — Újraindulás (ezt is te intézed)

A futó session a régi modellen marad. Az eszköz utolsó sora mondja meg, mi történik:

- `RESTART in 20 s` (always-on ágens): az eszköz kívülről ütemezte az újraindulásodat. **Azonnal** mondd meg a FELHASZNÁLÓNAK: „fél perc múlva újraindulok az új modellen, utána szólok”. Az új session első válaszában futtasd a `status`-t, és mondd meg, min futsz.
- `NEXT … no fleet command`: ezen a gépen nincs flotta; kérd meg az ágenst, aki téged kitelepített, hogy indítson újra. A FELHASZNÁLÓTÓL parancsot ne kérj.
- `NEXT tell the USER…` (interaktív session): mondd neki egyszerűen: „zárd be ezt az ablakot, és nyiss egy újat ebben a mappában”.

A saját unitodat a saját sessionödből soha ne indítsd újra (`systemctl restart`): az a parancs közepén téged öl meg.

## 6. lépés — Visszaállás

`python3 .mentat/bin/mentat_model.py use claude` — csak a saját kulcsait veszi ki; utána ugyanaz az újraindulás, és ugyanúgy te intézed.

## Mondd el a FELHASZNÁLÓNAK

Egy-két sorban: min futsz most, mennyibe kerül a mérés szerint, mi változott (csak ez az ágens), és mi a következő lépés (újraindulás). Ne mutass JSON-t és tokent.
